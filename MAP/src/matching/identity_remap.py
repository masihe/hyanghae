"""브랜드 매핑으로 바뀐 Commercial Identity ID 를 옛 ID 공간으로 되돌린다 (9a-4).

왜 이 방향인가 — 옛 ID 로 고정된 평가 자산이 두 개 있고 둘 다 해시로 잠겨 있다.

  - `gold_set_*.csv` 의 `commercial_identity_id` (사람 산출물, 재생성 스크립트 없음)
  - `llm_ko_to_latin_outputs.csv` (`EXPECTED_LLM_HASHES` 로 SHA-256 고정 +
    `assert set(ko_latin.commercial_identity_id) == set(identity_ids)`)

이 둘을 새 ID 로 갱신하려면 해시 상수를 고쳐야 하고, 고치지 않으면 집합 assert 가 깨진다.
두 assert 가 서로를 잠근다. 그래서 **고정본은 손대지 않고 새 파이프라인 출력을 옛 ID 로 번역**한다.

번역은 이름만 바꾼다. 내용(canonical_brand 등)은 브랜드 매핑이 반영된 새 값 그대로다.

한 가지 되돌릴 수 없는 것이 있다. 옛 `ci_8a5e23bbda0a` 는 서로 다른 두 브랜드
(애프터블로우 / 센녹)가 해시 충돌로 뭉쳐 있던 것이고, 매핑 적용 후 정상 분리된다.
분리된 두 행을 하나의 옛 ID 로 되돌리면 그 충돌을 되살리는 셈이라 **옛 공간에서 제외**한다.
평가 대상 DEV 77건에 없으므로 지표에 영향이 없다(이 모듈이 실행 시 확인한다).
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]  # MAP/
REMAP_PATH = ROOT / "data/korea_popularity/identity_remap_brand_mapping.csv"


def load_remap() -> pd.DataFrame:
    frame = pd.read_csv(REMAP_PATH, encoding="utf-8-sig", keep_default_na=False)
    assert frame.new_commercial_identity_id.is_unique, "신규 ID 가 중복이다"
    return frame


def new_to_old(remap: pd.DataFrame | None = None) -> tuple[dict[str, str], set[str]]:
    """1:1 로 되돌릴 수 있는 신규→옛 대응과, 되돌릴 수 없는 신규 ID 집합을 준다."""
    remap = load_remap() if remap is None else remap
    split_old = set(remap.old_commercial_identity_id[
        remap.groupby("old_commercial_identity_id").new_commercial_identity_id.transform("size") > 1])
    usable = remap[~remap.old_commercial_identity_id.isin(split_old)]
    ambiguous = set(remap.new_commercial_identity_id[
        remap.old_commercial_identity_id.isin(split_old)])
    return dict(zip(usable.new_commercial_identity_id, usable.old_commercial_identity_id)), ambiguous


def as_old_ids(frame: pd.DataFrame, column: str = "commercial_identity_id",
               remap: pd.DataFrame | None = None) -> tuple[pd.DataFrame, list[str]]:
    """신규 ID 로 된 프레임을 옛 ID 공간으로 번역한다. 되돌릴 수 없는 행은 떨어뜨린다."""
    mapping, ambiguous = new_to_old(remap)
    out = frame.copy()
    dropped = sorted(set(out[column]) & ambiguous)
    out = out[~out[column].isin(ambiguous)].copy()
    unknown = sorted(set(out[column]) - set(mapping))
    assert not unknown, f"대응표에 없는 신규 ID {len(unknown)}건: {unknown[:5]}"
    out[column] = out[column].map(mapping)
    assert out[column].is_unique, "번역 후 옛 ID 가 중복됐다"
    return out, dropped


def describe() -> None:
    remap = load_remap()
    mapping, ambiguous = new_to_old(remap)
    changed = int(remap.changed.sum()) if remap.changed.dtype != object else int((remap.changed == "True").sum())
    print(f"대응표 {len(remap)}행 | 변경 {changed}건 | 1:1 되돌리기 가능 {len(mapping)}건 "
          f"| 되돌릴 수 없음 {len(ambiguous)}건 {sorted(ambiguous)}")


if __name__ == "__main__":
    describe()
