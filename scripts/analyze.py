#!/usr/bin/env python3
"""Keyword, co-occurrence and laddering analysis of the crawled Reddit data.
Inputs : data/reddit/{posts_all.csv, posts_filtered.csv, comments.csv, comments_filtered.csv}
Outputs: analysis/ (corpus.csv, keyword_*.csv, cooccurrence_*.csv, laddering_*.csv, implication_*.csv, hvm_*.csv, *.png, laddering_quotes.md)
usage  : analyze.py <project_dir>
"""
import csv, json, os, re, sys, datetime, collections, itertools, math, warnings
warnings.filterwarnings("ignore")
csv.field_size_limit(10**9)
ROOT = sys.argv[1]
D = os.path.join(ROOT, "data"); OUT = os.path.join(ROOT, "analysis"); os.makedirs(OUT, exist_ok=True)
KW = json.load(open(os.path.join(ROOT, "scripts", "keywords.json"), encoding="utf-8"))
AGENT_SUBS = set(KW["agent_subs"])
CORE_GROUPS = ["waiting_idle", "flow_attention", "supervision_intervention", "resume_return"]
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt; HAVE_MPL = True
except Exception:
    HAVE_MPL = False
try:
    import networkx as nx; HAVE_NX = True
except Exception:
    HAVE_NX = False

def rd(p): return list(csv.DictReader(open(p, encoding="utf-8-sig")))
def wr(p, rows, cols):
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
def week_of(d):
    dt = datetime.date.fromisoformat(d); return (dt - datetime.timedelta(days=dt.weekday())).isoformat()
def norm(t): return re.sub(r"\s+", " ", (t or "")).strip()

posts_all = rd(os.path.join(D, "reddit", "posts_all.csv"))
posts_f = {r["id"]: r for r in rd(os.path.join(D, "reddit", "posts_filtered.csv"))}
comments_all = rd(os.path.join(D, "reddit", "comments.csv"))
comments_f = {r["id"]: r for r in rd(os.path.join(D, "reddit", "comments_filtered.csv"))}
W0, W1 = min(p["date"] for p in posts_all), max(p["date"] for p in posts_all)
print(f"loaded: reddit posts {len(posts_all)} (filtered {len(posts_f)}), comments {len(comments_all)} (matched {len(comments_f)}), window {W0} ~ {W1}")

corpus = []
for p in posts_all:
    f = posts_f.get(p["id"])
    if not f or int(f["core_groups"]) < 1: continue
    corpus.append(dict(source="reddit_post", id=p["id"], date=p["date"], subreddit=p["subreddit"], score=p["score"],
                       text=norm(p["title"] + ". " + p["selftext"]), url=p["url"], hit_groups=f["hit_groups"], core_groups=f["core_groups"]))
for c in comments_all:
    f = comments_f.get(c["id"])
    if not f: continue
    if not (W0 <= c["date"] <= W1): continue
    hg = set(f["hit_groups"].split(";")); core = len(hg & set(CORE_GROUPS))
    if core < 1: continue
    corpus.append(dict(source="reddit_comment", id=c["id"], date=c["date"], subreddit=c["post_subreddit"], score=c["score"],
                       text=norm(c["body"]), url=c["url"], hit_groups=f["hit_groups"], core_groups=str(core)))
FP = re.compile(r"\b(i|i'm|i’m|i've|i’ve|my|me|myself)\b", re.I)
TOOL = re.compile(r"claude|codex|cursor|copilot|windsurf|devin|cline|aider|gemini cli|\bagents?\b|vibe[- ]cod|opencode|jules", re.I)
EXP = re.compile(r"\bwait(ing|ed|s)?\b|idle|bored|boredom|twiddl|staring|doomscroll|in the meantime|while (it|claude|codex|cursor|the agent|agents?) (runs?|works?|is working|does)|lose track|losing track|lost track|keep track|which (session|one|terminal|agent)|where i (was|left off)|context[- ]switch|switching between|alt[- ]tab|\bflow\b|focus|babysit|keep checking|constantly checking|check(ing)? on|watching (it|the terminal)|interrupt|permission prompt|approve every|approval fatigue|asks? me|needs? me|waiting on me", re.I)
WAIT_RX = re.compile(r"\bwait(ing|ed|s)?\b|idle|twiddl|staring (at|into)|dead time|downtime", re.I)
QUOTA_RX = re.compile(r"usage limit|rate[- ]?limit|\blimits?\b|quota|usage (window|cap|reset)|reset(s|ting)?\b|5[- ]hour|five[- ]hour|weekly (limit|cap|window)|credits?\b|tokens? (ran|run) out|out of (tokens|credits|usage)|capacity|cooldown|throttl|overloaded|outage|\bdown\b|529|rate limited|hit (the|my) (limit|cap)", re.I)
AGENTWAIT_RX = re.compile(r"wait(ing|ed|s)? (for|on) (it|claude|codex|cursor|copilot|the agent|agents?|the (model|ai|llm|output|response|result|task|run|build|tests?)|a (response|reply|permission)|my agent|the (next|first) (step|turn))|while (it|claude|codex|cursor|the agent|agents?) (runs?|works?|is working|does|thinks?|generates?|codes?)|wait(ing)? (for|until) (it|the agent|claude|codex) (to )?(finish|complete|respond|come back|return)|permission|approv|stuck on|needs? (me|my input)|waiting on me|waiting for me|to finish|finishes|finished running|long[- ]running|runs? for|minutes? (of|to) (run|wait)", re.I)
def wait_type(text):
    if not WAIT_RX.search(text): return "none"
    a = bool(AGENTWAIT_RX.search(text)); q = bool(QUOTA_RX.search(text))
    if a and q: return "both"
    if a: return "agent"
    if q: return "quota"
    return "unspecified"
EXP_NOWAIT = re.compile(r"doomscroll|in the meantime|while (it|claude|codex|cursor|the agent|agents?) (runs?|works?|is working|does)|lose track|losing track|lost track|keep track|which (session|one|terminal|agent)|where i (was|left off)|context[- ]switch|switching between|alt[- ]tab|\bflow\b|focus|babysit|keep checking|constantly checking|check(ing)? on|watching (it|the terminal)|interrupt|permission prompt|approve every|approval fatigue|asks? me|needs? me|waiting on me|bored|boredom", re.I)
TRADING_RX = re.compile(r"\b(trading|trader|trades?|crypto|bitcoin|btc|solana|ethereum|eth|wallet|defi|forex|stocks?|options|futures|portfolio|pnl|airdrop|memecoin|on-?chain|perps?|leverage|liquidat)\b", re.I)
CODING_RX = re.compile(r"claude code|codex|cursor|copilot|windsurf|cline|aider|vibe[- ]cod|coding|\bcode\b|terminal|repo|pull request|\bPRs?\b|refactor|commit|compile|tests?\b|debug", re.I)
PROMO_RX = re.compile(r"https?://|github\.com|\bi (built|made|created|launched|shipped)\b|check it out|introducing|open[- ]source", re.I)
for d in corpus:
    d["wait_type"] = wait_type(d["text"])
    d["trading"] = int(bool(TRADING_RX.search(d["text"]) and not CODING_RX.search(d["text"])))
    d["promo"] = int(bool(PROMO_RX.search(d["text"]) and re.search(r"\bi (built|made|created|launched|shipped)\b", d["text"], re.I)))
    f = bool(FP.search(d["text"]) and TOOL.search(d["text"]) and EXP.search(d["text"]) and (int(d["core_groups"]) >= 2 or bool(re.search(r"\bwait|idle|bored|lose track|losing track|lost track|keep track|context[- ]switch|switching between|babysit|while (it|claude|codex|cursor|the agent|agents?) (runs?|works?|is working)", d["text"], re.I))))
    if f and d["wait_type"] == "quota" and not EXP_NOWAIT.search(d["text"]): f = False
    if f and d["trading"]: f = False
    d["focus"] = int(f)
wr(os.path.join(OUT, "corpus.csv"), corpus, ["source", "id", "date", "subreddit", "score", "focus", "wait_type", "trading", "promo", "core_groups", "hit_groups", "text", "url"])
print("excluded as trading/crypto:", sum(d["trading"] for d in corpus), "| promo-flagged:", sum(d["promo"] for d in corpus))
print("wait types (experience docs):", collections.Counter(d["wait_type"] for d in corpus))
print("corpus (experience docs, core>=1):", collections.Counter(d["source"] for d in corpus))
focus = [d for d in corpus if d["focus"]]
print("focus docs (first-person delegation experience):", collections.Counter(d["source"] for d in focus), "total", len(focus))
print("wait types (focus docs):", collections.Counter(d["wait_type"] for d in focus))

groups = {g: [t.lower() for t in ts] for g, ts in KW["groups"].items()}
HYPE = ["productiv", "10x", "100x", "faster", "ship", "game changer", "game-changer", "saves me", "save time", "time saver", "saved me", "hours of work", "in minutes", "hands-free", "while i sleep", "overnight", "autonomous"]
def hits_in(text):
    t = text.lower()
    return {g: [term for term in ts if term in t] for g, ts in groups.items()}
term_docs = collections.Counter(); group_docs = collections.Counter()
weekly = collections.defaultdict(lambda: collections.Counter())
bysub = collections.defaultdict(lambda: collections.Counter())
for p in posts_all:
    t = (p["title"] + " " + p["selftext"]).lower()
    agent = p["subreddit"] in AGENT_SUBS
    wk = week_of(p["date"])
    weekly[wk]["posts"] += 1; bysub[p["subreddit"]]["posts"] += 1
    if agent: weekly[wk]["agent_posts"] += 1
    hit_any_core = False
    for g, ts in groups.items():
        found = [term for term in ts if term in t]
        if found:
            group_docs[g] += 1; bysub[p["subreddit"]][g] += 1
            for term in found: term_docs[(g, term)] += 1
            if g in CORE_GROUPS: hit_any_core = True
    if hit_any_core:
        weekly[wk]["friction"] += 1; bysub[p["subreddit"]]["friction"] += 1
        if agent: weekly[wk]["agent_friction"] += 1
    if any(h in t for h in HYPE):
        weekly[wk]["hype"] += 1; bysub[p["subreddit"]]["hype"] += 1
        if agent: weekly[wk]["agent_hype"] += 1
    wt = wait_type(p["title"] + " " + p["selftext"])
    if wt in ("agent", "both"):
        weekly[wk]["wait_agent"] += 1; bysub[p["subreddit"]]["wait_agent"] += 1
        if agent: weekly[wk]["agent_wait_agent"] += 1
    if wt in ("quota", "both"):
        weekly[wk]["wait_quota"] += 1; bysub[p["subreddit"]]["wait_quota"] += 1
        if agent: weekly[wk]["agent_wait_quota"] += 1
rows = [dict(group=g, term=term, posts=n, share_pct=round(100 * n / len(posts_all), 2)) for (g, term), n in term_docs.most_common()]
wr(os.path.join(OUT, "keyword_terms.csv"), rows, ["group", "term", "posts", "share_pct"])
focus_weekly = collections.Counter(week_of(d["date"]) for d in focus if d["source"] == "reddit_post")
rows = []
for wk in sorted(weekly):
    c = weekly[wk]
    c["focus_posts"] = focus_weekly.get(wk, 0)
    full = int((datetime.date.fromisoformat(wk) + datetime.timedelta(days=6)).isoformat() <= W1)
    rows.append(dict(week=wk, full_week=full, posts=c["posts"], friction=c["friction"], friction_pct=round(100 * c["friction"] / max(c["posts"], 1), 2),
                     hype=c["hype"], hype_pct=round(100 * c["hype"] / max(c["posts"], 1), 2),
                     agent_posts=c["agent_posts"], agent_friction=c["agent_friction"], agent_friction_pct=round(100 * c["agent_friction"] / max(c["agent_posts"], 1), 2),
                     agent_hype=c["agent_hype"], agent_hype_pct=round(100 * c["agent_hype"] / max(c["agent_posts"], 1), 2),
                     agent_friction_to_hype=round(c["agent_friction"] / max(c["agent_hype"], 1), 2),
                     focus_posts=c["focus_posts"], focus_per_1000=round(1000 * c["focus_posts"] / max(c["agent_posts"], 1), 2),
                     agent_wait_agent_pct=round(100 * c["agent_wait_agent"] / max(c["agent_posts"], 1), 2),
                     agent_wait_quota_pct=round(100 * c["agent_wait_quota"] / max(c["agent_posts"], 1), 2)))
wr(os.path.join(OUT, "keyword_weekly.csv"), rows, list(rows[0].keys()))
weekly_rows = rows
rows = []
for sub, c in sorted(bysub.items(), key=lambda kv: -kv[1]["posts"]):
    r = dict(subreddit=sub, posts=c["posts"], friction=c["friction"], friction_pct=round(100 * c["friction"] / c["posts"], 2), hype=c["hype"], hype_pct=round(100 * c["hype"] / c["posts"], 2),
             wait_agent_pct=round(100 * c["wait_agent"] / c["posts"], 2), wait_quota_pct=round(100 * c["wait_quota"] / c["posts"], 2))
    for g in groups: r[g + "_pct"] = round(100 * c[g] / c["posts"], 2)
    rows.append(r)
wr(os.path.join(OUT, "keyword_by_subreddit.csv"), rows, list(rows[0].keys()))
print("keyword: group doc counts over all reddit posts:", dict(group_docs), "| hype posts:", sum(c["hype"] for c in weekly.values()))

CONCEPTS = {
    "waiting (agent)": r"__AGENTWAIT__",
    "waiting (quota)": r"__QUOTAWAIT__",
    "bored/idle": r"\b(bored|boredom|idle|twiddl|staring (at|into)|dead time|downtime|kill(ing)? time)",
    "permission/approval": r"permission|approv",
    "babysitting": r"babysit|baby-sit",
    "interruption": r"interrupt",
    "parallel sessions": r"(parallel|multiple|several|\d+\+?) (sessions|agents|terminals|projects|tabs|windows)|in parallel|at once|simultaneous",
    "losing track": r"lose track|losing track|lost track|keep track|which (session|one|terminal|agent)|reconstruct",
    "context switching": r"context[- ]switch|switching between|alt[- ]tab|tab[- ]switch|juggl",
    "focus/flow": r"\bflow\b|focus|concentrat|deep work|in the zone",
    "constant checking": r"keep checking|constantly checking|check(ing)? on|polling|watching (it|the terminal)|keep looking|keep an eye|glance",
    "notification": r"notif|alert|chime|\bsound\b|\bbell\b|badge|ping",
    "built a tool": r"i built|built a|built an|menu bar|dashboard|extension|visualizer|open[- ]source",
    "anxiety/stress": r"anxi|stress|panic|overwhelm|nervous",
    "exhaustion": r"exhaust|fatigue|burn(ed|t)? ?out|drain|tired|melting",
    "frustration": r"frustrat|annoy|infuriat|hate",
    "role shift": r"manager|tech lead|intern|middleware|orchestrat|my (actual )?job (has )?(quietly )?(changed|shifted)|barely (write|type) code|don't code anymore|not really coding",
    "deskilling": r"deskill|atrophy|losing (my )?skills|lose (my )?skills|lazy|useless|rusty",
    "autonomy/hands-off": r"autonom|hands[- ]off|unattended|let it (run|cook)|fire and forget|yolo|auto[- ]?accept|skip[- ]permissions|dangerously",
    "speed": r"too fast|slower|faster|speed|quick",
    "review burden": r"review|verif|double[- ]check|rework|audit",
    "productivity": r"productiv|throughput|10x|100x|\bship",
    "usage limits": r"\blimit|quota|usage window|5-hour|5 hour|reset|rate[- ]limit",
    "trust": r"\btrust",
    "context loss (agent)": r"(lose|lost|loses|losing) (its |the )?(context|train of thought|thread)|forgets|memory",
    "relief/freedom": r"make coffee|go to sleep|go for a walk|leave my desk|free(s|d)? (me|up)|\brelax|retire|while i sleep",
    "tethered to desk": r"can'?t leave|not gonna leave|stuck at my desk|at my desk|glued|chained",
    "multitasking": r"multi[- ]?task",
    "adhd": r"\badhd\b",
}
CRX = {k: re.compile(v, re.I) for k, v in CONCEPTS.items() if not v.startswith("__")}
ANALYSIS_DOCS = focus
doc_concepts = []
for d in ANALYSIS_DOCS:
    cs = {k for k, rx in CRX.items() if rx.search(d["text"])}
    if d["wait_type"] in ("agent", "both", "unspecified"): cs.add("waiting (agent)")
    if d["wait_type"] in ("quota", "both"): cs.add("waiting (quota)")
    doc_concepts.append(cs)
cnt = collections.Counter(); pair = collections.Counter()
for cs in doc_concepts:
    for k in cs: cnt[k] += 1
    for a, b in itertools.combinations(sorted(cs), 2): pair[(a, b)] += 1
N = len(ANALYSIS_DOCS)
rows = [dict(concept=k, docs=n, share_pct=round(100 * n / N, 2)) for k, n in cnt.most_common()]
wr(os.path.join(OUT, "cooccurrence_nodes.csv"), rows, ["concept", "docs", "share_pct"])
rows = []
for (a, b), n in pair.most_common():
    pmi = math.log((n * N) / (cnt[a] * cnt[b])) if n else 0
    rows.append(dict(source=a, target=b, docs=n, pmi=round(pmi, 3), jaccard=round(n / (cnt[a] + cnt[b] - n), 3)))
wr(os.path.join(OUT, "cooccurrence_edges.csv"), rows, ["source", "target", "docs", "pmi", "jaccard"])
print("co-occurrence: top concepts", cnt.most_common(8))

LADDER = {
  "A": {
    "A1 장시간 자율 실행": r"while (it|claude|codex|the agent|agents?) (runs?|works?|is working|does)|runs? for (hours|minutes)|for \d+ (minutes|hours)|let it (run|cook)|in the background|overnight|long[- ]running|background agent",
    "A2 승인·권한 프롬프트": r"permission prompt|permission|approv|allow (it|the agent) to|confirm (every|each)",
    "A3 질문·개입 요청": r"asks? me|keeps asking|ask(ing)? (a )?question|interrupt|needs? (me|my input|attention)|waiting (on|for) (me|you|my|input|approval)|clarif",
    "A4 병렬 다중 세션": r"(parallel|multiple|several|\d+\+?) (sessions|agents|terminals|projects|tabs|windows|worktrees)|in parallel|at once|simultaneous|swarm",
    "A5 알림·상태 가시성": r"notif|alert|chime|sound|bell|badge|status|dashboard|menu bar|visibility|indicator",
    "A6 자율 모드(auto-accept·YOLO)": r"yolo|auto[- ]?accept|auto[- ]?approve|skip[- ]permissions|dangerously|hands[- ]off|unattended|full(y)? autonomous|bypass",
    "A7 에이전트 신뢰성(속도·문맥 손실·탈선)": r"too fast|way too fast|so fast|slower|(lose|lost|loses|losing) (its |the )?(context|train of thought|thread)|forgets|compaction|context window|off the rails|off track|drift|hallucinat|wrong direction",
  },
  "Cf": {
    "C1 대기·공백 시간": r"__WAIT_AGENT__",
    "C2 놓침·재구성": r"lose track|losing track|lost track|keep track|which (session|one|terminal|agent)|reconstruct|where i (was|left off)|what was i doing|figure out what (it|they) did",
    "C3 문맥 전환·내 작업 중단": r"context[- ]switch|switching between|alt[- ]tab|tab[- ]switch|juggl|switch(ing)? (back|over|to)|interrupt(s|ed|ing)? (me|my)|pull(ed|s)? me|breaks my|mid[- ]thought|train of thought",
    "C4 상시 감시·베이비시팅": r"keep checking|constantly checking|check(ing)? on|polling|watching (it|the terminal)|keep looking|keep an eye|babysit|glance|can'?t leave|not gonna leave|stuck at my desk|at my desk|glued|chained|monitor(ing)? (it|them|the)",
    "C5 검수·재작업 부담": r"review|verif|double[- ]check|rework|clean up|fix(ing)? (its|the) mess|audit|go through (the|its) (diff|changes)",
    "C6 우회책·도구 제작": r"i built|built a|built an|so i built|wrote a script|hook|workaround|i made a|set up tmux|notification script",
    "C7 기다리며 다른 일": r"while (it|claude|codex|the agent|agents?) (runs?|works?|is working)|in the meantime|read(ing)? a book|make coffee|another (task|project|thing)|side (task|project)|second (task|project)|do something else",
  },
  "Cp": {
    "P1 지루함·붕 뜸": r"\bbored|boredom|boring|twiddl|staring into space|nothing to do|dead time|limbo|in between",
    "P2 불안·스트레스·소진": r"anxi|stress|panic|overwhelm|nervous|worr|exhaust|fatigue|burn(ed|t)? ?out|drain|tired|melting|blender",
    "P3 몰입 상실": r"\bflow\b|focus|concentrat|deep work|in the zone|attention|distract",
    "P4 역할 변화·탈숙련": r"manager|tech lead|intern|middleware|orchestrat|babysitter|my (actual )?job|barely (write|type) code|don't code anymore|useless|deskill|atrophy|losing (my )?skills|lazy|rusty|imposter|not really (coding|working)",
    "P5 좌절": r"frustrat|annoy|infuriat|hate|drives me|pain in the",
    "P6 해방감·여유": r"\brelax|relief|freed|frees|free time|go to sleep|peace|calm|less stress|while i (sleep|walk|cook)|go for a walk|make coffee",
  },
  "V": {
    "V1 생산성·성과": r"productiv|throughput|10x|100x|\bship|get more done|more work done|output|velocity",
    "V2 통제감·상황 인식": r"control|oversight|in charge|know what('s| is) (going on|happening)|visibility|on top of|situational|aware",
    "V3 유능감·크래프트": r"skill|craft|learn|understand|good at|hands[- ]on|love (writing|coding)|i love|engineer(ing)? (judgment|taste)|ownership",
    "V4 시간 자율": r"my time|free time|retire|freedom|walk away|leave|go to sleep|life|evenings?|weekends?",
    "V5 신뢰·안심": r"\btrust|reliab|confiden|peace of mind|calm|sanity|without losing my mind|less anxious|predictab",
  },
}

LRX = {lvl: {code: re.compile(rx, re.I) for code, rx in codes.items() if not rx.startswith("__")} for lvl, codes in LADDER.items()}
WAIT_CODE = {"agent": ["C1 대기·공백 시간"], "unspecified": ["C1 대기·공백 시간"], "quota": [], "both": ["C1 대기·공백 시간"], "none": []}
LRX_WAIT = re.compile(r"\bwait(ing|ed|s)?\b|idle|dead time|downtime|twiddl|staring (at|into)", re.I)
code_docs = collections.Counter(); ac = collections.Counter(); cv = collections.Counter(); cc = collections.Counter()
lad_rows = []; quotes = collections.defaultdict(list)
for d, cs in zip(ANALYSIS_DOCS, doc_concepts):
    hit = {lvl: [code for code, rx in LRX[lvl].items() if rx.search(d["text"])] for lvl in LRX}
    hit["Cf"] = WAIT_CODE[d["wait_type"]] + hit["Cf"]
    A = hit["A"]; C = hit["Cf"] + hit["Cp"]; V = hit["V"]
    for lvl in hit:
        for code in hit[lvl]:
            code_docs[code] += 1
            if len(quotes[code]) < 400: quotes[code].append(d)
    for a in A:
        for c in C: ac[(a, c)] += 1
    for cf in hit["Cf"]:
        for cp in hit["Cp"]: cc[(cf, cp)] += 1
    for c in C:
        for v in V: cv[(c, v)] += 1
    lad_rows.append(dict(source=d["source"], id=d["id"], date=d["date"], subreddit=d["subreddit"], score=d["score"],
                         A=";".join(A), C_functional=";".join(hit["Cf"]), C_psychological=";".join(hit["Cp"]), V=";".join(V),
                         ladder_complete=int(bool(A and C and V)), text=d["text"][:1500], url=d["url"]))
wr(os.path.join(OUT, "laddering_codes.csv"), lad_rows, list(lad_rows[0].keys()))
wr(os.path.join(OUT, "laddering_code_counts.csv"), [dict(code=k, docs=n, share_pct=round(100 * n / N, 2)) for k, n in sorted(code_docs.items())], ["code", "docs", "share_pct"])
def matrix(pairs, rows_, cols_, path):
    out = []
    for r in rows_:
        row = {"": r}
        for c in cols_: row[c] = pairs.get((r, c), 0)
        out.append(row)
    wr(path, out, [""] + cols_)
A_codes = list(LADDER["A"]); Cf_codes = list(LADDER["Cf"]); Cp_codes = list(LADDER["Cp"]); V_codes = list(LADDER["V"])
matrix(ac, A_codes, Cf_codes + Cp_codes, os.path.join(OUT, "implication_A_to_C.csv"))
matrix(cc, Cf_codes, Cp_codes, os.path.join(OUT, "implication_Cf_to_Cp.csv"))
matrix(cv, Cf_codes + Cp_codes, V_codes, os.path.join(OUT, "implication_C_to_V.csv"))
edges = [dict(level="A->C", source=a, target=c, docs=n) for (a, c), n in ac.items()] + \
        [dict(level="Cf->Cp", source=a, target=c, docs=n) for (a, c), n in cc.items()] + \
        [dict(level="C->V", source=a, target=c, docs=n) for (a, c), n in cv.items()]
edges.sort(key=lambda e: -e["docs"])
wr(os.path.join(OUT, "hvm_edges.csv"), edges, ["level", "source", "target", "docs"])
A2N = "A2 승인·권한 프롬프트"; A6N = "A6 자율 모드(auto-accept·YOLO)"
seg_docs = {"prompt": [], "auto": []}
for r in lad_rows:
    A = r["A"].split(";") if r["A"] else []
    if A6N in A: seg_docs["auto"].append(r)
    elif A2N in A: seg_docs["prompt"].append(r)
seg_code = {k: collections.Counter() for k in seg_docs}; seg_pairs = {k: collections.Counter() for k in seg_docs}
for k, rows_ in seg_docs.items():
    for r in rows_:
        C = [c for c in (r["C_functional"] + ";" + r["C_psychological"]).split(";") if c]; V = [v for v in r["V"].split(";") if v]
        for c in set(C + V): seg_code[k][c] += 1
        for c in C:
            for v in V: seg_pairs[k][("C->V", c, v)] += 1
        for cf in [c for c in r["C_functional"].split(";") if c]:
            for cp in [c for c in r["C_psychological"].split(";") if c]: seg_pairs[k][("Cf->Cp", cf, cp)] += 1
allc = Cf_codes + Cp_codes + V_codes
wr(os.path.join(OUT, "laddering_segments_code_share.csv"),
   [dict(code=c, prompt_docs=seg_code["prompt"][c], prompt_pct=round(100 * seg_code["prompt"][c] / max(len(seg_docs["prompt"]), 1), 1),
         auto_docs=seg_code["auto"][c], auto_pct=round(100 * seg_code["auto"][c] / max(len(seg_docs["auto"]), 1), 1)) for c in allc],
   ["code", "prompt_docs", "prompt_pct", "auto_docs", "auto_pct"])
wr(os.path.join(OUT, "hvm_edges_by_autonomy.csv"),
   sorted([dict(segment=k, level=lv, source=a, target=b, docs=n, pct=round(100 * n / max(len(seg_docs[k]), 1), 1)) for k in seg_pairs for (lv, a, b), n in seg_pairs[k].items()], key=lambda e: (e["segment"], -e["docs"])),
   ["segment", "level", "source", "target", "docs", "pct"])
print("autonomy segments: prompt", len(seg_docs["prompt"]), "docs | auto", len(seg_docs["auto"]), "docs")
complete = sum(r["ladder_complete"] for r in lad_rows)
print(f"laddering: {N} docs coded, {complete} with full A-C-V ladder; top A->C:", [(k, n) for k, n in ac.most_common(5)])

import random
sample = []
for src, k in [("reddit_post", 80), ("reddit_comment", 70)]:
    rich = [r for r in lad_rows if r["source"] == src and 150 <= len(r["text"]) <= 1500 and r["ladder_complete"] == 1]
    rest = [r for r in lad_rows if r["source"] == src and 150 <= len(r["text"]) <= 1500 and r["ladder_complete"] == 0]
    rng = random.Random(42); rng.shuffle(rich); rng.shuffle(rest)
    sample += (rich + rest)[:k]
def short(codes): return ";".join(c.split(" ")[0] for c in codes.split(";") if c)
for r in sample:
    r["auto_A"] = short(r["A"]); r["auto_C"] = short(r["C_functional"]); r["auto_P"] = short(r["C_psychological"]); r["auto_V"] = short(r["V"])
    for who in ("c1", "c2", "final"):
        for col in ("relevant", "A", "C", "P", "V"): r[f"{col}_{who}"] = ""
wr(os.path.join(OUT, "laddering_sample_for_coding.csv"), sample,
   ["source", "id", "date", "subreddit", "score", "url", "text", "auto_A", "auto_C", "auto_P", "auto_V",
    "relevant_c1", "A_c1", "C_c1", "P_c1", "V_c1", "relevant_c2", "A_c2", "C_c2", "P_c2", "V_c2", "relevant_final", "A_final", "C_final", "P_final", "V_final"])
print("coding sample:", len(sample), "docs")

def excerpt(text, rx, width=220):
    m = rx.search(text) if rx is not None else None
    if not m: return text[:width]
    s = max(0, m.start() - width // 2); return ("…" if s else "") + text[s:s + width] + ("…" if s + width < len(text) else "")
with open(os.path.join(OUT, "laddering_quotes.md"), "w", encoding="utf-8") as f:
    f.write("# 래더링 코드별 인용 후보 (자동 추출, 사람 검증용)\n\n코드별로 점수 높은 문서 6건, 매칭 지점 주변 발췌. 출처 링크 포함.\n")
    for lvl, codes in LADDER.items():
        f.write(f"\n## {lvl}\n")
        for code in codes:
            docs = quotes.get(code, [])
            docs = sorted(docs, key=lambda d: -int(float(d["score"] or 0)))[:6]
            f.write(f"\n### {code}  (n={code_docs[code]})\n")
            for d in docs:
                f.write(f"- [{d['source']} r/{d['subreddit']} {d['date']} s={d['score']}]({d['url']}) {excerpt(d['text'], LRX[lvl].get(code, LRX_WAIT))}\n")

if HAVE_MPL:
    wk = [r for r in weekly_rows if r["agent_posts"] >= 50 and r["full_week"]]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot([r["week"] for r in wk], [r["agent_friction_pct"] for r in wk], marker="o", label="friction terms (waiting/flow/supervision/resume)")
    ax.plot([r["week"] for r in wk], [r["agent_hype_pct"] for r in wk], marker="s", label="productivity / time-saving terms")
    ax.set_ylabel("% of posts in agent subreddits"); ax.set_title("Weekly share of posts: friction vs. productivity framing"); ax.legend(); ax.grid(alpha=.3)
    plt.xticks(rotation=45, ha="right"); plt.tight_layout(); plt.savefig(os.path.join(OUT, "chart_weekly_trend.png"), dpi=150); plt.close()
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot([r["week"] for r in wk], [r["agent_wait_agent_pct"] for r in wk], marker="o", label="waiting for the agent (task / permission / output)")
    ax.plot([r["week"] for r in wk], [r["agent_wait_quota_pct"] for r in wk], marker="s", label="waiting for quota / usage-limit reset")
    ax.set_ylabel("% of posts in agent subreddits"); ax.set_title("Two kinds of waiting, weekly share"); ax.legend(); ax.grid(alpha=.3)
    plt.xticks(rotation=45, ha="right"); plt.tight_layout(); plt.savefig(os.path.join(OUT, "chart_weekly_waiting.png"), dpi=150); plt.close()
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar([r["week"] for r in wk], [r["focus_posts"] for r in wk], color="#6b8fb8")
    ax2 = ax.twinx(); ax2.plot([r["week"] for r in wk], [r["focus_per_1000"] for r in wk], color="#d9534f", marker="o", label="per 1,000 posts")
    ax.set_ylabel("first-person delegation-experience posts (count)"); ax2.set_ylabel("per 1,000 agent-subreddit posts", color="#d9534f")
    ax.set_title("Weekly volume of first-person 'waiting / losing track / babysitting' posts (Reddit)"); ax.grid(alpha=.3)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right"); plt.tight_layout(); plt.savefig(os.path.join(OUT, "chart_weekly_focus.png"), dpi=150); plt.close()
    bs = [r for r in rd(os.path.join(OUT, "keyword_by_subreddit.csv")) if int(r["posts"]) >= 300]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    xs = range(len(bs)); ax.bar([i - .2 for i in xs], [float(r["friction_pct"]) for r in bs], width=.4, label="friction %")
    ax.bar([i + .2 for i in xs], [float(r["hype_pct"]) for r in bs], width=.4, label="hype %")
    ax.set_xticks(list(xs)); ax.set_xticklabels([r["subreddit"] for r in bs], rotation=45, ha="right"); ax.set_ylabel("% of posts"); ax.legend(); ax.set_title("Friction vs. productivity framing by subreddit"); plt.tight_layout()
    plt.savefig(os.path.join(OUT, "chart_by_subreddit.png"), dpi=150); plt.close()
    if HAVE_NX:
        G = nx.Graph()
        top = [k for k, n in cnt.most_common(26) if n >= 40]
        for k in top: G.add_node(k, w=cnt[k])
        jac = {}
        for (a, b), n in pair.items():
            if a in top and b in top and n >= 15:
                jac[(a, b)] = n / (cnt[a] + cnt[b] - n)
        keep = set()
        for k in top:
            ties = sorted([(j, e) for e, j in jac.items() if k in e], reverse=True)[:3]
            keep.update(e for _, e in ties)
        for (a, b) in keep: G.add_edge(a, b, w=pair[(a, b)], j=jac[(a, b)])
        pos = nx.spring_layout(G, k=1.6, seed=11, weight="j", iterations=300)
        fig, ax = plt.subplots(figsize=(12, 9.5))
        jmax = max(d["j"] for _, _, d in G.edges(data=True))
        nx.draw_networkx_edges(G, pos, width=[0.5 + 5 * G[u][v]["j"] / jmax for u, v in G.edges()], alpha=.45, edge_color="#5b7fa8", ax=ax)
        nx.draw_networkx_nodes(G, pos, node_size=[200 + 3200 * cnt[n] / max(cnt.values()) for n in G.nodes()], node_color="#bcd2ea", edgecolors="#4a6fa5", alpha=.95, ax=ax)
        nx.draw_networkx_labels(G, pos, labels={n: f"{n}\n({cnt[n]})" for n in G.nodes()}, font_size=8.5, ax=ax)
        ax.set_title(f"Concept co-occurrence backbone (first-person delegation experiences, n={N}; node = docs, edge = Jaccard, top-3 ties per node)"); ax.axis("off"); plt.tight_layout()
        plt.savefig(os.path.join(OUT, "chart_concept_network.png"), dpi=150); plt.close()
    def layered(codes_by_layer, edge_sets, path, title, cutoff_frac=0.06):
        fig, ax = plt.subplots(figsize=(16, 10))
        pos = {}; maxn = 0
        for li, (lname, codes) in enumerate(codes_by_layer):
            codes = [c for c in codes if code_docs[c] > 0]; maxn = max(maxn, len(codes))
            for ci, c in enumerate(codes):
                pos[c] = (li * 4.0, -ci * 1.0)
        for pairs in edge_sets:
            mx = max(pairs.values()) if pairs else 1
            for (a, b), n in pairs.items():
                if a in pos and b in pos and n >= cutoff_frac * mx and n >= 5:
                    ax.annotate("", xy=(pos[b][0] - 1.35, pos[b][1]), xytext=(pos[a][0] + 1.35, pos[a][1]),
                                arrowprops=dict(arrowstyle="-|>", lw=0.5 + 4 * n / mx, color="#4a6fa5", alpha=.4, shrinkA=0, shrinkB=0))
        for li, (lname, codes) in enumerate(codes_by_layer):
            codes = [c for c in codes if code_docs[c] > 0]
            for c in codes:
                ax.text(pos[c][0], pos[c][1], f"{c}\n(n={code_docs[c]})", ha="center", va="center", fontsize=7.5, zorder=5,
                        bbox=dict(boxstyle="round,pad=0.3", fc="#eef3fa", ec="#6b8fb8"))
            ax.text(li * 4.0, 1.1, lname, ha="center", fontsize=11, weight="bold")
        ax.set_xlim(-1.8, (len(codes_by_layer) - 1) * 4.0 + 1.8); ax.set_ylim(-maxn + 0.2, 1.8)
        ax.axis("off"); ax.set_title(title + "  (arrow width = number of co-occurring docs; edges below 6% of the layer max hidden)")
        plt.savefig(path, dpi=150, bbox_inches="tight"); plt.close()
    layered([("Attributes (A)", A_codes), ("Functional consequences (Cf)", Cf_codes), ("Psychological consequences (Cp)", Cp_codes), ("Values (V)", V_codes)],
            [{k: v for k, v in ac.items() if k[1] in Cf_codes}, cc, {k: v for k, v in cv.items() if k[0] in Cp_codes}],
            os.path.join(OUT, "chart_hvm.png"), f"Hierarchical Value Map draft (auto-coded, n={N}, edges = co-occurring docs)")
print("charts:", "ok" if HAVE_MPL else "skipped (matplotlib missing)")
print("outputs in", OUT)
