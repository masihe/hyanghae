# 자연어 추천 — 다음 세션 인수인계

| | |
|---|---|
| 작성 | 2026-09-17 |
| 담당 | 김용석 (AI) |
| 저장소 | 팀 `C:\Users\SSAFY\Desktop\S15P21E203` 의 **`ai/` 만** · 개인 `C:\Users\SSAFY\Desktop\hyanghae` 는 자유 |
| 이 문서 | **다음 세션이 시작할 때 읽는다.** 일이 끝나면 갱신하거나 지운다 |

---

## 0. 다음 세션이 할 일 — 한 줄

**`ai/` 에서 안 쓰는 파일을 정리한다.** 새 Jira 이슈가 필요하다.

다른 것은 **다 준비돼 있고 사람의 행동(리뷰·이슈 생성)을 기다리는 중**이다.

---

## 1. 지금 서 있는 자리 — 한 눈에

```
[진행 중]  MR !148  노트 브리지          커밋 4개 · 리뷰 반영 완료 · **병합 대기**

[준비 완료 · 이슈 번호만 있으면 바로 MR]
   delivery/lexicon_v1_14/        사전 v1.8 -> v1.14
   delivery/unmatched_estimator/  ⑤단계 미매칭 추정 + 캐시
   (둘 다 !148 병합 뒤 develop 에서 브랜치를 판다)

[다음 세션의 일]
   ai/ 파일 정리                   아래 4장. 아직 아무것도 안 했다

[사람이 해야 하는 것]
   MR !148 리뷰 · Jira 이슈 3개 생성 · Jira 상태 이동
   (Jira 도 GitLab MR 생성도 이 도구로는 못 한다)
```

---

## 2. 끝난 것 — 다시 하지 말 것

### 팀 저장소에 올라간 것 — MR !148 (브랜치 `feature/ai/S15P21E203-296-note-accord-bridge`)

```
5926709  feat: 노트 이름을 accord 로 해석하는 브리지 연결
18e5bf7  docs: 노트 브리지 연결에 맞춰 검색 규칙과 실측값 갱신
ddc6e80  fix: 노트 브리지 표의 결측 행을 버리고 조회 결과를 tuple 로 굳힌다   ← 리뷰 반영
6280812  docs: p 문턱이 배포 CSV 에서 거르지 않는다는 사실과 기저율 계수 근거를 바로잡는다  ← 리뷰 반영
```

**리뷰 지적 두 건을 다 반영했다.** `p >= 0.5` 가 배포 CSV 에서 0행을 거른다는 것(실제로
거르는 것은 `lift` 987행)과, `woody` 기저율 0.617 이 역산값이고 직접 재면 0.6305 라는 것.

### 기록된 것

```
DECISIONS.md  N14  노트 브리지 연결 (p>=0.5 · lift>=1.4)
              N15  ⑤단계 미매칭 추정 + 파일 캐시   ← 새로 씀
측정 기록      18   브리지 규칙 넷 비교 · 기저율
              19   설문 155건 중 12건이 향수 요청이 아니다 -> 143건으로 잰다
              20   ⑤단계 추정 천장·E1/E2/E3·지연     ← 새로 씀
WORKING_NOTES 6장  **팀 DB 를 로컬에서 보는 법**      ← 새로 씀
```

### 측정으로 닫힌 질문들

```
브리지 규칙            D3(p>=0.5 · lift>=1.4). 문턱은 72번이 0~2.5 를 훑어 검증
N2 단독 매핑 금지       걸리지 않는다. 단독 조건이 89 -> 73 으로 **줄어든다**
설문 무효 응답          동의 표현 12건 제외. 67·72·74번이 자동으로 뺀다
⑤단계 추정 켤 것인가    켠다. 실사용 조건 추출 60.8% -> 85.3%
표현당 accord 개수      E3(최대 3개)
지연                   병렬로 문장당 6.05s -> 1.64s. GMS 한도 분당 3만 요청
일관성                 캐시로 막는다. 같은 문장 두 번 -> 0/5 에서 **5/5** 일치
캐시 위치              **파일(미매칭 로그 자체).** DB·백엔드 경유는 제약에 걸린다
강도 컬럼(안건 ①)       **넣지 않는다**(2026-09-17 뒤집힘). 되돌릴 수 없는 손실이 아니다
미매칭 로그 위치(안건 ③) DB 는 백엔드가 INSERT · AI 는 파일을 캐시로 계속 쓴다
```

---

## 3. 준비돼 있는 인계 묶음 — `EDA/delivery/`

각 폴더의 `README.md` 에 적용 명령 · 효과 · 한계 · MR 재료가 다 있다.

| 폴더 | 무엇 | 상태 |
|---|---|---|
| `note_bridge/` | 노트 브리지 | **적용 완료**(MR !148). 참고용으로 남긴다 |
| `lexicon_v1_14/` | 사전 v1.8 → v1.14 | `git apply --check` 통과. **Jira 이슈 필요** |
| `unmatched_estimator/` | ⑤단계 추정 + 캐시 | `git apply --check` 통과. **Jira 이슈 필요** |

**둘 다 MR !148 이 병합된 뒤 상태를 기준으로 만들었다.** 병합 전에 `develop` 에서
브랜치를 파면 충돌한다.

### 사전 v1.14 — **성능이 근거가 아니다**

NDCG `+0.0027` 인데 95% 구간이 `[-0.000146, +0.005997]` 로 0 을 포함한다. 응답 단위로도
나아진 6건 · 나빠진 6건 · 동점 588건이다. **근거는 일관성이다** — 앞으로의 모든 측정이
v1_14 기준이고 `lexicon_version` 컬럼에 실제 배포본이 들어가야 한다.

**회피 확장은 지금 엔진에서 닿지 않는다.** `understand()` 가 `avoid` 를 `_normalize_accord`
로만 푼다 — 사전을 안 탄다. `DECISIONS.md` N12 가 구현돼야 열린다.

### ⑤단계 추정 — **`spec.md` 1장의 예외다**

1장이 *"매핑은 사전이 하고 LLM 은 구조화만 한다"* 인데 이 기능은 LLM 이 매핑한다.
근거와 한계 9개를 `DECISIONS.md` N15 에 적었다. **NDCG +0.0466 은 합성 600 이
역생성 데이터라 부풀려졌을 수 있다** — 믿을 지표는 조건 추출률 60.8% → 85.3% 다.

---

## 4. 다음 세션의 일 — `ai/` 파일 정리

**(가) 로 확정**(2026-09-17 사용자 결정). ①·② 만 하고 ③ 은 팀 회의로 넘긴다.

### 왜 이 파일들이 있나

DB 에 향수 데이터가 없던 시절의 산물이다. `build_data.py` 가 스스로 적어 뒀다 —
*"DB 에 향수 전체가 들어가면 이 파일은 필요 없어진다. 그때까지의 임시 조치다."*
**그 조건이 2026-09-17 에 충족됐다**(DB 에 `perfumes` 129,161 · `perfume_accords`
1,000,570 · `accords` 92 · `WORKING_NOTES.md` 6장).

### ① 지우는 것 — 근거가 문서에 있다

```
ai/data/perfumes_already_in_db.csv     1KB   "DB 에 이미 있는 것" 목록. UPSERT 로 대체됐다
ai/data/accords_already_in_db.csv      0KB   PREDEPLOY 2-1: "적재 전 스냅샷이라 이미 낡았다"
ai/data/domain_lexicon_v1_2.csv       19KB   사전 옛 버전. **어느 코드도 안 쓴다**
```

`build_load_files.py` 가 앞 둘을 참조하므로 **그 참조도 함께 지운다.**

### ② 개인 저장소로 옮기는 것

```
ai/delivery/for_db/  accords.csv · brands.csv · perfumes.csv.gz · perfume_accords.csv.gz
```

DB 적재용으로 만든 것이고 **적재가 끝났다.** 다만 **재적재할 일이 생기면 또 필요하다**
(사전 버전 변경 · 강도 컬럼 추가). `build_load_files.py` 로 다시 만들 수 있다.

### ③ 손대지 않는 것 — 팀 회의 안건이다

```
ai/data/perfumes_nlr.csv.gz   4.85MB   DB 의 perfumes + perfume_accords 와 같은 내용
ai/data/accord_dictionary.csv    7KB   DB 의 accords 와 같은 내용
```

**DB 로 옮길 수 있지만 큰 변경이다.** `psycopg` 의존성이 붙어 4개 → 5개가 되고,
*"DB 없이 독립적으로 돈다"* 가 깨지며(DB 가 죽으면 AI 도 못 뜬다), 인프라에 인계한
배포 조건이 바뀐다. **`NLR_PREDEPLOY_DECISIONS.md` 안건 ④ 가 바로 이 안건이고 미결이다.**

### ④ 남기는 것 — DB 에 대응 테이블이 없다

```
ai/data/domain_lexicon_v1_8.csv   25KB   향 사전. 팀이 만든 핵심 자산
ai/data/note_accord_bridge.csv    95KB   노트 브리지
ai/data/stage1_prompt_v1.txt       2KB   ①단계 프롬프트
ai/logs/                                 미매칭 로그 = **추정 캐시**. 볼륨이 필요하다
```

`%lexicon%` · `%bridge%` · `%nlr%` 이름의 테이블을 DB 에서 찾았으나 **하나도 없다** [측정].

---

## 5. 사람이 해야 하는 것 — 도구로 안 된다

```
MR !148 리뷰·병합
Jira 이슈 3개 생성       사전 v1.14 · ⑤단계 추정 · ai/ 파일 정리
Jira 상태 이동           브랜치 생성 -> In Progress · MR 생성 -> In Review
MR 생성                  glab 도 API 토큰도 없다. 제목·소스·타깃이 채워진 링크만 만들 수 있다
리뷰어 지정              AI 파트 MR 은 백엔드 담당 1명이 추가 리뷰 (컨벤션 3장)
```

**Jira 제목 형식** — `[모듈][작업종류] 작업 내용` (컨벤션 5장). 예: `[AI][Chore] ai 폴더의
안 쓰는 데이터 파일 정리`. **MR 제목에는 Jira 키를 넣고 커밋 메시지에는 넣지 않는다.**

---

## 6. 팀 DB 를 볼 수 있다

운영 DB 를 로컬로 복원해 뒀다(2026-09-17). 띄우는 법 · 접속 정보 · 무엇이 들어 있는지는
**`docs/WORKING_NOTES.md` 6장**에 있다.

```bash
cd C:/Users/SSAFY/Desktop/S15P21E203
docker compose -f compose.manual-test.yaml up -d --wait
docker compose -f compose.manual-test.yaml exec -T postgres \
  psql -U hyanghae -d hyanghae_test -c "SELECT count(*) FROM perfumes;"
```

**⚠ `spec.md` §8 19번이 낡았다.** *"DB 에는 향 지도용 200개, accords 60종뿐이고 people
컬럼이 없다"* 고 적혀 있는데 **셋 다 사실과 다르다.** 200 은 `perfume_map_points`,
60 은 seed 파일의 수다. `people` 은 `fragrantica_rating_count` 다.

---

## 7. 별개로 남은 것

### 팀이 정해야 하는 것

```
evidence 의 tier         브리지가 만든 accord 는 from·tier·rationale 이 null 이다.
                        근거를 붙이려면 계약(VERIFIED/TEAM/LLM)에 값이 하나 더 필요하다
API 계약 변경            백엔드가 미매칭을 DB 에 넣으려면 응답에 llmAccords 등 5칸이 더 필요하다
                        (PREDEPLOY 안건 ③ 후속). 합의되면 AI 쪽은 내가 고친다
raw_text 보관 기간       파일은 30일 뒤 비운다. **DB 쪽은 누가 지울지 안 정해졌다**
안건 ② 피드백 저장        **가장 급하다.** 오픈 후엔 사용자 행동이 영구 손실
안건 ④ perfumes_nlr      위 3장 ③
N2 원칙의 확장 범위       현행 엔진이 이미 만드는 단독 조건 27건이 먼저 대상이 된다
```

### 아직 답 없는 발견 — 셋 중 하나가 닫혔다

1. **`ozonic` 이 네 표현에 공통 신호** — 빨래 · 깨끗한 · 촉촉한 · 비 오는 숲.
   사전에 한 번도 들어 있지 않다
2. **`머스크 → soapy` · `이불 → soapy` 가 반증인데 `core` 다.** 같은 판정을 받은
   `호텔` · `차가운` 은 강등됐다. **왜 둘만 남았는지 모른다**
3. ~~**엔진이 `optional` 을 아예 버린다**~~ → **조사했다** (2026-09-17 · 측정 기록 22번)

   `spec.md` 206·262행이 *"`optional` 은 점수에만 기여한다"* 인데 구현은 필터·점수
   **양쪽에서** 버린다. 엔진 최초 구현(`47f6f3f`)에 주석 없이 들어왔고 그 커밋 메시지도
   언급하지 않았다 — **근거 있는 선택이 아니라 누락으로 보인다** [추정].

   **다만 고쳐도 얻는 것이 작다.** 설계대로 필터를 `core` 만 쓰면 `core` 가 없는 표현은
   여전히 조건 0개다. 살릴 대상이 `머스크`·`이불`·`비 오는 숲` **3개 표현**뿐이고
   결과 집합이 아니라 순위만 바뀐다. `search()`·`_rank()`·응답 형식까지 번지는 변경이라
   **이번에는 고치지 않기로 했다.**

   함께 확인된 것 — **사전 v1.14 가 늘린 6행이 전부 `optional` 이다.** 즉 사전을 넣어도
   엔진이 쓰는 행은 안 늘어난다. v1.14 의 근거는 여전히 일관성뿐이다.

### 낡은 채로 남겨 둔 곳 — 일부러 안 고쳤다

```
spec.md 개정 이력    2026-09-13 이 마지막. 09-14~09-17 세션이 없다
                    **그 작업을 한 사람이 써야 한다**
spec.md §8 19번      DB 현황이 낡았다(위 6장). 설계 문서 본문이라 손대지 않았다
spec.md §8 18번      "미매칭 로그 미구현" — 실제로는 unmatched_log.py 가 있다
```

---

## 8. 지켜야 할 것

```
팀 저장소    ai/ 밖은 절대 건드리지 않는다
             브랜치는 {작업유형}/{영역}/{Jira 키}-{기능명} · Co-Authored-By 를 붙이지 않는다
             **커밋과 푸시는 요청받았을 때만 한다** (TEAM_CONVENTIONS.md 7장)
원본 데이터   perfumes.csv · 체크포인트 CSV 를 덮어쓰지 않는다
측정 스크립트  파일을 만들지 않고 표준출력에만 쓴다 (41번 이후 관례)
             예외 — GMS 를 부르는 69·74번은 체크포인트를 남긴다
사전 버전    팀 저장소 기본값은 v1_8 · 최근 측정은 전부 v1_14
설문 데이터   19번 판정에 따라 **동의 표현 12건을 뺀 143건**으로 잰다
```

### 개인 저장소 미커밋 상태 (2026-09-17 기준)

```
 M EDA/docs/DECISIONS.md                          N13·N14·N15
 M EDA/docs/WORKING_NOTES.md                      6장 팀 DB 보는 법
 M EDA/docs/nlr_engineering_notes.md              측정 기록 15~20 · 목차
 M EDA/docs/spec.md                               관련 문서의 결정·측정 개수
 M EDA/docs/plans/NLR_INTEGRATION_DISCUSSION.md   같은 두 곳
 M EDA/docs/plans/NLR_NEXT_SESSION.md             이 문서
?? EDA/docs/plans/NLR_PREDEPLOY_DECISIONS.md      배포 전 확정 문서 (안건 ③ 후속 포함)
?? EDA/60~74_*.py                                 측정 스크립트 14개
?? EDA/analysis_outputs/69_* · 74_*               체크포인트와 프롬프트
?? EDA/delivery/lexicon_v1_14/ · unmatched_estimator/
```

**전부 커밋하지 않았다.** 커밋은 요청받았을 때만 한다.
