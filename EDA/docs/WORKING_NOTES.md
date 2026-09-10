# 실행 환경 메모

이 저장소에서 실제로 작업할 때 부딪히는 것들. **설계 내용이 아니라 조작 방법과 함정만** 적는다.

설계는 `spec.md`, 결정은 `DECISIONS.md`, 측정은 `nlr_engineering_notes.md`를 본다.

---

## 1. 실행 환경

### Python

```bash
cd C:/Users/SSAFY/Desktop/hyanghae/EDA
./venv/Scripts/python.exe   # 시스템 python에는 pandas가 없다
```

한글 출력이 깨지면 `export PYTHONIOENCODING=utf-8`.

### Jupyter 커널이 깨져 있다 ⚠

등록된 `python3` 커널이 **없는 경로**를 가리킨다.

```
등록됨: C:\Users\SSAFY\Desktop\EDA\venv\Scripts\python.exe
실제:   C:\Users\SSAFY\Desktop\hyanghae\EDA\venv\Scripts\python.exe
```

프로젝트를 옮기면서 생긴 문제로 보인다. **VS Code나 Jupyter에서 노트북을 열면 커널이 안 뜬다.**

임시 커널로 우회할 수 있다(사용자 설정을 건드리지 않는다).

```bash
# 1. 임시 kernelspec 생성
./venv/Scripts/python.exe - <<'PY'
import json, pathlib, sys
kd = pathlib.Path("<임시디렉터리>/jupyter/kernels/venv311")
kd.mkdir(parents=True, exist_ok=True)
(kd / "kernel.json").write_text(json.dumps({
    "argv": [sys.executable, "-Xfrozen_modules=off", "-m", "ipykernel_launcher", "-f", "{connection_file}"],
    "display_name": "venv311", "language": "python"}, indent=1), encoding="utf-8")
PY

# 2. JUPYTER_PATH를 지정해 실행
export JUPYTER_PATH='<임시디렉터리>\jupyter'
./venv/Scripts/python.exe -m nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.kernel_name=venv311 --ExecutePreprocessor.timeout=1800 \
  <노트북>.ipynb
```

**근본 해결**은 `jupyter kernelspec` 재등록이지만 사용자 환경 설정이므로 임의로 바꾸지 않았다.

### GMS API 키

`.env`의 `GMS_KEY`. 만료되면 이렇게 나온다.

```
HTTP 401  {"message":"[GMS 에러] Invalid or expired GMS key"}
```

키를 읽는 것과 서버가 받아주는 것은 다르다. 키 길이가 정상이어도 401이면 **만료**다.
SSAFY GMS 포털에서 재발급받는다. 401이 나면 재시도하지 말고 사용자에게 알린다.

- Gateway `https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions`
- Model `gpt-5.4-nano`

---

## 2. 하면 안 되는 조작

### 노트북 16을 다시 실행하면 QA 판정 60건이 지워진다 🚨

`16_stage1_golden_set_quality_audit.ipynb` **cell 30**이
`analysis_outputs/16_golden_set_quality_audit_candidates.csv`를 **무조건 덮어쓰고**,
그 다음 수동 컬럼이 비어 있는지 assert한다.

```python
audit_output_df.to_csv(CANDIDATES_PATH, ...)          # 덮어씀
...
if saved[["manual_decision", ...]].ne("").any().any():
    raise RuntimeError("수동 판단 컬럼은 모두 빈 값이어야 합니다.")
```

**판정은 복사본에만 있다** — `evaluation_data/stage1/16_golden_set_quality_audit_reviewed.csv`.
원본은 비어 있는 상태로 두고 노트북 16은 실행하지 않는다.

### 노트북 13·14·15를 수정하면 15·16이 실행 불가가 된다

`15_...ipynb` cell 5가 `PROTECTED_PATHS`로 nb13·nb14·Golden Set·metrics·evaluation 파일을
해싱하고 cell 53에서 다시 해싱해 다르면 `raise`한다. `16_...ipynb` cell 3/36도 입력 7개에 같은 걸 한다.

→ 채점이나 분석을 바꿔야 하면 **새 노트북을 만든다.** 25·26번이 그 방식이다.

### 노트북 15를 처음부터 실행하면 API를 호출한다

`FORCE_RERUN = False`여도 **cell 13이 무조건 smoke test를 한 번 호출**한다.
그리고 cell 7이 `GMS_KEY` 없으면 `raise`한다.

→ 재채점만 하려면 nb15를 실행하지 말고 저장된 예측 CSV를 읽는다
(`13/14/15_*_predictions.csv`, `15_llm_stage1_checkpoint.csv`).

### 평가 데이터를 수정하지 않는다

`AGENTS.md`: *"Do not change evaluation data because a model disagrees with it.
Potential label issues should be reported separately."*

`13_stage1_golden_set_v1_200.xlsx`는 읽기 전용이다. 라벨 문제는
`analysis_outputs/16_golden_set_errata_report.md`처럼 보고서로 남긴다.

---

## 3. 새 노트북을 만들 때 쓰는 패턴

25·26번이 따르는 방식이다.

```
1  사전 등록      규칙·파라미터를 데이터 로드 셀보다 앞에 둔다
2  입력 해싱      실행 전후 SHA-256 대조. 다르면 raise
3  쓰기 가드      write_output()으로만 저장. prefix·디렉터리·보호파일 검사
4  REPORT_ONLY   True면 계산·표시만 하고 파일 0개 생성
5  재현 게이트    기존 수치를 재현하는지 먼저 확인하고, 실패하면 중단
6  체크포인트     API 응답 원본을 저장해 재호출 없이 재채점
```

**노트북을 실행하기 전에 dry-run을 한다.** 코드 셀만 뽑아 `REPORT_ONLY=True`로 돌리면
디버깅이 훨씬 빠르다.

```bash
./venv/Scripts/python.exe - <<'PY'
import json, pathlib, matplotlib; matplotlib.use("Agg")
nb = json.loads(pathlib.Path("<노트북>.ipynb").read_text(encoding="utf-8"))
g = {"__name__": "__main__"}; g["display"] = print; g["Markdown"] = lambda s: s
for i, c in enumerate(nb["cells"]):
    if c["cell_type"] != "code": continue
    s = "".join(c["source"]).replace("REPORT_ONLY = False", "REPORT_ONLY = True")
    s = s.replace("from IPython.display import Markdown, display", "pass").replace("plt.show()", "plt.close('all')")
    exec(compile(s, f"<cell {i}>", "exec"), g)
PY
```

### 한글 컬럼명 주의

`itertuples`는 한글·공백이 든 컬럼명을 `_5`, `_6` 같은 위치 이름으로 바꾼다.
**위치로 접근하면 조용히 어긋난다.** `to_dict("records")`로 컬럼명 접근을 쓴다.

---

## 4. 줄바꿈

`.gitattributes`가 `* text=auto eol=lf`로 LF를 강제한다
(*"데이터 저장소다. git이 줄바꿈을 자동 변환하면 SHA-256으로 증명한 출처가 깨진다"*).

다만 `.gitattributes`가 2026-09-10에 추가돼서 **기존 파일은 아직 작업 트리에 CRLF로 있다.**
`13_rule_stage1_metrics.csv`, `11_rule_lexicon.csv` 등 전부 CRLF다.

새로 만드는 CSV도 pandas 기본값(CRLF)으로 두면 기존 파일과 일관된다.
전체 정규화는 별도 작업이므로 개별 파일만 LF로 바꾸지 않는다.

---

## 5. 자주 쓰는 확인 명령

```bash
cd C:/Users/SSAFY/Desktop/hyanghae/EDA
export PYTHONIOENCODING=utf-8

# accord 92개와 코퍼스 지지도
./venv/Scripts/python.exe -c "
import pandas as pd
d = pd.read_csv('analysis_outputs/10_accord_dictionary.csv')
print(d[['accord','perfume_count']].head(20).to_string(index=False))"

# 보호 대상이 안 바뀌었는지
cd .. && git status --short -- EDA/evaluation_data EDA/analysis_outputs/1[0-9]_* EDA/1[0-9]_*.ipynb
```
