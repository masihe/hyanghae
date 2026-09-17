# 향 사전 v1.8 → v1.14 — 배포 인계

| | |
|---|---|
| 작성 | 2026-09-16 |
| 대상 | 팀 저장소 `ai/` |
| **전제** | **MR !148(296 노트 브리지)이 먼저 병합돼야 합니다.** 패치가 그 위에서 만들어졌습니다 |
| 근거 | 측정 기록 14번 · `NLR_PREDEPLOY_DECISIONS.md` 「사전 버전이 어긋나 있습니다」 |

**표기** — **[측정]** 은 실제로 잰 값, **[제안]** 은 판단입니다.

---

## 1. 무엇을 바꾸나 — 한 줄

**엔진의 기본 사전을 `domain_lexicon_v1_8.csv` 에서 `domain_lexicon_v1_14.csv` 로 바꿉니다.**

```
지금    팀 저장소 기본값   v1_8  (53행 · 고유 표현 33개)
분석    최근 측정 전부     v1_14 (63행 · 고유 표현 41개)   개인 저장소에만 있었습니다
```

`NLR_PREDEPLOY_DECISIONS.md` 가 *"사전 버전이 어긋나 있습니다"* 로 적어 둔 것을 맞추는 일입니다.

---

## 2. 들어 있는 것

```
lexicon_v1_14.patch            엔진 1줄 + 문서 숫자 (6개 파일 · +35 / -34)
data/domain_lexicon_v1_14.csv  사전 63행 · 31KB
README.md                      이 문서
```

---

## 3. 적용 방법

**MR !148 이 병합된 뒤에** 최신 `develop` 에서 브랜치를 만듭니다.

```bash
cd <팀 저장소 루트>
git switch develop && git pull origin develop
git switch -c feature/ai/S15P21E203-<이슈키>-lexicon-v1-14

cp delivery/lexicon_v1_14/data/domain_lexicon_v1_14.csv ai/data/
git apply --check delivery/lexicon_v1_14/lexicon_v1_14.patch   # 먼저 확인만
git apply delivery/lexicon_v1_14/lexicon_v1_14.patch
```

**옛 사전 `domain_lexicon_v1_8.csv` 는 지우지 않습니다.** `v1_2` 도 남아 있고,
`NLR_LEXICON_PATH` 로 버전을 바꿔 비교할 수 있어야 합니다(README 참고).

### 되돌리는 법

```bash
git apply -R delivery/lexicon_v1_14/lexicon_v1_14.patch
rm ai/data/domain_lexicon_v1_14.csv
```

---

## 4. 효과 — **성능이 근거가 아닙니다** [측정]

합성 평가셋 600문장 · 노트 브리지 켬 · LLM 호출 없이 저장된 ①단계 출력 재사용.

| | v1_8 (지금) | **v1_14 (패치 후)** |
|---|---:|---:|
| 사전 행수 | 53행 (고유 표현 33) | **63행 (고유 표현 41)** |
| LLM 구조화 + 사전 | 529/600 = 88.2% | **533/600 = 88.8%** |
| 사전만 (LLM 없이) | 453/600 = 75.5% | **461/600 = 76.8%** |
| `AND` / `SINGLE_BROAD` / 완화 | 412 / 75 / 42 | 417 / 73 / 43 |

**NDCG@5 는 0.495198 → 0.496896 (+0.001698) 인데, 짝지은 부트스트랩 20,000회에서
95% 구간이 `[-0.001358, +0.005059]` 로 0 을 포함합니다** [측정].
응답 단위로도 **나아진 6건 · 나빠진 6건 · 동점 588건**입니다.

**성능이 올랐다고 말할 수 없습니다.** 이 MR 의 근거는 셋입니다.

1. **일관성** — 최근 분석과 측정 기록(14 · 18 · 19 · 20번)이 전부 `v1_14` 기준입니다.
   배포본이 `v1_8` 이면 모든 측정에 *"배포본과 다름"* 단서를 달아야 합니다
2. **`lexicon_version` 컬럼** — `NLR_PREDEPLOY_DECISIONS.md` 안건 ②의 피드백 테이블에
   실제 배포본 값이 들어가야 합니다
3. **회피 확장이 준비돼 있습니다** — v1.9~v1.14 확장의 상당수가 회피용 표현입니다.
   지금은 닿지 않지만(아래 6번) `DECISIONS.md` N12 를 구현하는 날 바로 살아납니다

---

## 5. 문서 숫자를 함께 고쳤습니다

사전을 바꾸면 **6개 파일 21곳**의 실측값이 낡습니다. 패치에 함께 담았습니다.

| 파일 | 고친 것 |
|---|---|
| `nlr_engine.py` | `DEFAULT_LEXICON` (동작) · 설명문 2곳 |
| `README.md` | 데이터 목록 · 실측표 2개 · `NLR_LEXICON_PATH` 기본값 · `candidate` 행수 |
| `server.py` · `llm_stage1.py` | 기동 로그 설명과 실측값 |
| `docs/search_rules.md` | 사전 파일명·행수 · `candidate` 행수 · 브리지 절의 기준 사전 |
| `docs/nlr_api_contract.md` | 구조화 유무에 따른 비율 |

---

## 6. 알아야 할 것 — **회피 확장은 지금 닿지 않습니다**

v1.9~v1.14 에서 늘린 것의 상당수가 **회피용 표현과 활용형**입니다. 그런데 **현재 엔진은
회피를 처리할 때 향 사전을 보지 않습니다.**

```python
# nlr_engine.py  understand()
for raw in ((structured or {}).get("avoid") or []):
    accord = _normalize_accord(index, raw)   # 사전을 안 탄다
```

합성 600 에서 회피가 잡힌 문장 수가 **v1_8 도 7건, v1_14 도 7건으로 같습니다** [측정].

*"회피도 사전을 경유한다"* 는 **`DECISIONS.md` N12 로 이미 결정됐고 미구현**입니다.
그것이 구현되면 이 사전 확장이 살아납니다. **이 MR 은 그 준비입니다.**

---

## 7. 확인하지 못한 것

- **실사용 성능은 여전히 못 잽니다.** 설문 143건에 정답 라벨이 없습니다(`spec.md` §8 3번)
- **설문 143건에서는 v1_8 과 v1_14 가 사실상 같습니다** — 평균 조건 1.68 vs 1.69,
  `AND` 56 vs 56 [측정]. 실사용 문장에서는 차이가 안 보입니다
- **`relation_type` 값이 부정확한 채로 갑니다.** N10 이 직역으로 판정한 5행
  (`과육`·`꿀`·`나무`·`상큼한`·`풀 냄새`)이 `EVOKES` 로 붙어 있습니다.
  **N11 이 이 열만 고치는 것을 측정해 기각했습니다** — 엔진이 읽는 8개 컬럼에
  `relation_type` 이 없어 아무것도 안 바뀝니다. N12 를 구현할 때 함께 고쳐야 합니다
- **`status` 는 여전히 전부 미확정입니다** — 63행 중 47행이 `candidate` 입니다.
  서비스에 써도 되는지에 대한 팀 판정이 없습니다
- **옛 사전을 지울지 정하지 않았습니다.** `v1_2` · `v1_8` 을 남겨 뒀습니다

---

## 8. 재현

```bash
cd EDA
export PYTHONIOENCODING=utf-8
./venv/Scripts/python.exe -W ignore 67_field_assignment_defects.py   # v1.14 기준 측정
```

사전 v1.8 → v1.14 의 효과는 **측정 기록 14번**에 있습니다.
