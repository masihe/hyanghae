"""오타 검문소의 보호 목록을 만든다. 사전 v1.15 기준.

    ./venv/Scripts/python.exe -W ignore 83_protected_words_v1_15.py

API 호출 0회. 사전과 kiwi 형태소 사전을 읽어 목록 파일 하나를 쓴다.

무엇을 만드나
--------------
`⑤단계 앞 오타 검문소`가 **건드리면 안 되는 낱말 목록**이다. 검문소는 사전 표면형에서
자모 한 개 떨어진 낱말을 오타로 보고 교정하는데, 그 자리에 **진짜 한국어 낱말**이
있으면 멀쩡한 요청을 부순다 [측정 기록 30번].

    향긋한 풀 느낌   ->  향긋한 꿀 느낌      `풀` 이 `꿀` 과 자모 거리 1 이다
    너무 무겁지 않게 ->  나무 무겁지 않게    `너무` 가 `나무` 와 자모 거리 1 이다
    겨울에 코트 입고 ->  겨울에 노트 입고    `코트` 가 `노트` 와 자모 거리 1 이다

이 목록에 있으면 교정하지 않는다.

왜 국어 사전 전체를 싣지 않나
------------------------------
kiwi 형태소 사전은 **529,334개**다. 그런데 검문소가 물어보는 낱말은 **사전 표면형에서
자모 한 개 떨어진 것**뿐이다. 그 밖의 낱말은 애초에 후보가 안 나와 교정되지 않는다.

    국어 낱말 전체            529,334개
    사전 표면형과 자모 거리 1      614개   <- 이것만 있으면 판정이 같다

**AI 서버에 형태소 분석기를 넣지 않아도 된다.** 4.4KB 텍스트 파일 하나면 된다.
`DECISIONS.md` N13 이 분석기를 기각한 이유(의존성 +1 · 메모리 +10MB)가 그대로 유효하다.

향 용어 예외
-------------
**국어 사전에 없는 향 전문 용어는 자동으로 보호되지 않는다.** 실측에서 `단향`(檀香,
백단향)이 `잔향` 으로 바뀌었다 — ⑤단계 입력 369개 중 4건이다.

향 용어 29개를 넣어 본 결과 위험한 것은 `단향` 하나였다. `침향`·`사향`·`몰약`·`정향`은
국어 사전에 있어 자동으로 보호되고, `통카`·`베티버`·`패출리`는 사전 표면형과 멀다.
그래서 자동 생성 목록에 **손으로 관리하는 예외 몇 개**를 더한다.

`단향` 을 사전 표면형으로 올리는 것이 더 나은 해법이지만 그것은 **사전 확장**이라
`spec.md` §7.2 의 출처 제한을 따라야 하는 별개 결정이다. 여기서는 교정만 막는다.

사전 버전이 바뀌면
-------------------
**다시 돌린다.** 표면형이 바뀌면 거리 1 인 낱말 집합도 바뀐다. 사전 버전마다 생성
스크립트를 하나씩 두는 관례(49·51·53~56·80번)와 같다.

의존성: kiwipiepy (EDA venv 에만 있다. AI 서버에는 필요 없다).
"""
from __future__ import annotations

import csv
import pathlib
import sys
import unicodedata

LEXICON = pathlib.Path("data/scent_knowledge/domain_lexicon_v1_15.csv")
OUT = pathlib.Path("data/scent_knowledge/protected_words_v1_15.txt")

# 국어 사전에 없어서 자동으로 보호되지 않는 향 전문 용어.
# **손으로 관리한다.** 새로 발견하면 여기 적고 측정 기록에 남긴다.
#
# **조사가 붙은 형태까지 넣는다.** 한국어가 교착어라 `단향` 만 적으면 `단향이` 가 따로
# 걸린다 — 실측에서 `잔향이` 로 바뀌었다. 아래 조사를 붙인 형태를 함께 생성한다.
#
# 엔진 쪽을 단순하게 두려고 여기서 펼친다. 목록 파일이 그냥 낱말 목록이면 엔진은
# `word in protected` 한 줄로 끝난다. 조사를 빠뜨리면 그 형태만 보호가 안 되는데,
# 그때의 동작은 **지금과 같다**(교정해서 ⑤단계 대신 사전 경로로 간다).
SCENT_TERM_EXCEPTIONS = [
    "단향",      # 檀香 = 백단향. `잔향` 으로 바뀐다 [측정 기록 30번 · 369개 중 4건]
]

# 예외 용어 뒤에 붙을 조사·어미. 실측에 나온 `이` 를 포함해 흔한 것만 둔다.
PARTICLES = ["", "이", "가", "은", "는", "을", "를", "의", "에", "도", "과", "와", "으로", "로"]

CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
JONG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"

MIN_LEN = 2          # 1글자는 교정 대상에서 뺀다. 후보가 너무 많다


def to_jamo(text):
    """한글을 자모로 편다. str.

    **음절이 아니라 자모로 재는 것이 이 설계의 전제다.** `빨레`/`빨래` 는 글자로는 한
    글자 차이지만 자모로는 `ㅐ`/`ㅔ` 한 개 차이다. 음절 단위로 재면 사전 표면형끼리
    충돌하는 쌍이 28쌍인데 자모 단위로는 0쌍이다 [측정 기록 30번].
    """
    out = []
    for ch in unicodedata.normalize("NFC", str(text)):
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:
            out.append(CHO[code // 588])
            out.append(JUNG[(code % 588) // 28])
            jong = JONG[code % 28]
            if jong != " ":
                out.append(jong)
        else:
            out.append(ch)
    return "".join(out)


def edit_distance_at_most(a, b, cap=1):
    """레벤슈타인 거리가 cap 이하면 그 값, 넘으면 cap+1. int.

    전체를 계산하지 않고 cap 을 넘는 순간 끊는다. 표면형 208개 x 낱말 53만 개를
    비교하므로 이 가지치기가 없으면 끝나지 않는다.
    """
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > cap:
            return cap + 1
        prev = cur
    return prev[-1]


def load_surface_forms(path):
    """사전의 표면형 전부. dict[str, set[str]] (표면형 -> 대표 표현).

    `nlr_engine.load_index` 와 같은 규칙으로 읽는다 — `expression` 과 `aliases` 를
    모두 쓰고 `status` 로 거르지 않는다. 엔진이 거르지 않으므로 여기서도 거르면 안 된다.
    """
    surface = {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            variants = [row["expression"]] + [
                a for a in (row["aliases"] or "").split("|") if a]
            for form in variants:
                if form:
                    surface.setdefault(form, set()).add(row["expression"])
    return surface


def korean_morphemes():
    """kiwi 형태소 사전의 모든 형태. set[str].

    **`tokenize()` 로는 안 된다.** 분석기가 모르는 글자 조합도 `NNG` 로 찍는다
    (`뷁쿱/NNG` · `츄릅삥/NNG`). 미등록 태그가 붙지 않아 등재 여부를 알 수 없다.
    `morpheme(i)` 를 0부터 훑어 사전 자체를 읽는다.
    """
    from kiwipiepy import Kiwi

    kiwi = Kiwi()
    forms = set()
    index = 0
    misses = 0
    while misses < 50:                 # 번호가 연속이 아니라 빈 자리를 건너뛴다
        try:
            forms.add(kiwi.morpheme(index).form)
            misses = 0
        except ValueError:
            misses += 1
        index += 1
    return forms


def build(surface, known):
    """보호할 낱말 목록. list[str].

    검문소가 교정 후보로 삼는 것은 **띄어쓰기 없는 표면형 중 2글자 이상**이다.
    거기서 자모 거리 1 인 국어 낱말만 담으면 판정이 사전 전체를 쓴 것과 같아진다.
    """
    targets = {f: to_jamo(f) for f in surface
               if " " not in f and len(f) >= MIN_LEN}
    lengths = {len(v) for v in targets.values()}

    out = []
    for word in known:
        if word in surface:
            continue                   # 사전에 있는 말은 애초에 교정 대상이 아니다
        jamo = to_jamo(word)
        if not any(abs(len(jamo) - L) <= 1 for L in lengths):
            continue                   # 길이만 봐도 거리 1 이 될 수 없다
        if any(edit_distance_at_most(jamo, g) == 1 for g in targets.values()):
            out.append(word)
    return targets, out


def main():
    if not LEXICON.is_file():
        sys.exit(f"사전이 없다: {LEXICON}")

    surface = load_surface_forms(LEXICON)
    known = korean_morphemes()
    targets, auto = build(surface, known)

    expanded = [term + p for term in SCENT_TERM_EXCEPTIONS for p in PARTICLES]
    manual = [w for w in expanded if w not in auto and w not in surface]
    skipped = [w for w in expanded if w in auto or w in surface]
    words = sorted(set(auto) | set(manual))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(words) + "\n", encoding="utf-8", newline="\n")

    print(f"사전 표면형        {len(surface)}개")
    print(f"  교정 후보 대상   {len(targets)}개 (띄어쓰기 없고 {MIN_LEN}글자 이상)")
    print(f"국어 형태소        {len(known):,}개")
    print()
    print(f"자동 생성          {len(auto)}개")
    print(f"향 용어 예외       {len(manual)}개  {' · '.join(manual) if manual else ''}")
    if skipped:
        print(f"  예외인데 불필요   {' · '.join(skipped)} (이미 보호되거나 사전에 있다)")
    print(f"합계              {len(words)}개  ->  {OUT}")
    print(f"파일 크기          {OUT.stat().st_size / 1024:.1f}KB")


if __name__ == "__main__":
    main()
