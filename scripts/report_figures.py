#!/usr/bin/env python3
"""Report-ready figures (Korean labels) from analysis CSVs. usage: report_figures.py <project_dir>"""
import csv, json, os, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
KFONT = next((f for f in ["Apple SD Gothic Neo", "Malgun Gothic", "NanumGothic", "Noto Sans CJK KR"] if f in {x.name for x in fm.fontManager.ttflist}), "DejaVu Sans")
plt.rcParams["font.family"] = KFONT; plt.rcParams["axes.unicode_minus"] = False
ROOT = sys.argv[1]; A = os.path.join(ROOT, "analysis"); FIG = os.path.join(A, "report_figures"); os.makedirs(FIG, exist_ok=True)
def rd(p): return list(csv.DictReader(open(p, encoding="utf-8-sig")))
BLUE, ORANGE, GREEN, GRAY = "#2f5d9a", "#d9822b", "#3a8f5c", "#777777"
agent_subs = set(json.load(open(os.path.join(ROOT, "scripts", "keywords.json"), encoding="utf-8"))["agent_subs"])

wk = [r for r in rd(os.path.join(A, "keyword_weekly.csv")) if r["full_week"] == "1"]
x = [r["week"][5:] for r in wk]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.6))
a1.plot(x, [float(r["agent_hype_pct"]) for r in wk], marker="s", color=ORANGE, label="생산성·시간 절약 프레임")
a1.plot(x, [float(r["agent_friction_pct"]) for r in wk], marker="o", color=BLUE, label="마찰 프레임 (대기·몰입·감독·복귀)")
a1.set_title(f"(a) 담론 프레임 비율 (에이전트 커뮤니티 {len(agent_subs)}곳)"); a1.set_ylabel("주간 게시글 중 %"); a1.grid(alpha=.3); a1.legend(fontsize=8)
a2.plot(x, [float(r["agent_wait_quota_pct"]) for r in wk], marker="s", color=GRAY, label="쿼타 대기 (사용량 제한 리셋)")
a2.plot(x, [float(r["agent_wait_agent_pct"]) for r in wk], marker="o", color=BLUE, label="에이전트 대기 (작업·승인·출력)")
a2.set_title("(b) 두 종류의 기다림"); a2.set_ylabel("주간 게시글 중 %"); a2.grid(alpha=.3); a2.legend(fontsize=8)
for a in (a1, a2): plt.setp(a.get_xticklabels(), rotation=45, ha="right", fontsize=8); a.set_xlabel("주 (2026, 월요일 기준)", fontsize=8)
plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig4_weekly.png"), dpi=200); plt.close()

bs = [r for r in rd(os.path.join(A, "keyword_by_subreddit.csv")) if int(r["posts"]) >= 800]
bs.sort(key=lambda r: (r["subreddit"] not in agent_subs, -float(r["friction_pct"])))
fig, ax = plt.subplots(figsize=(10, 3.6)); xs = range(len(bs))
ax.bar([i - .2 for i in xs], [float(r["friction_pct"]) for r in bs], width=.4, color=BLUE, label="마찰 프레임 (대기·몰입·감독·복귀)")
ax.bar([i + .2 for i in xs], [float(r["hype_pct"]) for r in bs], width=.4, color=ORANGE, label="생산성·시간 절약 프레임")
ax.set_xticks(list(xs)); ax.set_xticklabels([("r/" + r["subreddit"]) for r in bs], rotation=35, ha="right", fontsize=8)
n_agent = sum(1 for r in bs if r["subreddit"] in agent_subs)
ax.axvline(n_agent - .5, color=GRAY, ls="--", lw=1); ax.text(n_agent - .6, ax.get_ylim()[1] * .95 if ax.get_ylim()[1] > 0 else 9, "에이전트 도구 커뮤니티 ←  → 일반 개발 커뮤니티", ha="center", fontsize=8, color=GRAY)
ax.set_ylabel("게시글 중 %"); ax.legend(fontsize=8); ax.grid(axis="y", alpha=.3); plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig2_by_subreddit.png"), dpi=200); plt.close()

import networkx as nx
nodes = rd(os.path.join(A, "cooccurrence_nodes.csv")); edges = rd(os.path.join(A, "cooccurrence_edges.csv"))
KO = {"waiting (agent)": "에이전트 대기", "waiting (quota)": "쿼타 대기", "bored/idle": "지루함·붕 뜸", "permission/approval": "승인 프롬프트", "babysitting": "베이비시팅", "interruption": "중단", "parallel sessions": "병렬 세션", "losing track": "놓침·재구성", "context switching": "문맥 전환", "focus/flow": "몰입·집중", "constant checking": "상시 확인", "notification": "알림", "built a tool": "도구 직접 제작", "anxiety/stress": "불안·스트레스", "exhaustion": "소진", "frustration": "좌절", "role shift": "역할 변화(관리자)", "deskilling": "탈숙련", "autonomy/hands-off": "자율·방임 모드", "speed": "속도", "review burden": "검수 부담", "productivity": "생산성", "usage limits": "사용량 제한", "trust": "신뢰", "context loss (agent)": "에이전트 문맥 손실", "relief/freedom": "해방감", "tethered to desk": "책상에 묶임", "multitasking": "멀티태스킹", "adhd": "ADHD"}
cnt = {r["concept"]: int(r["docs"]) for r in nodes}
top = [r["concept"] for r in nodes if int(r["docs"]) >= 40][:24]
jac = {(e["source"], e["target"]): float(e["jaccard"]) for e in edges if e["source"] in top and e["target"] in top and int(e["docs"]) >= 15}
keep = set()
for k in top:
    ties = sorted([(j, e) for e, j in jac.items() if k in e], reverse=True)[:3]; keep.update(e for _, e in ties)
G = nx.Graph()
for k in top: G.add_node(k)
for (a, b) in keep: G.add_edge(a, b, j=jac[(a, b)])
pos = nx.spring_layout(G, k=1.7, seed=11, weight="j", iterations=400)
TRACK = {"parallel sessions", "losing track", "context switching", "notification", "built a tool", "constant checking", "focus/flow"}
SUPER = {"permission/approval", "babysitting", "role shift", "review burden", "trust", "autonomy/hands-off", "interruption"}
col = ["#9ec3e6" if n in TRACK else "#f3c08b" if n in SUPER else "#bfd8c2" if n in ("waiting (agent)", "bored/idle", "relief/freedom") else "#dddddd" for n in G.nodes()]
fig, ax = plt.subplots(figsize=(10.5, 8))
jmax = max(d["j"] for _, _, d in G.edges(data=True))
nx.draw_networkx_edges(G, pos, width=[0.5 + 5 * G[u][v]["j"] / jmax for u, v in G.edges()], alpha=.45, edge_color="#6b7f99", ax=ax)
nx.draw_networkx_nodes(G, pos, node_size=[250 + 3000 * cnt[n] / max(cnt[k] for k in top) for n in G.nodes()], node_color=col, edgecolors="#55657a", alpha=.95, ax=ax)
nx.draw_networkx_labels(G, pos, labels={n: f"{KO.get(n, n)}\n({cnt[n]})" for n in G.nodes()}, font_size=8.5, font_family=KFONT, ax=ax)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color="#9ec3e6", label="추적·가시성 군집"), Patch(color="#f3c08b", label="감독·역할 군집"), Patch(color="#bfd8c2", label="기다림·공백"), Patch(color="#dddddd", label="기타")], loc="lower left", fontsize=8)
ax.set_title(f"1인칭 위임 경험 {sum(1 for _ in rd(os.path.join(A, 'corpus.csv')) if _['focus']=='1'):,}건의 개념 동시출현 (노드 = 문서 수, 선 = Jaccard 유사도, 노드당 상위 3개 연결)", fontsize=10)
ax.axis("off"); plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig1_network.png"), dpi=200); plt.close()

hv = {(r["source"], r["target"]): int(r["docs"]) for r in rd(os.path.join(A, "hvm_edges.csv"))}
cc = {r["code"]: int(r["docs"]) for r in rd(os.path.join(A, "laddering_code_counts.csv"))}
def code(prefix): return next(k for k in cc if k.startswith(prefix + " "))
LBL = {k.split(" ")[0]: " ".join(k.split(" ")[1:]) for k in cc}
BANDS = [
    ("사다리 1 · 감독 부담", BLUE, ["A2", "A3"], ["C4", "C1"], ["P4", "P5"], ["V3"]),
    ("사다리 2 · 복귀 비용", ORANGE, ["A4"], ["C2", "C3"], ["P3", "P2"], ["V2"]),
    ("사다리 3 · 공백의 질", GREEN, ["A1", "A5"], ["C1", "C7"], ["P1", "P6"], ["V4"]),
]
fig, ax = plt.subplots(figsize=(12, 8.2))
XS = [0, 1, 2, 3]; band_h = 2.6
for bi, (name, color, *layers) in enumerate(BANDS):
    y0 = -bi * band_h
    pos = {}
    for li, codes in enumerate(layers):
        ys = [y0 + 0.5] if len(codes) == 1 else [y0 + 1.0, y0 + 0.0]
        for c, y in zip(codes, ys): pos[c] = (XS[li], y)
    pairs = [(a, b) for li in range(3) for a in layers[li] for b in layers[li + 1]]
    mx_band = max(hv.get((code(a), code(b)), 0) for a, b in pairs)
    for a, b in pairs:
        n = hv.get((code(a), code(b)), 0)
        if n < 5: continue
        (x1, y1), (x2, y2) = pos[a], pos[b]
        ax.annotate("", xy=(x2 - .40, y2), xytext=(x1 + .40, y1), arrowprops=dict(arrowstyle="-|>", lw=0.6 + 4.5 * n / mx_band, color=color, alpha=.5, shrinkA=0, shrinkB=0))
        ax.text(x1 + .40 + (x2 - x1 - .80) * 0.5, (y1 + y2) / 2 + (0.09 if y1 >= y2 else -0.16), str(n), fontsize=7, color=color, ha="center", alpha=.95)
    for c, (x, y) in pos.items():
        ax.text(x, y, f"{LBL[c]}\n(n={cc[code(c)]})", ha="center", va="center", fontsize=8.5, zorder=5, bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=color, lw=1.3))
    ax.text(-0.62, y0 + 0.5, name, ha="right", va="center", fontsize=9.5, weight="bold", color=color)
    if bi < len(BANDS) - 1: ax.axhline(y0 - band_h / 2 + 0.3, color="#dddddd", lw=0.8, xmin=0.0, xmax=1.0)
for x, t in [(0, "속성 (A)\n에이전트의 특성"), (1, "기능적 결과 (C)\n실제로 일어나는 일"), (2, "심리적 결과 (C)\n느끼는 것"), (3, "가치 (V)\n추구하는 것")]:
    ax.text(x, 2.1, t, ha="center", va="center", fontsize=10, weight="bold")
ax.set_xlim(-1.9, 3.6); ax.set_ylim(-2 * band_h - 0.8, 2.7); ax.axis("off")
ax.set_title("가치계층도(HVM) 초안: 1인칭 위임 경험에서 나타난 지배적 사다리 3개\n(선 두께·숫자 = 두 코드가 함께 나타난 문서 수; '대기·공백 시간'은 사다리 1과 3에 모두 속함; 자동 코딩, 검증 전)", fontsize=9.5)
plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig3_hvm_clean.png"), dpi=200); plt.close()

seg = rd(os.path.join(A, "laddering_segments_code_share.csv"))
lad = rd(os.path.join(A, "laddering_codes.csv"))
A2N, A6N = "A2 승인·권한 프롬프트", "A6 자율 모드(auto-accept·YOLO)"
n_auto = sum(1 for r in lad if A6N in r["A"].split(";")); n_prompt = sum(1 for r in lad if A2N in r["A"].split(";") and A6N not in r["A"].split(";"))
fig, ax = plt.subplots(figsize=(10, 6.2))
labels = [r["code"] for r in seg]; ys = range(len(labels))
ax.barh([y + .2 for y in ys], [float(r["prompt_pct"]) for r in seg], height=.4, color=BLUE, label=f"승인 프롬프트 언급 (낮은 자율성, n={n_prompt})")
ax.barh([y - .2 for y in ys], [float(r["auto_pct"]) for r in seg], height=.4, color=ORANGE, label=f"자율 모드(auto-accept·YOLO) 언급 (높은 자율성, n={n_auto})")
ax.set_yticks(list(ys)); ax.set_yticklabels(labels, fontsize=8.5); ax.invert_yaxis()
for i in (7, 13): ax.axhline(i - .5, color="#cccccc", lw=.8)
ax.text(ax.get_xlim()[1] * .98, 6.5 - .3, "기능적 결과 ↑ / 심리적 결과 ↓", ha="right", fontsize=7.5, color=GRAY); ax.text(ax.get_xlim()[1] * .98, 12.5 - .3, "심리적 결과 ↑ / 가치 ↓", ha="right", fontsize=7.5, color=GRAY)
ax.set_xlabel("해당 코드가 나타난 문서 비율 (%)"); ax.grid(axis="x", alpha=.3); ax.legend(fontsize=8, loc="lower right")
ax.set_title("자율성 수준별 결과·가치 코드 비율 (1인칭 위임 경험, 자동 코딩)", fontsize=10)
plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig5_autonomy_segments.png"), dpi=200); plt.close()
print("figures written to", FIG)
