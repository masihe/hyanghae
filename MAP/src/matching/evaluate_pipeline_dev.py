"""파이프라인 산출물을 옛 ID 공간으로 번역해 기존 DEV 평가를 그대로 돌린다 (9b · 9c).

Run with venv/Scripts/python.exe src/matching/evaluate_pipeline_dev.py

측정 대상은 retrieval(R@k)이 아니라 **자동 확정 정확도**다.
`evaluate_brand_mapping_dev.py` 가 이미 retrieval 을 쟀고, 그 값이 파이프라인에도
성립함은 별도로 확인했다(평가 관련 컬럼이 DEV 77건 전부 동일).

여기서 새로 아는 것은 파이프라인이 실제로 내리는 MATCH / MATCH_REVIEW / NO_MATCH 판정의
정확도다. 이 값이 10단계 Verification 의 비교 기준선이 된다.

기존 평가 스크립트·Gold Set·LLM 고정본을 하나도 수정하지 않는다.
새 identity 파일을 옛 ID 공간으로 번역해 스크래치에 쓰고, 출력 경로만 갈아끼워 실행한다.

세 상태를 같은 조건으로 잰다.

  1. `before`  브랜드 매핑 반영 직전 동결 스냅샷, LLM 채널 없음 (재현 게이트)
  2. `brandmap` 브랜드 매핑 반영, LLM 채널 없음 (9b)
  3. `brandmap+llm` 브랜드 매핑 + LLM 이름 채널 (9c)

`run()` 이 실행마다 `matcher.LLM_KO_LATIN_NAMES` 를 명시적으로 갈아끼우고 되돌린다.
켜는 것은 3번뿐이다. import 부작용으로 채널을 끄지 않는다.
"""
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "korea"))
import build_korea_popularity_map as matcher
import evaluate_fragrantica_matcher_dev as baseline
import identity_remap as ir

ROOT = Path(__file__).resolve().parents[2]  # MAP/
DATA = ROOT / "data/korea_popularity"
NEW_COMMERCIAL = DATA / "korea_commercial_identities_brandmap.csv"

# 브랜드 매핑 반영 직전 스냅샷으로 돌린 결과. 하드코딩된 표시용 숫자가 아니라
# 매 실행마다 스냅샷에서 다시 만들어 대조하는 재현 게이트다 (9a-4).
EXPECTED_BEFORE = {
    "auto": 24, "correct": 17, "false": 7, "review": 8, "no_match": 45,
}
# 9b 로 기록한 값. 브랜드 매핑만 반영하고 LLM 채널은 없는 상태다.
EXPECTED_BRANDMAP = {
    "auto": 28, "correct": 20, "false": 8, "review": 9, "no_match": 40,
}
# 9c 로 기록한 값. 브랜드 매핑 + LLM 채널, Verification 없음.
EXPECTED_LLM = {
    "auto": 41, "correct": 33, "false": 8, "review": 9, "no_match": 27,
}
# 10b 로 기록한 값. Verification(기준 E) 적용, 사람 검토 확정 없음.
EXPECTED_VERIFIED = {
    "auto": 25, "correct": 23, "false": 2, "review": 25, "no_match": 27,
}
# 프로덕션 LLM 이름 표현 / 사람 검토 확정. run(...) 인자로만 켠다.
LLM_NAMES = dict(matcher.LLM_KO_LATIN_NAMES) or baseline.LLM_KO_LATIN_NAMES_PRODUCTION
HUMAN_CONFIRMATIONS = dict(matcher.REVIEWED_CONFIRMATIONS)

# 사람 검토(10d)가 DEV Gold 를 근거로 인용한 행이 있어, 그 뒤 DEV 수치는 이 override 의
# 품질을 재는 데 쓸 수 없다. 몇 건이 겹치는지 실행 시점에 세어 함께 보고한다.
GOLD_CONTAMINATED_NOTE = (
    "사람 검토가 DEV Gold 를 근거로 인용했다. 아래 +human 열은 override 품질의 측정이 아니다.")

# 10c 회귀 테스트 — 과거에 오매칭이었던 건이 다시 오매칭이 되지 않는지 본다.
# 기대값은 "정답으로 확정" 또는 "확정하지 않음" 이다. **오확정이면 실패다.**
# 네 건 모두 DEV Gold 에 라벨이 있어 정답을 알 수 있다.
REGRESSION_CASES = {
    "D078": "Clean 클래식 쿨 코튼 — 과거 Classic *Warm* Cotton 으로 오확정",
    "D016": "Miss Dior EDP — 과거 1947년 Miss Dior 로 오확정",
    "D022": "Le Sel d'Issey EDP — 과거 EDT 항목으로 오확정",
    "D062": "Versace 에로스 에너지 — 과거 Eros Najim 으로 오확정",
    "D012": "Le Sel d'Issey EDT — 위 EDP 와 갈라져야 한다",
    "D047": "Miss Dior 블루밍 부케 EDT — 과거 연도 변형으로 오확정",
}


def run(commercial_path: Path, out_dir: Path, llm: bool = False,
        verification: bool = False, human: bool = False) -> pd.DataFrame:
    """경로·LLM 채널·Verification·사람 검토 확정 유무만 갈아끼워 실행한다. 로직은 그대로다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = (baseline.COMMERCIAL_PATH, baseline.RESULTS_PATH, baseline.REPORT_PATH,
             matcher.LLM_KO_LATIN_NAMES, matcher.VERIFICATION_ENABLED,
             matcher.REVIEWED_CONFIRMATIONS)
    baseline.COMMERCIAL_PATH = commercial_path
    baseline.RESULTS_PATH = out_dir / baseline.RESULTS_PATH.name
    baseline.REPORT_PATH = out_dir / baseline.REPORT_PATH.name
    matcher.LLM_KO_LATIN_NAMES = LLM_NAMES if llm else {}
    matcher.VERIFICATION_ENABLED = verification
    matcher.REVIEWED_CONFIRMATIONS = HUMAN_CONFIRMATIONS if human else {}
    try:
        baseline.main()
        return pd.read_csv(baseline.RESULTS_PATH, keep_default_na=False)
    finally:
        (baseline.COMMERCIAL_PATH, baseline.RESULTS_PATH, baseline.REPORT_PATH,
         matcher.LLM_KO_LATIN_NAMES, matcher.VERIFICATION_ENABLED,
         matcher.REVIEWED_CONFIRMATIONS) = saved


def confirmation_stats(results: pd.DataFrame) -> dict:
    def flag(col):
        return results[col].astype(str).str.lower().isin(["true", "1"])
    auto = int((results.predicted_status == "MATCH").sum())
    correct = int(flag("correct_auto_match").sum())
    false = int(flag("false_auto_match").sum())
    return {
        "auto": auto, "correct": correct, "false": false,
        "review": int((results.predicted_status == "MATCH_REVIEW").sum()),
        "no_match": int((results.predicted_status == "NO_MATCH").sum()),
        "precision": round(correct / auto, 4) if auto else 0.0,
    }


def main() -> None:
    baseline.verify_snapshot()
    protected = [baseline.GOLD_PATH, baseline.COMMERCIAL_PATH,
                 DATA / "evaluation/fragrantica_matcher_baseline_dev_results.csv",
                 DATA / "evaluation/llm_ko_to_latin_outputs.csv"]
    before_hashes = {p: baseline.sha256(p) for p in protected}

    ir.describe()
    new = pd.read_csv(NEW_COMMERCIAL, keep_default_na=False)
    translated, dropped = ir.as_old_ids(new)
    print(f"파이프라인 identity {len(new)}행 -> 옛 ID 공간 {len(translated)}행 "
          f"(되돌릴 수 없어 제외 {len(dropped)}건: {dropped})")

    gold = pd.read_csv(baseline.GOLD_PATH, encoding="utf-8-sig", keep_default_na=False)
    eligible = gold[baseline.as_bool(gold.evaluation_eligible)]
    missing = sorted(set(eligible.commercial_identity_id) - set(translated.commercial_identity_id))
    assert not missing, f"평가 대상이 번역 프레임에 없다: {missing}"
    print(f"DEV 평가 대상 {len(eligible)}건 전부 번역 프레임에 존재")

    with tempfile.TemporaryDirectory(prefix="pipeline_dev_") as tmp:
        tmp = Path(tmp)
        print()
        print("=== 재현 게이트: 동결 스냅샷으로 변경 전 상태를 다시 만든다 ===")
        before = run(baseline.COMMERCIAL_PATH, tmp / "before")
        stats_before = confirmation_stats(before)
        drift = {k: (EXPECTED_BEFORE[k], stats_before[k])
                 for k in EXPECTED_BEFORE if EXPECTED_BEFORE[k] != stats_before[k]}
        if drift:
            raise RuntimeError(f"변경 전 재현 실패. 여기서 멈춘다: {drift}")
        print(f"변경 전 재현 확인: {EXPECTED_BEFORE} 일치")

        path = tmp / "korea_commercial_identities.csv"
        translated.to_csv(path, index=False)
        print()
        print("=== 브랜드 매핑 반영, LLM 채널 없음 (9b 재현 게이트) ===")
        brandmap = run(path, tmp / "brandmap")
        stats_brandmap = confirmation_stats(brandmap)
        drift = {k: (EXPECTED_BRANDMAP[k], stats_brandmap[k])
                 for k in EXPECTED_BRANDMAP if EXPECTED_BRANDMAP[k] != stats_brandmap[k]}
        if drift:
            raise RuntimeError(f"9b 재현 실패. LLM 채널이 채널 없는 경로를 바꿨다: {drift}")
        print(f"9b 재현 확인: {EXPECTED_BRANDMAP} 일치")

        covered = set(LLM_NAMES) & set(new.commercial_identity_id)
        print()
        print(f"=== 브랜드 매핑 + LLM 이름 채널 (9c) — 표현 보유 {len(covered)}/{len(new)} identity ===")
        llm = run(path, tmp / "brandmap_llm", llm=True)
        stats_llm = confirmation_stats(llm)
        drift = {k: (EXPECTED_LLM[k], stats_llm[k])
                 for k in EXPECTED_LLM if EXPECTED_LLM[k] != stats_llm[k]}
        if drift:
            raise RuntimeError(f"9c 재현 실패. Verification 이 꺼진 경로를 바꿨다: {drift}")
        print(f"9c 재현 확인: {EXPECTED_LLM} 일치")

        print()
        print("=== 위 + Verification (10b, 기준 E) ===")
        verified = run(path, tmp / "verified", llm=True, verification=True)
        stats_verified = confirmation_stats(verified)
        drift = {k: (EXPECTED_VERIFIED[k], stats_verified[k])
                 for k in EXPECTED_VERIFIED if EXPECTED_VERIFIED[k] != stats_verified[k]}
        if drift:
            raise RuntimeError(f"10b 재현 실패: {drift}")
        print(f"10b 재현 확인: {EXPECTED_VERIFIED} 일치")

        print()
        print(f"=== 위 + 사람 검토 확정 {len(HUMAN_CONFIRMATIONS)}건 (10d) ===")
        print(f"  주의: {GOLD_CONTAMINATED_NOTE}")
        human = run(path, tmp / "human", llm=True, verification=True, human=True)

    stats_human = confirmation_stats(human)
    print()
    print("=== 자동 확정 정확도 (DEV Gold 61 MATCH / 77 평가 대상) ===")
    labels = ("before", "brandmap", "+llm", "+verify", "+human*")
    states = (stats_before, stats_brandmap, stats_llm, stats_verified, stats_human)
    print(f"  {'항목':<12}" + "".join(f"{x:>10}" for x in labels))
    for key in ("auto", "correct", "false", "review", "no_match", "precision"):
        print(f"  {key:<12}" + "".join(f"{s[key]:>10}" for s in states))
    print()
    print(f"  잘못 확정: {stats_before['false']} -> {stats_brandmap['false']} -> "
          f"{stats_llm['false']} -> {stats_verified['false']} -> {stats_human['false']}건")
    print(f"  * {GOLD_CONTAMINATED_NOTE}")

    # LLM 채널이 무엇을 바꿨는지 행 단위로 본다. 총계만으로는 상쇄가 보이지 않는다.
    key_cols = ["predicted_status", "predicted_fragrantica_id"]
    left = llm.set_index("queue_id")[key_cols + ["gold_status", "gold_fragrantica_id",
                                                 "correct_auto_match"]]
    right = human.set_index("queue_id")[key_cols]
    changed = left.index[(left[key_cols].astype(str) != right[key_cols].astype(str)).any(axis=1)]
    print()
    print(f"=== Verification + 사람 검토로 판정이 바뀐 DEV identity {len(changed)}건 ===")
    if len(changed):
        print(f"  {'queue':<7}{'gold':<10}{'전':<14}{'후':<15}{'취소된 확정이 정답이었나'}")
        for q in changed:
            a, b = left.loc[q], right.loc[q]
            was = str(a.correct_auto_match).lower() in ("true", "1")
            print(f"  {q:<7}{a.gold_status:<10}{a.predicted_status:<14}{b.predicted_status:<15}"
                  f"{'정답을 잃음' if was else '오확정을 막음'}")
        lost = sum(1 for q in changed
                   if str(left.loc[q].correct_auto_match).lower() in ("true", "1"))
        print(f"  -> 정답 손실 {lost}건 / 오확정 차단 {len(changed) - lost}건")

    print()
    print("=== 10c 회귀 테스트 — 과거 오매칭이 다시 오확정되지 않는가 ===")
    view = human.set_index("queue_id")
    failures = []
    print(f"  {'queue':<7}{'판정':<14}{'결과':<12}설명")
    for q, label in REGRESSION_CASES.items():
        if q not in view.index:
            failures.append((q, "DEV 결과에 없음")); continue
        r = view.loc[q]
        gold, pred = str(r.gold_fragrantica_id), str(r.predicted_fragrantica_id)
        if r.predicted_status != "MATCH":
            verdict = "확정 안 함"
        elif gold not in ("", "nan") and pred not in ("", "nan") and float(gold) == float(pred):
            verdict = "정답 확정"
        else:
            verdict = "오확정"
            failures.append((q, f"{label} -> {pred} (정답 {gold})"))
        print(f"  {q:<7}{r.predicted_status:<14}{verdict:<12}{label}")
    if failures:
        print()
        print(f"  ** 회귀 {len(failures)}건 **")
        for q, why in failures:
            print(f"    {q}: {why}")
    else:
        print(f"  {len(REGRESSION_CASES)}건 전부 통과 (정답 확정 또는 확정 안 함)")

    for path, digest in before_hashes.items():
        assert baseline.sha256(path) == digest, f"보호 대상이 변경됐다: {path}"
    print()
    print("보호 대상 4개(Gold, 옛 identity, baseline 결과, LLM 고정본) SHA-256 불변 확인")


if __name__ == "__main__":
    main()
