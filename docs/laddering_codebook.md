# 래더링 코드북 v1 (2026-10-20 확정)

## 0. 결정 사항 (추천안 그대로 확정)

| # | 항목 | 결정 |
|---|---|---|
| 1 | 분석 단위 | 게시글·댓글 1건 = 응답자 1명의 래더. 긴 글은 사다리 여러 개 허용(코드를 복수 기입) |
| 2 | 포함 기준 | 코딩·업무 에이전트에 일을 **맡긴 1인칭 경험** 서술만 relevant=1. 트레이딩·크립토 봇, 쿼타 불만만 있는 글, 제품 홍보만 있는 글(고통 서술 없음)은 relevant=0 |
| 3 | 코드북 | 속성 7 · 기능적 결과 7 · 심리적 결과 6 · 가치 5 (아래) |
| 4 | 코더·규모 | 샘플 150건, 코더 2명 독립 코딩 → `laddering_agreement.py`로 일치도 확인 → 불일치 합의 → final 열 |
| 5 | HVM cutoff | 사람 코딩: 연결 5건 이상. 자동 코딩: 층별 최대값의 6% 이상 |
| 6 | 자율성 분할 | '승인 프롬프트' 언급 글 vs '자율 모드(auto-accept·YOLO)' 언급 글의 HVM을 따로 그려 비교 |
| 7 | 가치 틀 | 연구 맞춤 5개 (생산성, 통제감, 유능감, 시간 자율, 신뢰·안심) |
| 8 | 인용 원칙 | 사용자명 제외, (플랫폼 커뮤니티, 연-월)만 표기. 영어 원문 + 한국어 번역 병기 |

## 1. 코딩 방법

- 파일: `analysis/laddering_sample_for_coding.csv` (150건 = Reddit 게시글 80, 댓글 70. A-C-V가 모두 잡힌 글을 우선으로 고정 시드 무작위 추출).
- `auto_*` 열은 자동 코딩 제안값이다. **보고 참고만 하고, 본인 판단으로 `*_c1`(코더1) 또는 `*_c2`(코더2) 열에 기입**한다.
- 기입 형식: 코드 번호를 세미콜론으로 구분. 예) `A2;A4` / `C1;C4` / `P4` / `V3`. 해당 없음은 빈칸.
- `relevant_c1/_c2`: 포함 기준 충족 시 1, 아니면 0. 0이면 나머지 열은 비워도 된다.
- 한 글에서 **명시적으로 서술된 것만** 코딩한다. 추론하지 않는다. ("기다리는 동안 유튜브 본다" → C7, P1은 '지루하다'고 썼을 때만.)
- 홍보성 글(내가 만든 도구 소개)은 **왜 만들었는지 서술된 고통**을 코딩하고 제품 설명은 무시한다. 고통 서술이 없으면 relevant=0.
- 쿼타·사용량 제한 리셋을 기다리는 것은 C1이 아니다(연구 범위 밖). 에이전트의 작업·승인·출력을 기다리는 것만 C1.
- 두 코더가 끝나면 `python3 scripts/laddering_agreement.py .` 실행 → 일치도 표 확인 → 불일치 건을 함께 보고 `*_final` 열 확정 → 같은 스크립트가 함축매트릭스·HVM을 만든다.

## 2. 코드 정의

### A. 속성 — 에이전트·워크플로의 특성 (무엇이 그렇게 만들었나)

| 코드 | 정의 | 포함 신호 | 구분 규칙 |
|---|---|---|---|
| **A1 장시간 자율 실행** | 에이전트가 수 분~수 시간 스스로 돌아감 | "while it runs", "ran for 2 hours", background, overnight, long-running | 실행 길이·백그라운드성이 언급될 때. 단순 "I used Claude"는 아님 |
| **A2 승인·권한 프롬프트** | 도구 실행·파일 수정 전 승인을 요구함 | permission prompt, approve, allow, confirm each | 승인이라는 **행위**가 언급될 때 |
| **A3 질문·개입 요청** | 에이전트가 질문하거나 사람의 입력을 요구함 | asks me, needs my input, waiting on me, clarification | A2와 겹치면 둘 다 기입 가능 |
| **A4 병렬 다중 세션** | 세션·에이전트·터미널을 여러 개 동시에 돌림 | 3 sessions, in parallel, multiple agents, worktrees | 숫자나 '동시에'가 있어야 함 |
| **A5 알림·상태 가시성** | 알림·상태 표시·대시보드의 유무 | notification, bell, badge, status, dashboard | 가시성이 **없어서** 생긴 문제도 A5 |
| **A6 자율 모드(auto-accept·YOLO)** | 승인을 끄고 전면 자율로 돌림 | yolo, auto-accept, skip permissions, hands-off, unattended | 자율성 **높은** 조건. 분할 분석의 기준 |
| **A7 에이전트 신뢰성(속도·문맥 손실·탈선)** | 너무 빠름/느림, 문맥 잊음, 엉뚱한 방향 | too fast, forgets context, compaction, off the rails | 결과물 품질 불만 일반은 아님. 위임 중 **행동 특성**일 때 |

### C. 기능적 결과 — 실제로 일어나는 일

| 코드 | 정의 | 포함 신호 | 구분 규칙 |
|---|---|---|---|
| **C1 대기·공백 시간** | 에이전트의 작업·승인·출력을 기다리는 시간이 생김 | waiting for it, idle, dead time, staring at the terminal | 쿼타 리셋 대기는 제외 |
| **C2 놓침·재구성** | 어느 세션이 뭘 하는지 놓치고 다시 파악해야 함 | lose track, which one was waiting, reconstruct, where I left off | 복귀 비용의 핵심 |
| **C3 문맥 전환·내 작업 중단** | 과업 사이를 오가거나 내 작업이 끊김 | context switch, alt-tab, interrupts me, mid-thought | C2(상태 파악)와 구분: C3은 **전환 행위·중단** |
| **C4 상시 감시·베이비시팅** | 계속 확인하고 지켜봐야 함, 자리를 못 뜸 | keep checking, babysit, watching the terminal, can't leave my desk | |
| **C5 검수·재작업 부담** | 결과를 검토·수정·되돌리는 일이 늘어남 | review, verify, rework, clean up its mess | 자율성 높을 때 커지는 결과 |
| **C6 우회책·도구 제작** | 문제를 피하려고 스크립트·훅·앱을 만듦 | I built, hook, workaround, set up tmux | 홍보 글의 '만든 이유'는 여기 |
| **C7 기다리며 다른 일** | 기다리는 동안 다른 과업·활동을 함 | in the meantime, read a book, another project, make coffee | 실제로 했을 때. '못 한다'는 C4 |

### P. 심리적 결과 — 느끼는 것

| 코드 | 정의 | 포함 신호 |
|---|---|---|
| **P1 지루함·붕 뜸** | 할 일 없이 떠 있는 느낌 | bored, nothing to do, limbo, twiddling |
| **P2 불안·스트레스·소진** | 불안·초조·압도·지침 | anxious, stressed, overwhelmed, exhausted, burned out |
| **P3 몰입 상실** | 집중·흐름이 깨짐 | flow, focus, distracted, can't concentrate |
| **P4 역할 변화·탈숙련** | 개발자→관리자·베이비시터, 쓸모없어진 느낌, 기술 퇴화 | manager, intern, babysitter, barely write code, useless, atrophy |
| **P5 좌절** | 짜증·분노 | frustrating, annoying, infuriating |
| **P6 해방감·여유** | 놓여난 느낌, 쉼 | relief, relaxed, free time, go to sleep |

### V. 가치 — 궁극적으로 추구하는 것

| 코드 | 정의 | 포함 신호 |
|---|---|---|
| **V1 생산성·성과** | 더 많이·빨리 해내기 | productivity, throughput, ship, 10x |
| **V2 통제감·상황 인식** | 무슨 일이 벌어지는지 알고 쥐고 있기 | control, oversight, know what's going on, visibility |
| **V3 유능감·크래프트** | 내가 잘하는 사람이고 싶음, 만드는 즐거움, 배움 | skill, craft, I love coding, learn, ownership |
| **V4 시간 자율** | 내 시간을 내가 쓰기 | my time, walk away, evenings, life |
| **V5 신뢰·안심** | 믿고 맡길 수 있음, 마음 놓임 | trust, reliable, peace of mind, sanity |

## 3. 자주 헷갈리는 경우

- "I built a dashboard because I kept losing track of 5 sessions" → A4, A5(가시성 부재), C2, C6. 감정 서술 없으면 P는 빈칸. 가치는 "so I know what's going on" 같은 말이 있을 때만 V2.
- "I just approve everything now, then spend an hour reviewing the diff" → A6, C5. (A2는 승인 **행위**가 부담일 때. 여기서는 끈 상태이므로 A6.)
- "Waiting for the 5-hour limit to reset is killing me" → relevant=0 (쿼타 대기만).
- "While Codex runs I read papers, honestly it's the best part of my day" → A1, C7, P6, V4.
- 트레이딩 봇을 "agent"라 부르는 글 → relevant=0.
