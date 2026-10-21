# Reddit 크롤링 · 분석 코드

AI 코딩 에이전트(Claude Code, Codex, Cursor 등)에 일을 맡긴 사용자의 경험을 Reddit에서 수집하고, 키워드 분석 · 개념 동시출현 연결망 · 래더링(A-C-V) 분석을 하는 코드입니다.

- 수집은 [Arctic Shift](https://arctic-shift.photon-reddit.com) 공개 API를 씁니다. Reddit API 키나 로그인이 필요 없습니다.
- 데이터 파일은 레포에 없습니다. 아래 순서대로 실행하면 `data/`와 `analysis/`가 생깁니다.

## 설치

Python 3.9 이상.

```bash
pip install -r requirements.txt
```

## 실행 순서

레포 루트에서 실행합니다.

```bash
# 1. 서브레딧별 게시글 전체 수집 (중간에 끊겨도 다시 실행하면 이어서 받음)
python3 scripts/reddit_arctic.py posts --data data/reddit \
  --subs ClaudeAI,ClaudeCode,codex,cursor,vibecoding,AI_Agents,GithubCopilot,ChatGPTCoding \
  --after 2026-07-20 --before 2026-10-20

# 2. 키워드 필터 -> data/reddit/posts_all.csv, posts_filtered.csv
python3 scripts/reddit_arctic.py filter --data data/reddit

# 3. 키워드 그룹이 2개 이상 걸린 게시글의 댓글 트리 수집 -> comments.csv, comments_filtered.csv
python3 scripts/reddit_arctic.py comments --data data/reddit --min-core 2

# 4. 분석 -> analysis/
python3 scripts/analyze.py .

# 5. 보고서용 그림(한국어 라벨) -> analysis/report_figures/
python3 scripts/report_figures.py .

# 6. (사람 코딩 후) 코더 간 일치도와 사람 코딩 HVM
python3 scripts/laddering_agreement.py .
```

참고로 저는 위 8개에 더해 `OpenAI, cscareerquestions, ExperiencedDevs, webdev, programming`까지 13개 서브레딧을 3개월 동안 수집했습니다. 게시글 약 13만 건이었고, 무료 서비스라 요청 간격(기본 1.2초)을 두기 때문에 몇 시간 걸립니다. 처음에는 서브레딧 하나, 기간 1~2주로 돌려 보세요.

## 파일

| 파일 | 하는 일 |
|---|---|
| `scripts/reddit_arctic.py` | 수집기. 모드: `posts`(게시글), `filter`(키워드 필터), `comments`(댓글 트리), `export-comments`(댓글 CSV 재생성), `comments-by-date`(서브레딧 댓글 전체) |
| `scripts/keywords.json` | 키워드 사전 |
| `scripts/analyze.py` | 코퍼스 구성, 키워드 추이, 개념 동시출현, 래더링 자동 코딩, 사람 코딩용 표본, 차트 |
| `scripts/report_figures.py` | `analysis/`의 CSV로 보고서용 그림 5장 생성 |
| `scripts/laddering_agreement.py` | 사람 코딩 표본의 코더 간 카파, 사람 코딩 기준 HVM |
| `docs/laddering_codebook.md` | 래더링 코드북(속성 7 · 기능적 결과 7 · 심리적 결과 6 · 가치 5)과 코딩 규칙 |

## 키워드 사전 (`keywords.json`)

- `groups`: 5개 키워드 그룹(`waiting_idle`, `flow_attention`, `supervision_intervention`, `resume_return`, `affect_identity`). 소문자 부분 문자열로 매칭하고, 하나라도 걸리면 1차 필터를 통과합니다.
- `agent_subs`: 에이전트 도구 서브레딧. 여기에 없는 일반 서브레딧 글은 `agentic_context` 단어가 함께 있어야 통과합니다.
- `core_groups`: `affect_identity`를 뺀 4개 그룹 중 몇 개가 걸렸는지입니다. 감정 단어는 너무 일반적이라 따로 셉니다.

## 분석 산출물 (`analysis/`)

- `corpus.csv`: 핵심 그룹이 1개 이상 걸린 게시글 · 댓글. `focus=1`은 1인칭 + 에이전트 도구 언급 + 대기 · 놓침 · 몰입 신호가 모두 있는 글로, 연결망과 래더링은 이 집합으로 합니다. `wait_type`은 에이전트 대기(`agent`)와 사용량 제한 대기(`quota`)를 구분합니다.
- 키워드: `keyword_weekly.csv`(주간 마찰 · 생산성 프레임 비율, `full_week=0`은 수집 기간 끝의 덜 찬 주), `keyword_by_subreddit.csv`, `keyword_terms.csv`
- 연결망: `cooccurrence_nodes.csv`, `cooccurrence_edges.csv`(문서 수, PMI, Jaccard)
- 래더링: `laddering_codes.csv`(문서별 A/C/V 코드), `laddering_code_counts.csv`, `implication_*.csv`(함축 매트릭스), `hvm_edges.csv`, 자율성 수준별 분할(`laddering_segments_code_share.csv`, `hvm_edges_by_autonomy.csv`), `laddering_quotes.md`(코드별 인용 후보)
- 사람 코딩: `laddering_sample_for_coding.csv`(150건). `*_c1`, `*_c2`에 코더가 각자 코드를 적고 `*_final`에 합의 결과를 적습니다. 방법은 코드북 참고.

## 주의

- 래더링 코드는 정규식 기반 **자동 코딩**이라 그대로 결과로 쓰기보다는 사람 코딩의 출발점으로 보는 게 맞습니다.
- `analyze.py`의 개념 · 래더링 정규식과 `report_figures.py`의 사다리 구성은 제 연구 주제(에이전트 위임 중 대기 · 감독 · 복귀)에 맞춘 것입니다. 주제가 다르면 이 부분을 바꿔야 합니다.
- 수집한 데이터에는 Reddit 사용자명과 본문이 들어 있습니다. 공유하거나 인용할 때는 사용자명을 빼 주세요.
