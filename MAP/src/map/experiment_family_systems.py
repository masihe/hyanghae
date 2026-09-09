"""Family 체계 7 / 8A / 8B / 9 를 정의한다 (모듈. 직접 실행하지 않는다).

**왜 이 모듈인가.** Phase 0 의 9계열은 PROVISIONAL 이다. Fragrance Wheel 7계열을 뼈대로
하고 휠에 없는 Gourmand·Musk/Powdery 를 IFRA primary descriptor 근거로 추가한 후보안이며,
**9라는 숫자가 실험으로 최적임이 검증된 적은 없다.** 그래서 계열 개수를 실험 변수로 둔다.

**draft-1 은 읽기만 한다.** experiment_phase0_family_mapping.py 의 ACCORD_FAMILY 를
그대로 쓰고, 팀이 결정한 2건만 오버라이드해 reviewed-1 을 만든다. 그러면 Phase 0 의
재현 검증(특히 experiment_phase0_snapshot.py 의 cross-family 435 assert)이 계속 통과한다.

    aldehydic  MUSK -> FLORAL     (팀 결정)
    fresh      CITRUS -> MODIFIER (팀 결정. 특정 계열에 강제 배정하지 않는다)

**MODIFIER 와 no-family-signal 을 구분한다** (팀 결정. UNCLASSIFIED 는 쓰지 않는다).

    MODIFIER          계열 점수 계산에서 제외한 cross-family 특성. accord 데이터는 그대로 남는다
    UNMAPPED          향 계열로 볼 근거가 없는 11종 (plastic rubber vinyl …). modifier 와 별도 집계
    no-family-signal  계열 점수 총량이 0 인 향수. argmax 계열이 없다

**계열 해체는 억지 배정 대신 modifier 로 한다** (기본안). Gourmand·Musk 를 독립 영역에서
빼면 실제로 어떤 정보가 사라지는지 그대로 재는 것이 이번 실험의 중심 질문이기 때문이다.
Amber 병합은 민감도 변형(8A-A / 8B-A / 7-A)으로 따로 돌려 기본안과 대비한다.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "common")))
import experiment_phase0_family_mapping as fm

MAPPING_VERSION = "reviewed-1"
MODIFIER = "MODIFIER"
UNMAPPED = fm.UNMAPPED
NO_SIGNAL = "NO_FAMILY_SIGNAL"

# 팀이 결정한 draft-1 오버라이드. 이 2건이 draft-1 과의 전체 차이다.
REVIEWED_OVERRIDES = {
    "aldehydic": ("FLORAL", "팀 결정 — 알데하이드는 플로럴 축으로 본다 (draft-1 은 MUSK)"),
    "fresh": (MODIFIER, "팀 결정 — 어느 축의 신선함인지 데이터가 구분하지 않으므로 "
                        "특정 계열에 강제 배정하지 않고 cross-family modifier 로 둔다 "
                        "(draft-1 은 CITRUS)"),
}

# 민감도 변형에서 Amber 로 병합할 MUSK accord. 나머지 MUSK accord 는 modifier 로 남는다.
MUSK_TO_AMBER = ("musky", "animalic")

SYSTEMS = {
    "S9": {
        "label": "9계열", "short": "9",
        "musk": "keep", "gourmand": "keep", "group": "base",
        "note": "Phase 0 PROVISIONAL 초안. 휠 7계열 + IFRA 근거 2계열",
    },
    "S8A": {
        "label": "8A — 7계열 + Gourmand", "short": "8A",
        "musk": "modifier", "gourmand": "keep", "group": "base",
        "note": "Musk/Powdery 를 독립 영역에서 뺀다. 해당 accord 는 modifier",
    },
    "S8B": {
        "label": "8B — 7계열 + Musk/Powdery", "short": "8B",
        "musk": "keep", "gourmand": "modifier", "group": "base",
        "note": "Gourmand 를 독립 영역에서 뺀다. 해당 accord 20종은 modifier",
    },
    "S7": {
        "label": "7계열 — 휠 기반만", "short": "7",
        "musk": "modifier", "gourmand": "modifier", "group": "base",
        "note": "Fragrance Wheel 에 대응이 있는 7계열만. 두 계열 모두 modifier 로 해체",
    },
    "S8A_A": {
        "label": "8A-A — 8A + musky·animalic→Amber", "short": "8A-A",
        "musk": "amber", "gourmand": "keep", "group": "sensitivity",
        "note": "민감도. musky·animalic 을 Amber 로 병합, powdery·soapy·metallic 은 modifier",
    },
    "S8B_A": {
        "label": "8B-A — 8B + Gourmand→Amber", "short": "8B-A",
        "musk": "keep", "gourmand": "amber", "group": "sensitivity",
        "note": "민감도. Gourmand accord 20종을 Amber 로 병합",
    },
    "S7_A": {
        "label": "7-A — 7 + 둘 다 Amber", "short": "7-A",
        "musk": "amber", "gourmand": "amber", "group": "sensitivity",
        "note": "민감도. musky·animalic 과 Gourmand 20종을 모두 Amber 로 병합",
    },
}
BASE_SYSTEMS = [k for k, v in SYSTEMS.items() if v["group"] == "base"]
SENSITIVITY_SYSTEMS = [k for k, v in SYSTEMS.items() if v["group"] == "sensitivity"]
SYSTEM_ORDER = BASE_SYSTEMS + SENSITIVITY_SYSTEMS

LOW_MASS_THRESHOLDS = (0.20, 0.30, 0.50)   # 임계값을 하나로 고정하지 않는다
SMALL_FAMILY_THRESHOLDS = {"korea200": (10, 20), "global1000": (50, 100)}


def reviewed_mapping():
    """reviewed-1 의 accord -> 계열. draft-1 에 오버라이드 2건만 적용한다."""
    out = {a: f for a, (f, _r) in fm.ACCORD_FAMILY.items()}
    for accord, (target, _why) in REVIEWED_OVERRIDES.items():
        assert accord in out, f"draft-1 에 없는 accord 를 오버라이드할 수 없다: {accord}"
        out[accord] = target
    return out


def mapping_diff():
    """draft-1 대비 변경 목록. 검증용 — 2건이어야 한다."""
    base = {a: f for a, (f, _r) in fm.ACCORD_FAMILY.items()}
    rev = reviewed_mapping()
    return [{"accord": a, "draft_1": base[a], "reviewed_1": rev[a],
             "reason": REVIEWED_OVERRIDES[a][1]}
            for a in sorted(rev) if base[a] != rev[a]]


def accords_of(family, mapping=None):
    mapping = mapping or reviewed_mapping()
    return sorted(a for a, f in mapping.items() if f == family)


def resolve_system(key):
    """체계 하나의 accord -> 계열 배정과 modifier 집합을 만든다.

    반환: (assign, families, modifiers)
      assign    accord -> 계열 | MODIFIER | UNMAPPED
      families  살아남은 계열 목록 (fm.FAMILY_ORDER 순서 — 색을 체계 간 공유하려면 이 순서)
      modifiers 계열 점수에서 제외되는 accord 집합 (UNMAPPED 제외)
    """
    spec = SYSTEMS[key]
    assign = dict(reviewed_mapping())

    if spec["musk"] == "modifier":
        for a in accords_of("MUSK", assign):
            assign[a] = MODIFIER
    elif spec["musk"] == "amber":
        for a in accords_of("MUSK", assign):
            assign[a] = "AMBER" if a in MUSK_TO_AMBER else MODIFIER

    if spec["gourmand"] == "modifier":
        for a in accords_of("GOURMAND", assign):
            assign[a] = MODIFIER
    elif spec["gourmand"] == "amber":
        for a in accords_of("GOURMAND", assign):
            assign[a] = "AMBER"

    families = [f for f in fm.FAMILY_ORDER if any(v == f for v in assign.values())]
    modifiers = {a for a, v in assign.items() if v == MODIFIER}
    return assign, families, modifiers


def family_scores(accord_lists, key):
    """FS1(raw strength 합) 기준 계열 점수와 정보 손실 지표.

    Phase 0 의 experiment_phase0_family_score.score_matrix 와 같은 FS1 정의를 쓰되,
    modifier 를 명시적으로 다루고 family_mass / accord_mass / modifier_mass 를 함께 낸다.
    기존 함수 시그니처는 건드리지 않는다 (Phase 0 스크립트가 그대로 돌아야 한다).
    """
    assign, families, modifiers = resolve_system(key)
    index = {f: i for i, f in enumerate(families)}
    n = len(accord_lists)

    raw = np.zeros((n, len(families)), dtype=np.float64)
    accord_mass = np.zeros(n)
    modifier_mass = np.zeros(n)
    unmapped_mass = np.zeros(n)
    for r, lst in enumerate(accord_lists):
        for name, strength in lst:
            accord_mass[r] += strength
            target = assign.get(name, UNMAPPED)
            if target == MODIFIER:
                modifier_mass[r] += strength
            elif target == UNMAPPED:
                unmapped_mass[r] += strength
            else:
                raw[r, index[target]] += strength

    family_mass = raw.sum(axis=1)
    no_signal = family_mass <= 0
    M = raw / np.maximum(family_mass[:, None], 1e-12)

    srt = np.sort(M, axis=1)
    top1 = srt[:, -1].copy()
    top2 = srt[:, -2].copy() if len(families) >= 2 else np.zeros(n)
    argmax = np.array([families[i] for i in M.argmax(axis=1)], dtype=object)
    # 계열 신호가 없으면 argmax·top1·margin 을 만들지 않는다 (없는 값을 만들어 쓰지 않는다)
    argmax[no_signal] = NO_SIGNAL
    top1[no_signal] = np.nan
    top2[no_signal] = np.nan

    with np.errstate(divide="ignore", invalid="ignore"):
        mass_ratio = np.where(accord_mass > 0, family_mass / accord_mass, np.nan)
        mod_ratio = np.where(accord_mass > 0, modifier_mass / accord_mass, np.nan)

    return {
        "system": key,
        "families": families,
        "modifiers": sorted(modifiers),
        "M": M,
        "argmax": argmax,
        "top1": top1,
        "top2": top2,
        "margin": top1 - top2,
        "family_mass": family_mass,
        "accord_mass": accord_mass,
        "modifier_mass": modifier_mass,
        "unmapped_mass": unmapped_mass,
        "family_mass_ratio": mass_ratio,
        "modifier_mass_ratio": mod_ratio,
        "no_signal": no_signal,
    }


def system_summary(key):
    """체계 하나의 구성 요약 (계열 수, 계열별 accord 수, modifier 목록)."""
    assign, families, modifiers = resolve_system(key)
    spec = SYSTEMS[key]
    return {
        "key": key, "label": spec["label"], "short": spec["short"],
        "group": spec["group"], "note": spec["note"],
        "musk_policy": spec["musk"], "gourmand_policy": spec["gourmand"],
        "family_count": len(families),
        "families": families,
        "families_ko": [fm.FAMILY_DEF[f][0] for f in families],
        "accords_per_family": {f: len(accords_of(f, assign)) for f in families},
        "modifier_accords": sorted(modifiers),
        "modifier_count": len(modifiers),
        "unmapped_accords": sorted(a for a, v in assign.items() if v == UNMAPPED),
    }
