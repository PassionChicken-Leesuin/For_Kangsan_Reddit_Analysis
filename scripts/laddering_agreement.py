#!/usr/bin/env python3
"""Inter-coder agreement + human-coded HVM from laddering_sample_for_coding.csv.
usage: laddering_agreement.py <project_dir>  (needs *_c1 / *_c2 filled; *_final optional)"""
import csv, os, sys, collections, itertools
ROOT = sys.argv[1]; A = os.path.join(ROOT, "analysis")
csv.field_size_limit(10**9)
rows = list(csv.DictReader(open(os.path.join(A, "laddering_sample_for_coding.csv"), encoding="utf-8-sig")))
def codes(v): return {c.strip().upper() for c in (v or "").replace(",", ";").split(";") if c.strip()}
LEVELS = ["A", "C", "P", "V"]
coded = [r for r in rows if (r.get("relevant_c1") or "").strip() != "" and (r.get("relevant_c2") or "").strip() != ""]
print(f"docs coded by both: {len(coded)} / {len(rows)}")
if not coded: sys.exit("fill relevant_c1/relevant_c2 first")

def kappa(pairs):
    n = len(pairs); po = sum(1 for x, y in pairs if x == y) / n
    p1 = sum(x for x, _ in pairs) / n; p2 = sum(y for _, y in pairs) / n
    pe = p1 * p2 + (1 - p1) * (1 - p2)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0, po
out = []
k, po = kappa([(int(r["relevant_c1"]), int(r["relevant_c2"])) for r in coded])
out.append(dict(level="relevant", code="(전체)", n=len(coded), agreement=round(po, 3), kappa=round(k, 3)))
both_rel = [r for r in coded if r["relevant_c1"].strip() == "1" and r["relevant_c2"].strip() == "1"]
for lvl in LEVELS:
    allc = sorted(set().union(*[codes(r[f"{lvl}_c1"]) | codes(r[f"{lvl}_c2"]) for r in both_rel]))
    jac = [len(codes(r[f"{lvl}_c1"]) & codes(r[f"{lvl}_c2"])) / max(len(codes(r[f"{lvl}_c1"]) | codes(r[f"{lvl}_c2"])), 1) for r in both_rel]
    ks = []
    for c in allc:
        k, po = kappa([(int(c in codes(r[f"{lvl}_c1"])), int(c in codes(r[f"{lvl}_c2"]))) for r in both_rel])
        ks.append(k); out.append(dict(level=lvl, code=c, n=len(both_rel), agreement=round(po, 3), kappa=round(k, 3)))
    out.append(dict(level=lvl, code="(평균)", n=len(both_rel), agreement=round(sum(jac) / max(len(jac), 1), 3), kappa=round(sum(ks) / max(len(ks), 1), 3)))
with open(os.path.join(A, "laddering_agreement.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=["level", "code", "n", "agreement", "kappa"]); w.writeheader(); w.writerows(out)
for r in out:
    if r["code"].startswith("("): print(f"{r['level']:9s} {r['code']:8s} n={r['n']:3d} agreement={r['agreement']}  kappa={r['kappa']}")
print("-> laddering_agreement.csv (코드별 카파 포함). 카파 0.6 미만 코드는 정의를 다시 논의할 것.")

final = [r for r in rows if (r.get("relevant_final") or "").strip() == "1"]
if final:
    cnt = collections.Counter(); ac = collections.Counter(); cp = collections.Counter(); cv = collections.Counter()
    for r in final:
        Ac, Cc, Pc, Vc = (codes(r[f"{l}_final"]) for l in LEVELS)
        for c in Ac | Cc | Pc | Vc: cnt[c] += 1
        for a in Ac:
            for c in Cc | Pc: ac[(a, c)] += 1
        for c in Cc:
            for p in Pc: cp[(c, p)] += 1
        for c in Cc | Pc:
            for v in Vc: cv[(c, v)] += 1
    edges = [dict(level=lv, source=a, target=b, docs=n) for lv, d in [("A->C", ac), ("Cf->Cp", cp), ("C->V", cv)] for (a, b), n in d.items() if n >= 5]
    edges.sort(key=lambda e: -e["docs"])
    with open(os.path.join(A, "hvm_human_edges.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["level", "source", "target", "docs"]); w.writeheader(); w.writerows(edges)
    with open(os.path.join(A, "hvm_human_code_counts.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["code", "docs"]); w.writeheader(); w.writerows([dict(code=c, docs=n) for c, n in sorted(cnt.items())])
    print(f"human HVM: {len(final)} relevant docs, {len(edges)} edges with >=5 docs -> hvm_human_edges.csv")
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        from matplotlib import font_manager as fm
        plt.rcParams["font.family"] = next((f for f in ["Apple SD Gothic Neo", "Malgun Gothic", "NanumGothic", "Noto Sans CJK KR"] if f in {x.name for x in fm.fontManager.ttflist}), "DejaVu Sans")
        layers = [("속성 (A)", sorted(c for c in cnt if c.startswith("A"))), ("기능적 결과 (C)", sorted(c for c in cnt if c.startswith("C"))), ("심리적 결과 (P)", sorted(c for c in cnt if c.startswith("P"))), ("가치 (V)", sorted(c for c in cnt if c.startswith("V")))]
        pos = {}; fig, ax = plt.subplots(figsize=(13, 8))
        for li, (name, cs) in enumerate(layers):
            for ci, c in enumerate(cs): pos[c] = (li * 3.0, -ci)
            ax.text(li * 3.0, 1.1, name, ha="center", fontsize=11, weight="bold")
        mx = max((e["docs"] for e in edges), default=1)
        for e in edges:
            a, b = e["source"], e["target"]
            if a in pos and b in pos:
                ax.annotate("", xy=(pos[b][0] - .7, pos[b][1]), xytext=(pos[a][0] + .7, pos[a][1]), arrowprops=dict(arrowstyle="-|>", lw=0.5 + 4 * e["docs"] / mx, color="#4a6fa5", alpha=.5))
        for c, (x, y) in pos.items(): ax.text(x, y, f"{c}\n(n={cnt[c]})", ha="center", va="center", fontsize=8, zorder=5, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#55657a"))
        ax.set_xlim(-1.2, 10.2); ax.set_ylim(-max(len(cs) for _, cs in layers) + .2, 1.8); ax.axis("off")
        ax.set_title(f"가치계층도 (사람 코딩, relevant {len(final)}건, 연결 5건 이상)"); plt.tight_layout()
        os.makedirs(os.path.join(A, "report_figures"), exist_ok=True); plt.savefig(os.path.join(A, "report_figures", "fig3_hvm_human.png"), dpi=200); print("-> report_figures/fig3_hvm_human.png")
    except Exception as e:
        print("chart skipped:", e)
else:
    print("(*_final 열이 비어 있어 사람 코딩 HVM은 건너뜀)")
