# 자연어 추천 AI 서버 완성 — 작업 계획

| | |
|---|---|
| 작성 | 2026-09-15 |
| 목표 | **AI 서버를 서비스에 쓸 수 있는 상태로 만든다** |
| 담당 | 김용석 (AI) |
| 저장소 | 팀 `C:\Users\SSAFY\Desktop\S15P21E203` 의 **`ai/` 만** · 개인 `C:\Users\SSAFY\Desktop\hyanghae` 는 자유 |

---

## 0. 지금 무엇이 되고 무엇이 안 되나

```
사용자 문장   "빨래 냄새 나는 향수 찾고 있어"
   ↓  ①  LLM 이 문장에서 향 표현을 뽑는다          ← ✗ 없다. 이번 작업의 핵심
   ↓  ②  사전이 그 표현을 향 특성으로 바꾼다        ← ✓ 된다 (사전 v1.8, 53행)
   ↓  ③  그 특성을 가진 향수를 129,161개에서 찾는다  ← ✓ 된다
   ↓  ④  세기 순으로 5개를 고른다                  ← ✓ 된다
결과   향수 5개 + 근거                             ← ✓ 된다
   ↓  ⑤  사전이 못 받은 표현을 LLM 이 추측한다      ← ✗ 자리만 있다 (estimator=)
   ↓  ⑥  못 받은 표현을 로그에 남긴다               ← ✓ 된다
```

**①이 없어서 지금은 사전 글자 맞추기만 씁니다.**

| | LLM 없음 (현재) | LLM 있음 |
|---|---:|---:|
| 문장을 알아듣는 비율 | **75.5%** | 86.7% |

합성 평가셋 600문장 기준입니다. **실사용자 설문 155건에서는 48.4%가 조건 0개**라
실제로는 더 나쁩니다.

---

## 1. 이미 확보된 것 — 새로 만들지 마십시오

**①단계 프롬프트가 이미 있고 755회 측정까지 끝났습니다.** 설계부터 하면 시간을 버립니다.

| | 값 |
|---|---|
| 프롬프트 | `EDA/analysis_outputs/15_stage1_llm_prompt_v1.txt` (28줄) |
| 모델 | `gpt-5.4-nano` |
| 엔드포인트 | `https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions` |
| 인증 | `Authorization: Bearer $GMS_KEY` — **환경변수. 코드에 적지 마십시오** |
| 호출 예시 | `EDA/15_stage1_llm_evaluation.ipynb` 의 `call_gms()` |
| 지연 실측 | 중앙 **1.47초** · p90 1.85 · 최대 3.02 (755회) |
| 토큰 실측 | 입력 중앙 640 · 출력 중앙 110 |

**출력 형태가 엔진이 그대로 받는 모양입니다.**

```json
{"scent_preference": ["white flowers", "woody"],
 "context": {"season": [], "daypart": [], "gender": []},
 "performance": {"intensity": "", "longevity": ""},
 "avoid": [],
 "additional_requirements": ["진한 하얀 꽃 향", "비누처럼 밝은 느낌"]}
```

`nlr_engine.understand(index, text, conditions)` 의 `conditions` 가 바로 이것입니다.
**변환이 필요 없습니다.**

프롬프트의 핵심 제약(그대로 지켜야 합니다) —
*"이미지·감각 표현(깨끗한·포근한·차가운)을 임의의 향으로 바꾸지 마세요.
확신할 수 없는 원문 의미는 `additional_requirements` 에 보존하세요."*
**해석은 사전이 합니다. LLM 은 뽑기만 합니다.**

백엔드가 이미 `GMS_API_KEY` · `GMS_MODEL` 환경변수를 `application-prod.yaml` 에 두고
있으므로 팀에 키가 있습니다. 인프라에 AI 서버용 환경변수를 요청하면 됩니다.

---

## 2. 할 일 — 우선순위

### A. ①단계 LLM 구조화 붙이기 ★ 이번 작업의 본체

**새 모듈** `ai/llm_stage1.py` 를 만듭니다. `nlr_engine.py` 에 넣지 마십시오 —
**엔진은 네트워크를 모른다**는 것이 이 코드의 설계이고, 그래야 DB·인터넷 없이 테스트됩니다.

```
structure(text, *, timeout=..., session=...) -> dict | None
    문장 하나를 conditions dict 로. 실패하면 None.
```

지켜야 할 것

- **프롬프트를 파일에서 읽습니다.** `EDA/.../15_stage1_llm_prompt_v1.txt` 를
  `ai/data/` 또는 `ai/prompts/` 로 복사하고, 파일의 sha256 앞자리를 로그에 남깁니다.
  프롬프트가 바뀌었는데 결과가 바뀐 이유를 모르게 되는 것을 막습니다.
- **키는 환경변수(`GMS_API_KEY`)** 로만 받습니다. 기본값을 코드에 넣지 마십시오.
- **실패하면 `None` 을 돌려주고 서비스는 계속 돕니다.** LLM 이 죽어도 사전 매칭으로
  75.5% 는 답합니다. 예외를 삼키지 말고 로그에 남기되 요청은 500 으로 죽이지 마십시오.
- **`server.py` 에서 `conditions` 가 없을 때만** 부릅니다. 백엔드가 이미 넘겼으면
  그대로 씁니다(계약서 그대로).
- 타임아웃은 실측 p99 2.44초를 근거로 잡되 **백엔드 타임아웃 8초 안에** 들어와야 합니다.

### B. ⑤단계 LLM 추정 경로 연결

`spec.md` §3 ②-d 가 *"사전에 없는 말은 LLM 이 향 특성을 추측하고 그 사실을 로그에 남긴다"*
로 정해 두었고, **코드에 자리가 이미 있습니다.**

```python
recommend(index, text, conditions, estimator=...)      # nlr_engine.py
unmatched_log.cached_estimator(estimate_fn, path=...)  # 같은 말엔 같은 답
```

- 조건이 **하나도 안 잡혔을 때만** 부릅니다(엔진이 이미 그렇게 짜여 있습니다).
- **캐시를 반드시 씁니다.** LLM 은 같은 뜻에 다른 답을 냅니다 — 같은 뜻 21쌍 중
  15쌍이 상위 50개에서 하나도 안 겹쳤습니다. 캐시가 없으면 같은 말에 사용자마다
  다른 향수가 나갑니다. 캐시는 별도 파일이 아니라 **미매칭 로그 자체**입니다.
- 추정 결과는 `tier: "LLM"` 이고 `rationale` 은 **비웁니다.** 사전의 근거와 섞으면
  나중에 구분할 수 없습니다(spec 1장). 설명은 `llm_reasoning` 에 따로 담깁니다.
- 추정용 프롬프트는 **없습니다.** 새로 만들어야 하는 유일한 프롬프트입니다.
  출력은 `{"accords": [...], "reasoning": "..."}` 이고 **92개 목록 안에서만** 고르게
  해야 합니다(`ai/data/accord_dictionary.csv`). 엔진이 목록 밖 값은 버립니다.

### C. 잘못된 UTF-8 요청의 에러 형식 — 알려진 결함

정상 JSON·문법 오류·필드 누락은 전부 `400 {code, message}` 로 나가는데,
**바이트 디코딩 실패만** `{"detail": ...}` 로 나갑니다. 핸들러 이전 단계라 안 걸립니다.
계약서에 "에러는 전부 공통 형식"이라고 적어 둔 것과 어긋납니다.
202 MR 리뷰 요청 사항 3번에 올려 둔 항목입니다.

### D. `ai/README.md` 의 「아직 안 되는 것」 절이 낡았습니다

- *"API 서버는 이 스토리 범위 밖"* → 202 에서 만들었습니다
- *"사전 44행"* → v1.8 은 53행입니다
- **설문 실패율 표기가 갈립니다. 원본(`spec.md`)은 48.4% 인데 두 곳에 44% 로 적혀
  있습니다** — `ai/README.md:213` 과 `ai/docs/nlr_api_contract.md:119`. 202 작업 때
  잘못 적은 것으로 보입니다. **48.4% 로 통일하십시오.**
  (같은 문서의 `README.md:360` 과 `search_rules.md:303` 은 48.4% 로 맞게 적혀 있습니다)

### E. 여력이 되면

- **Dockerfile** — 배포는 인프라 작업이지만 이미지 정의는 AI 쪽이 주는 편이 빠릅니다.
  메모리 약 500MB 필요(13만 × 92 행렬 48MB + pandas·numpy).
- **검사 스크립트를 저장소에** — 지금 세 MR 모두 *"테스트 코드를 작성했지만 저장소에
  넣지 않았습니다"* 로 나가 있습니다. `ai/` 에 테스트 디렉터리 관습이 없어서입니다.
- **향 특성 92개 한국어 표기** — 화면의 추천 이유를 채우려면 필요합니다.
  회의 안건 2 의 결과를 확인하고 시작하십시오.

---

## 3. 하면 안 되는 것

- **팀 저장소는 `ai/` 밖을 절대 건드리지 않습니다.** `backend/` · `frontend/` ·
  `Jenkinsfile` · 마이그레이션은 다른 담당입니다.
- **`master` · `develop` 에 직접 푸시하지 않습니다.** 브랜치를 팝니다.
  `feature/ai/S15P21E203-{번호}-{기능명}`
- **커밋과 푸시는 요청받을 때만 합니다.**
- **API 키를 코드·문서·커밋 어디에도 적지 않습니다.**
- **설문 155건은 사전 확장에 쓰지 않습니다.** 채점용입니다. 출처는
  팀 문서 · 미매칭 로그 · `ai_summary` 로 제한합니다(spec §7.2).
- **`domain_lexicon_v1.csv` · `v1_1.csv` 는 보존본**이라 덮어쓰지 않습니다.
- **측정하지 않은 개선을 개선이라고 말하지 않습니다.**

---

## 4. 검증 방법

### 서버 없이

```bash
cd ai
source venv/Scripts/activate            # PowerShell: .\venv\Scripts\Activate.ps1
export PYTHONIOENCODING=utf-8           # PowerShell: $env:PYTHONIOENCODING="utf-8"
python nlr_engine.py "빨래 냄새 나는 향수"
#   조건 ['fresh','soapy']  상태 OK  단계 AND  후보 518
```

### 서버로 — **한글을 `-d` 로 직접 넘기면 안 됩니다**

Windows 셸이 인자의 한글을 깨뜨립니다. Git Bash 는 400 으로 터지고
**PowerShell 은 에러 없이 `NO_CONDITION` 을 돌려줍니다.** 자세한 것은 `ai/README.md`.

```bash
uvicorn server:app --host 127.0.0.1 --port 8000
curl http://localhost:8000/health

printf '%s' '{"text":"빨래 냄새 나는 향수 찾고 있어"}' | \
  curl -s -X POST http://localhost:8000/nlr/recommend \
       -H 'Content-Type: application/json' --data-binary @-
```

### 회귀 — **반드시 돌리십시오**

```bash
cd EDA
python 41_lexicon_ndcg.py ../../S15P21E203/ai/data/domain_lexicon_v1_8.csv
#   쿼리 600 · NDCG@5 0.4688 · 조건충족률 0.5908     <- 이 값이 유지돼야 합니다
```

**①단계를 붙이면 커버리지가 75.5% → 86.7% 로 올라야 합니다.** 안 오르면 프롬프트나
파싱이 잘못된 것입니다. 600문장에 저장된 LLM 결과(`34_evalset_stage1_checkpoint.csv`)와
새로 부른 결과를 대조하면 원인을 좁힐 수 있습니다.

---

## 5. 지금 열려 있는 것

| | 상태 |
|---|---|
| MR **!112** (245 적재 파일) | 리뷰 중. 백엔드 코멘트 1건 해결하고 답변 대기 |
| **249** (사전 v1.8) | 푸시됨. **MR 아직 안 올림** |
| `DECISIONS.md` **N10** | 사용자 승인(9/14). **팀 승인 전** |
| 회의 안건 2 (추천 이유 표기) | 결과 확인 필요 |
| 회의 안건 3 (LLM 추측 표시) | 결과 확인 필요 — **B 작업이 여기 걸립니다** |
| 회의 안건 4 (LLM 호출 위치) | 결과 확인 필요 — **A 작업이 여기 걸립니다** |
| `ai/docs/nlr_briefing.html` | 미커밋. 회의 자료라 넣을지 미정 |
| 백엔드 13만 적재 | 245 머지 후 진행 |

**A 를 시작하기 전에 안건 4(LLM 을 AI 서버에서 부를지 Spring 에서 부를지)를
확인하십시오.** AI 서버에서 부르기로 했다면 그대로 진행하고, Spring 이면
`/nlr/understand` 를 Spring 이 부르는 형태가 되어 A 의 범위가 달라집니다.

---

## 6. 읽을 순서

| | 무엇을 |
|---|---|
| 1 | `EDA/AGENTS.md` — 작업 규칙 |
| 2 | `EDA/docs/WORKING_NOTES.md` — 실행 환경, 하면 안 되는 조작 |
| 3 | **이 문서** |
| 4 | 팀 `ai/README.md` — 서버 기동, 미매칭 로그 |
| 5 | 팀 `ai/docs/nlr_api_contract.md` — 연동 형식 |
| 6 | 팀 `ai/docs/search_rules.md` — 검색·정렬 규칙과 근거 |
| 7 | `EDA/docs/spec.md` §1 · §3 ②-d · §4.3 · §4.4 |
| 8 | `EDA/docs/DECISIONS.md` **N10** (최신) · N2 · N9 |
| 9 | 팀 `ai/nlr_engine.py` · `ai/server.py` · `ai/unmatched_log.py` |
