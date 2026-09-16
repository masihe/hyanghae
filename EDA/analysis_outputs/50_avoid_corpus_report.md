# 50. 회피 후보 넷의 ai_summary 배수 — N4 방법 재적용

재현: `./venv/Scripts/python.exe 50_avoid_corpus_evidence.py`
방법: `30_ai_summary_expression_accord.ipynb`(N4)의 계산을 새 후보 4개에 재적용. 노트북은 실행하지 않았다 — 로직만 새 스크립트로 옮겼다.

## 표본

- 전체 향수 131,930 · `ai_summary` 보유 12,432(9.4%) · accord 와 둘 다 보유 12,411
- 통제군(무작위) 최대 배수 1.38 — 표현별 배수와 이 값을 비교해서 읽는다

## 표현별 결과

| 표현 | 해당 향수 | 상위 accord (배수) |
|---|---:|---|
| 화려한 | 437 | `tuberose` 1.92x · `rose` 1.37x · `yellow floral` 1.31x · `patchouli` 1.24x · `animalic` 1.23x |
| 인공적인 | 6,274 | `sour` 1.64x · `coconut` 1.40x · `cherry` 1.37x · `tropical` 1.34x · `salty` 1.28x |
| 흔한 | 2,818 | `aquatic` 1.56x · `marine` 1.54x · `salty` 1.52x · `ozonic` 1.34x · `fresh` 1.29x |
| 복잡하게 변하는 향 | 3,766 | `whiskey` 1.75x · `cherry` 1.33x · `smoky` 1.33x · `tobacco` 1.31x · `balsamic` 1.26x |

`*` 는 검색어가 accord 이름과 겹쳐 순환인 항목 — 신호로 읽지 않는다.

## 검색어 (결과를 보기 전에 정함)

- `화려한` -> ['flashy', 'showy', 'loud', 'extravagant', 'glamorous']  (순환: ['oud'])
- `인공적인` -> ['synthetic', 'artificial', 'chemical']
- `흔한` -> ['common', 'ordinary', 'generic', 'basic', 'typical']
- `복잡하게 변하는 향` -> ['complex', 'evolves', 'evolving', 'multifaceted', 'layered']

## 한계 — N4 와 동일하게 적용된다

- 대중적 향수에 쏠린 표본이다(`ai_summary` 커버리지 9.4%, 평가자 수 중앙값이 70배 차이)
- 동반 출현이지 인과가 아니다
- 영어 서술이라 번역 가정이 들어간다
- Fragrantica 출처라 서비스 반영 여부는 별도 판단(`spec.md` §8)이 필요하다
- 부분 문자열 검색이라 잡음 제거가 안 돼 있다

## 관련 자료

- `DECISIONS.md` N4 — 이 방법의 원 결정과 근거
- `30_ai_summary_expression_accord.ipynb` — 원 계산 (실행하지 않음, 로직만 참고)
- `48_avoid_concept_suppression.py` — 이 넷을 후보로 고른 근거(NO_MAP 41개 분류)