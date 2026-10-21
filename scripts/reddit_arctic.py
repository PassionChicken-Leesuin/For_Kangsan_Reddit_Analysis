#!/usr/bin/env python3
"""Arctic Shift Reddit crawler.

modes:
  posts            : date-paginate all posts of each subreddit into raw/posts_<sub>.jsonl (resumable)
  filter           : local keyword filter -> posts_all.csv, posts_filtered.csv
  comments         : fetch full comment trees for filtered posts -> comments/comments.jsonl, comments.csv, comments_filtered.csv
  export-comments  : rebuild comments.csv / comments_filtered.csv from comments.jsonl
  comments-by-date : date-paginate all comments of a subreddit -> raw/comments_bydate_<sub>.jsonl

usage:
  python3 reddit_arctic.py posts --data DIR --subs ClaudeAI,ClaudeCode --after 2026-07-20 --before 2026-10-20
  python3 reddit_arctic.py filter --data DIR --keywords keywords.json
  python3 reddit_arctic.py comments --data DIR --keywords keywords.json [--min-hits 1] [--max-posts N]
"""
import argparse, csv, datetime, json, os, sys, time, urllib.error, urllib.parse, urllib.request

BASE = "https://arctic-shift.photon-reddit.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
POST_FIELDS = "id,created_utc,subreddit,author,title,selftext,score,num_comments,url,link_flair_text,over_18"
COMMENT_FIELDS = "id,created_utc,subreddit,author,body,score,link_id,parent_id"
SLEEP = 1.2


def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def get(path, params, max_tries=8):
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    backoff = 5
    for attempt in range(1, max_tries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                body = json.loads(r.read().decode("utf-8"))
                if body.get("data") is None:
                    raise RuntimeError(body.get("error", "no data"))
                return body["data"]
        except urllib.error.HTTPError as e:
            txt = ""
            try:
                txt = e.read().decode("utf-8")[:200]
            except Exception:
                pass
            if e.code == 429:
                reset = e.headers.get("X-RateLimit-Reset")
                wait = int(float(reset)) + 2 if reset else 60
                log(f"  429 rate limited; sleeping {wait}s")
                time.sleep(wait)
                continue
            if e.code == 400:
                raise RuntimeError(f"400 bad request: {txt}")
            log(f"  HTTP {e.code} ({txt[:80]}); retry {attempt}/{max_tries} in {backoff}s")
        except Exception as e:
            log(f"  error {type(e).__name__}: {str(e)[:100]}; retry {attempt}/{max_tries} in {backoff}s")
        time.sleep(backoff)
        backoff = min(backoff * 2, 120)
    raise RuntimeError(f"giving up on {path} {params}")


def to_epoch(s):
    if s.isdigit():
        return int(s)
    return int(datetime.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp())


def load_state(data, name="state_posts"):
    p = os.path.join(data, f"{name}.json")
    if os.path.exists(p):
        return json.load(open(p))
    return {}


def save_state(data, st, name="state_posts"):
    p = os.path.join(data, f"{name}.json")
    tmp = p + ".tmp"
    json.dump(st, open(tmp, "w"), ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def paginate(path, params_base, out_path, state_key, st, data, start, end, label, state_name="state_posts"):
    seen = {r["id"] for r in read_jsonl(out_path)}
    sst = st.setdefault(state_key, {})
    if sst.get("done"):
        log(f"{label}: already done ({sst.get('count', 0)} items)")
        return
    cur = sst.get("after", start)
    total = sst.get("count", len(seen))
    pages = 0
    with open(out_path, "a", encoding="utf-8") as out:
        while cur < end:
            params = dict(params_base, after=cur, before=end, limit=100, sort="asc")
            items = get(path, params)
            pages += 1
            if not items:
                break
            new = [x for x in items if x["id"] not in seen]
            for x in new:
                seen.add(x["id"])
                out.write(json.dumps(x, ensure_ascii=False) + "\n")
            out.flush()
            total += len(new)
            last = max(x["created_utc"] for x in items)
            if not new:
                cur = last + 1
            else:
                cur = last - 1 if last - 1 > cur else last
                if cur <= params["after"]:
                    cur = last + 1
            sst.update(after=cur, count=total)
            if pages % 5 == 0:
                save_state(data, st, state_name)
            d = datetime.datetime.utcfromtimestamp(last).strftime("%Y-%m-%d %H:%M")
            log(f"{label}: page {pages} +{len(new)} (total {total}) reached {d}")
            if len(items) < 100:
                break
            time.sleep(SLEEP)
    sst.update(done=True, count=total)
    save_state(data, st, state_name)
    log(f"{label}: DONE {total} items")


def cmd_posts(a):
    st = load_state(a.data, "state_posts")
    start, end = to_epoch(a.after), to_epoch(a.before)
    for sub in [s.strip() for s in a.subs.split(",") if s.strip()]:
        out_path = os.path.join(a.data, "raw", f"posts_{sub}.jsonl")
        paginate("/api/posts/search", {"subreddit": sub, "fields": POST_FIELDS}, out_path,
                 sub, st, a.data, start, end, f"r/{sub} posts", "state_posts")


def cmd_comments_by_date(a):
    st = load_state(a.data, "state_comments_bydate")
    start, end = to_epoch(a.after), to_epoch(a.before)
    for sub in [s.strip() for s in a.subs.split(",") if s.strip()]:
        out_path = os.path.join(a.data, "raw", f"comments_bydate_{sub}.jsonl")
        paginate("/api/comments/search", {"subreddit": sub, "fields": COMMENT_FIELDS}, out_path,
                 sub, st, a.data, start, end, f"r/{sub} comments", "state_comments_bydate")


def load_keywords(path):
    kw = json.load(open(path, encoding="utf-8"))
    groups = {g: [t.lower() for t in terms] for g, terms in kw["groups"].items()}
    return kw, groups


def match(text, kw, groups, sub):
    t = text.lower()
    hits = {}
    for g, terms in groups.items():
        found = [term for term in terms if term in t]
        if found:
            hits[g] = found
    if not hits:
        return None
    if sub not in kw["agent_subs"]:
        if not any(c in t for c in kw["agentic_context"]):
            return None
    return hits


def permalink(sub, pid):
    return f"https://www.reddit.com/r/{sub}/comments/{pid}/"


def cmd_filter(a):
    kw, groups = load_keywords(a.keywords)
    raw_dir = os.path.join(a.data, "raw")
    rows_all, rows_f = [], []
    for fn in sorted(os.listdir(raw_dir)):
        if not fn.startswith("posts_") or not fn.endswith(".jsonl"):
            continue
        for p in read_jsonl(os.path.join(raw_dir, fn)):
            body = p.get("selftext") or ""
            if body in ("[removed]", "[deleted]"):
                body = ""
            row = {
                "id": p["id"],
                "date": datetime.datetime.utcfromtimestamp(p["created_utc"]).strftime("%Y-%m-%d"),
                "created_utc": p["created_utc"],
                "subreddit": p.get("subreddit", ""),
                "author": p.get("author", ""),
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "flair": p.get("link_flair_text") or "",
                "title": p.get("title", ""),
                "selftext": body,
                "url": permalink(p.get("subreddit", ""), p["id"]),
            }
            rows_all.append(row)
            hits = match(row["title"] + "\n" + body, kw, groups, row["subreddit"])
            if hits:
                r = dict(row)
                r["n_groups"] = len(hits)
                r["n_hits"] = sum(len(v) for v in hits.values())
                r["core_groups"] = len([g for g in hits if g != "affect_identity"])
                r["hit_groups"] = ";".join(hits.keys())
                r["hit_terms"] = ";".join(sorted({t for v in hits.values() for t in v}))
                rows_f.append(r)
    rows_f.sort(key=lambda r: (-r["core_groups"], -r["n_groups"], -r["n_hits"], -r["num_comments"]))
    cols_all = ["id", "date", "subreddit", "author", "score", "num_comments", "flair", "title", "selftext", "url", "created_utc"]
    cols_f = ["id", "date", "subreddit", "core_groups", "n_groups", "n_hits", "hit_groups", "hit_terms", "score", "num_comments", "flair", "title", "selftext", "url", "author", "created_utc"]
    with open(os.path.join(a.data, "posts_all.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols_all, extrasaction="ignore"); w.writeheader(); w.writerows(rows_all)
    with open(os.path.join(a.data, "posts_filtered.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols_f, extrasaction="ignore"); w.writeheader(); w.writerows(rows_f)
    by_sub = {}
    for r in rows_f:
        by_sub[r["subreddit"]] = by_sub.get(r["subreddit"], 0) + 1
    log(f"filter: {len(rows_all)} posts total -> {len(rows_f)} filtered; by sub: {by_sub}")


def flatten(nodes, depth, link_id, out):
    for n in nodes:
        if n.get("kind") == "more":
            continue
        d = n.get("data", n)
        out.append({
            "id": d.get("id"), "link_id": link_id, "parent_id": d.get("parent_id"), "depth": depth,
            "created_utc": d.get("created_utc"), "author": d.get("author"), "score": d.get("score"),
            "body": d.get("body") or "", "subreddit": d.get("subreddit"),
        })
        kids = d.get("replies") or n.get("replies") or []
        if isinstance(kids, dict):
            kids = kids.get("data", {}).get("children", [])
        if kids:
            flatten(kids, depth + 1, link_id, out)


def cmd_comments(a):
    st = load_state(a.data, "state_comments")
    kw, groups = load_keywords(a.keywords)
    done = set(st.get("comments_done", []))
    fp = os.path.join(a.data, "posts_filtered.csv")
    posts = list(csv.DictReader(open(fp, encoding="utf-8-sig")))
    subs = {x.strip() for x in a.subs.split(",") if x.strip()}
    todo = [p for p in posts if int(p["num_comments"] or 0) > 0 and int(p["n_hits"]) >= a.min_hits
            and int(p.get("core_groups") or 0) >= a.min_core and (not subs or p["subreddit"] in subs) and p["id"] not in done]
    if a.max_posts:
        todo = todo[: a.max_posts]
    log(f"comments: {len(todo)} posts to fetch ({len(done)} already done)")
    out_path = os.path.join(a.data, "comments", "comments.jsonl")
    with open(out_path, "a", encoding="utf-8") as out:
        for i, p in enumerate(todo, 1):
            try:
                tree = get("/api/comments/tree", {"link_id": f"t3_{p['id']}", "limit": 9999})
            except Exception as e:
                log(f"  skip {p['id']}: {e}")
                continue
            flat = []
            flatten(tree, 0, p["id"], flat)
            for c in flat:
                c["post_subreddit"] = p["subreddit"]
                out.write(json.dumps(c, ensure_ascii=False) + "\n")
            out.flush()
            done.add(p["id"])
            st["comments_done"] = sorted(done)
            if i % 10 == 0:
                save_state(a.data, st, "state_comments")
            log(f"  [{i}/{len(todo)}] r/{p['subreddit']} {p['id']} -> {len(flat)} comments | {p['title'][:50]}")
            time.sleep(SLEEP)
    st["comments_done"] = sorted(done)
    save_state(a.data, st, "state_comments")
    export_comments(a.data, kw, groups)


def export_comments(data, kw, groups):
    rows = read_jsonl(os.path.join(data, "comments", "comments.jsonl"))
    cols = ["id", "link_id", "parent_id", "depth", "date", "post_subreddit", "author", "score", "body", "url", "created_utc"]
    out_all, out_f = [], []
    for c in rows:
        if not c.get("body") or c["body"] in ("[removed]", "[deleted]"):
            continue
        r = dict(c)
        r["date"] = datetime.datetime.utcfromtimestamp(c["created_utc"]).strftime("%Y-%m-%d") if c.get("created_utc") else ""
        r["url"] = f"https://www.reddit.com/r/{c.get('post_subreddit','')}/comments/{c['link_id']}/_/{c['id']}/"
        out_all.append(r)
        hits = match(c["body"], kw, groups, c.get("post_subreddit", ""))
        if hits:
            rf = dict(r)
            rf["n_groups"] = len(hits); rf["n_hits"] = sum(len(v) for v in hits.values())
            rf["hit_groups"] = ";".join(hits.keys()); rf["hit_terms"] = ";".join(sorted({t for v in hits.values() for t in v}))
            out_f.append(rf)
    out_f.sort(key=lambda r: (-r["n_groups"], -r["n_hits"], -(r["score"] or 0)))
    with open(os.path.join(data, "comments.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(out_all)
    with open(os.path.join(data, "comments_filtered.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["n_groups", "n_hits", "hit_groups", "hit_terms"] + cols, extrasaction="ignore"); w.writeheader(); w.writerows(out_f)
    log(f"comments export: {len(out_all)} comments, {len(out_f)} keyword-matched")


def main():
    global SLEEP
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["posts", "filter", "comments", "comments-by-date", "export-comments"])
    ap.add_argument("--data", required=True)
    ap.add_argument("--subs", default="")
    ap.add_argument("--after", default="2026-07-20")
    ap.add_argument("--before", default="2026-10-20")
    ap.add_argument("--keywords", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "keywords.json"))
    ap.add_argument("--min-hits", type=int, default=1)
    ap.add_argument("--max-posts", type=int, default=0)
    ap.add_argument("--min-core", type=int, default=0, help="comments: only posts with core_groups >= N")
    ap.add_argument("--sleep", type=float, default=SLEEP, help="seconds between requests")
    a = ap.parse_args()
    SLEEP = a.sleep
    os.makedirs(os.path.join(a.data, "raw"), exist_ok=True)
    os.makedirs(os.path.join(a.data, "comments"), exist_ok=True)
    if a.mode == "posts":
        cmd_posts(a)
    elif a.mode == "filter":
        cmd_filter(a)
    elif a.mode == "comments":
        cmd_comments(a)
    elif a.mode == "comments-by-date":
        cmd_comments_by_date(a)
    elif a.mode == "export-comments":
        kw, groups = load_keywords(a.keywords); export_comments(a.data, kw, groups)


if __name__ == "__main__":
    main()
