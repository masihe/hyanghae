# 49. 사전 v1.8 -> v1.9 — 향이 아닌 회피 표현 4개를 NOT_RELATED 로 명시

재현: `./venv/Scripts/python.exe 49_lexicon_v1_9_nonolfactory.py`
행 수: 53 -> 57 (신규 4) · alias 변경 1건 · API 호출 0회

## 무엇을 바꿨나

- `kr.nomap.sexy` aliases 에 `Sexy` 추가 — 영어 표기가 빠져 있었다
- `kr.nomap.feminine` 신규 — `여성스러운` (여성스러운|feminine|여성적인), source `B-72796-3`
- `kr.nomap.cute` 신규 — `귀여운` (귀여운|cute), source `B-64679-1`
- `kr.nomap.classic` 신규 — `클래식한` (클래식한|classic|고전적인), source `A-12109-3`
- `kr.nomap.young` 신규 — `어린` (어린|young|너무 어린 느낌|too young feel), source `B-1158-2|B-6693-2|B-56098-3|B-66933-2`

## 효과 — 지금은 없다

`nlr_engine.understand()` 의 avoid 는 accord 이름 완전 일치로만 풀리고 사전을 경유하지 않는다(48번 발견). 이 네 항목은 `NOT_RELATED`/`NO_MAPPING`이라 애초에 accord 를 연결하지 않으므로, 사전을 태우게 되더라도 검색 결과에 영향이 없다. 이번 변경의 유일한 즉시 효과는 `additional_requirements` 경로의 미매칭 분류가 `NOT_IN_LEXICON` 대신 `NOT_CORE`로 바뀌는 것뿐이다.

## 검증

v1.8 -> v1.9 로 사전만 바꿔 41번 NDCG 재현 게이트를 돌렸다. 두 값이 완전히 같아야 한다(NOT_RELATED 행은 accord 를 안 주므로). 실행 로그가 실제 값을 남긴다.

## 다루지 않은 것

48번이 찾은 41개 NO_MAP 표현 중 나머지 33개 — 매칭 방식으로 풀리는 것(`too sweet` 류, `NLR_NEXT_SESSION.md` 1장③에서 판단 보류 중), 질감층과 얽힌 것(`무겁`·`끈적`), 근거 조사가 더 필요한 것은 이 변경에 포함하지 않았다.

## 팀 저장소 반영

아직 반영하지 않았다. 이 파일은 개인 저장소에만 있다. `status: candidate`(사람 검토 전)로 표시해 뒀다.