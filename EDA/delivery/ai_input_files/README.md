# AI 서버 보조 파일 — 생성 스크립트 인계

| | |
|---|---|
| 작성 | 2026-09-17 |
| 대상 | 팀 저장소 `ai/` |
| **전제** | **아직 넣지 마십시오.** 엔진이 이 파일들을 읽는 코드가 없습니다. 아래 3장의 질문이 먼저 풀려야 합니다 |
| 근거 | 측정 기록 **24번** · `docs/plans/NLR_SIMILAR_PERFUME_SCOPE.md` 10·11장 |

**표기** — **[측정]** 은 실제로 잰 값, **[제안]** 은 판단, **[미확인]** 은 아직 모르는 것입니다.

---

## 1. 무엇을 만드나 — 한 줄

**AI 서버가 DB 없이 쓸 수 있도록 향 지도 200개 목록과 향수 한국어 이름을 파일로 만든다.**

```
python build_ai_inputs.py

    ai/data/map_perfume_ids.csv        200행      1.4KB    fragrantica_id
    ai/data/perfume_names_ko.csv   129,160행  3,451KB    fragrantica_id · name_ko
```

원천이 둘 다 팀 저장소에 있어 **DB 를 읽지 않습니다.**

```
backend/db/seed/perfume_map_points.csv   향 지도 200개 (MAP 담당 산출물)
backend/db/seed/perfume_ko.csv           향수 한국어 이름 (백엔드 seed)
ai/data/perfumes_nlr.csv.gz              엔진이 쓰는 향수 129,161개
```

---

## 2. 들어 있는 것

```
build_ai_inputs.py   생성 스크립트
README.md            이 문서
```

**데이터 파일은 넣지 않았습니다.** 스크립트로 언제든 다시 만들 수 있고,
`perfume_names_ko.csv` 가 3.4MB 라 저장소에 두기에 큽니다. 그리고 지금은 **어느 코드도
읽지 않아서**, 넣어 두면 `S15P21E203-306`(안 쓰는 데이터 파일 정리)과 같은 이유로
다음에 지워질 수 있습니다.

---

## 3. ⚠ 왜 아직 팀 저장소에 넣지 않았나

**이 파일들이 필요한 이유는 200개 우선 정렬입니다.** `ai/docs/nlr_api_contract.md`
50행에 이렇게 적혀 있습니다.

> | 4 | **향 지도 200개를 항상 먼저 보여준다** | 형식은 안 바뀐다. 순서만 바뀐다 |

「이 계약이 서 있는 결정 넷」의 네 번째이고 **아직 구현되지 않았습니다** [측정].

```
엔진 코드         korea_selection · map_point · is_map · priority   전부 0건
엔진 데이터        perfumes_nlr.csv.gz 에 200개인지 표시하는 칸 없음
search_rules.md   계약이 이 문서를 가리키는데 "200개" 언급 0건
```

의도적으로 미룬 것입니다 — 커밋 `4efa3bf`(2026-09-14) 메시지가 `onMap`(향지도 200개
여부)을 *"아직 구현하지 않은 필드"* 로 적었습니다.

### 막고 있는 질문

**"왜 200개를 먼저 보여주는가" 의 근거가 어디에도 없습니다.** 계약 문서에 결정만 있고
이유가 없습니다.

정렬을 바꾸는 것은 `DECISIONS.md` **N9**(정렬 규칙)를 다시 여는 일입니다. N9 는 정렬 식
후보 셋을 전체 데이터로 비교해 정한 것이고, 근거 없이 그 위에 규칙을 하나 더 얹으면
나중에 왜 그랬는지 아무도 모릅니다.

**이 결정을 한 사람이 이유를 말해 준 뒤에 적용하십시오.**

---

## 4. 적용 방법 (질문이 풀린 뒤)

새 Jira 이슈와 브랜치가 필요합니다. 200개 우선 정렬 구현과 **한 이슈로 묶는 것을
권합니다** [제안] — 파일만 넣으면 안 쓰이는 데이터가 됩니다.

```bash
cd <팀 저장소 루트>
git switch develop && git pull origin develop
git switch -c feature/ai/S15P21E203-<이슈키>-map-first-ordering

cp <이 폴더>/build_ai_inputs.py ai/
cd ai && python build_ai_inputs.py
```

그다음 해야 하는 것이 남습니다.

```
nlr_engine 이 map_perfume_ids.csv 를 읽어 정렬에 반영한다
search_rules.md 에 그 규칙을 적는다   ← 계약 문서가 이 문서를 가리키고 있다
DECISIONS.md 에 N9 와의 관계를 적는다
```

---

## 5. 한국어 이름 맞추기 규칙 — SQL 과 같아야 합니다

`backend/db/seed/load_perfume_catalog.sql` **133~140행**과 같은 규칙을 씁니다.

```sql
SELECT name, min(NULLIF(btrim(translated_name), '')) AS translated_name
FROM stg_perfume_ko
WHERE NULLIF(btrim(name), '') IS NOT NULL
  AND NULLIF(btrim(translated_name), '') IS NOT NULL
GROUP BY name
HAVING count(DISTINCT btrim(translated_name)) = 1;
```

**영문 이름 하나에 번역이 하나로 정해지는 것만 쓰고 겹치면 버립니다.** 실측에서 버린
이름이 **1개**였습니다.

**규칙이 두 곳에 있습니다.** 한쪽을 바꿀 때 다른 쪽도 봐야 합니다. 스크립트 docstring
에도 적어 두었습니다.

### 앞뒤 공백

`build_load_files.py` 와 같은 방식으로 `str.strip()` 을 씁니다. 원본 향수 이름 917개에
앞뒤 공백이 있고 그중 NBSP(U+00A0)가 섞여 있어 **SQL 의 `TRIM()` 으로는 걷지 못합니다.**

---

## 6. 검증 결과 [측정]

`perfumes.name_ko` 와 대조했습니다.

```
DB 행수 129,160 · 생성 파일 129,160 · 한쪽에만 있는 것 0개 · 값이 다른 것 3개
```

**그 3개는 DB 가 낡은 것입니다.** `perfume_ko.csv` 가 2026-09-17 에 `develop` 에서
갱신됐고 DB 는 그 전에 적재됐습니다.

```
Eclat d'Arpège                원천·생성 파일 → 에클라 드 아르페주   DB → 에클라 다르페주
Eclat d'Arpège Summer 2007    같은 이유
Chanel N°5 Eau Premiere       원천·생성 파일 → 샤넬 No. 5 오 프르미에르   DB → 샤넬 No. 5 오 프레미어
```

**즉 생성 파일이 최신 원천을 따릅니다.** 같은 규칙으로 같은 결과가 나오는 것이
확인됐습니다.

200개 목록은 **200개가 전부 엔진 데이터에 있습니다**(없는 것 0개).

---

## 7. ⚠ 같은 데이터가 한 곳 더 생깁니다

`spec.md` **§8 19번**이 이미 향수 정보가 두 곳에 있는 것을 문제로 적었습니다.

> **같은 향수 정보가 두 곳에 있고 서로 다르다.** 화면에서 두 출처를 섞으면 어긋난다.

이 파일들이 한 곳을 더 만듭니다. 그래서 **원천을 복사하지 않고 스크립트로 다시 만드는
방식**을 골랐습니다 — 원천이 바뀌면 다시 돌립니다.

**다만 자동으로 따라가지는 않습니다.** `perfume_ko.csv` 나 `perfume_map_points.csv` 가
갱신되면 누군가 이 스크립트를 다시 돌려야 합니다. 그 시점을 정하는 규칙이 없습니다
[미확인].

---

## 8. 왜 DB 를 읽지 않기로 했나

`spec.md` **132~139행**이 이유를 적었습니다.

> 두 서버가 같은 DB 스키마를 알고 있으면 DB 담당자가 컬럼 하나를 바꿀 때 양쪽을
> 고쳐야 한다. Python 이 DB 를 모르면 그 위험이 사라지고, 입력→출력만 보면 되니
> 테스트와 실험도 쉬워진다.

**다만 그 전제는 이미 깨졌습니다** — `spec.md` 설계에서는 검색을 Spring 이 SQL 로
하기로 했는데, 협의에서 AI 서버가 검색까지 하기로 바뀌었습니다. 그래서 지금
`perfumes_nlr.csv.gz` 4.97MB 를 들고 있습니다.

**현재의 실질 이유는 배포 조건입니다.** 아웃바운드가 `gms.ssafy.io` 하나로 제한돼
인프라에 인계됐습니다(`NLR_DEPLOY_HANDOFF.md` · 2026-09-15).

DB 를 읽는 선택지를 검토했고 **파일 쪽을 골랐습니다.** 필요한 것이 두 개뿐이고
(200행 + 129,160행), DB 를 읽으려면 의존성 4개→5개 · 아웃바운드 조건 변경 · DB 장애가
AI 서버로 번지는 것을 받아들여야 합니다. `NLR_PREDEPLOY_DECISIONS.md` **안건 ④** 가
같은 질문을 다루고 **미결**입니다.

---

## 9. 확인하지 못한 것

- **엔진이 이 파일들을 읽는 코드를 쓰지 않았습니다.** 파일만 만들었습니다
- **200개를 먼저 보여주는 근거** [미확인]. 3장. 이 결정을 한 사람이 답해야 합니다
- **정렬에 어떻게 반영할지** [미확인]. 맨 앞으로 끌어올릴지, 동점일 때만 앞세울지,
  몇 개까지 허용할지 정해지지 않았습니다. `search_rules.md` 가 비어 있습니다
- **원천 갱신을 따라가는 규칙** [미확인]. 7장
- **`perfume_names_ko.csv` 를 엔진이 실제로 쓸 때의 메모리 증가** [미확인].
  129,160행을 읽으면 기동 시간과 메모리가 늘어납니다. 재지 않았습니다

---

## 10. 재현

```bash
cd <팀 저장소 루트>/ai
python build_ai_inputs.py
```

출력은 `ai/data/` 아래에만 씁니다. 입력은 읽기만 합니다.

**스크립트가 자기 위치를 기준으로 경로를 잡습니다**(`HERE = Path(__file__).parent`).
그래서 이 인계 폴더에서 그냥 돌리면 원천을 못 찾습니다. **복사하지 않고 검증만 하려면
경로를 인자로 넘기십시오.**

```bash
T=C:/Users/SSAFY/Desktop/S15P21E203
python build_ai_inputs.py \
  --source     "$T/ai/data/perfumes_nlr.csv.gz" \
  --map-points "$T/backend/db/seed/perfume_map_points.csv" \
  --perfume-ko "$T/backend/db/seed/perfume_ko.csv" \
  --output-dir <임시 폴더>
```

**이 방법으로 팀 저장소의 것과 같은 파일이 나오는 것을 확인했습니다** [측정 · 2026-09-17].
두 파일 모두 sha256 이 같았습니다.

DB 와 대조하려면 이렇게 합니다.

```bash
cd <팀 저장소 루트>
docker compose -f compose.manual-test.yaml exec -T postgres \
  psql -U hyanghae -d hyanghae_test -At -F$'\t' -c \
  "SELECT fragrantica_id, name_ko FROM perfumes
   WHERE NULLIF(btrim(name_ko),'') IS NOT NULL ORDER BY fragrantica_id;"
```
