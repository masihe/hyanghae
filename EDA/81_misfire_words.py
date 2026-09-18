"""GPT 어휘 조사가 준 낱말을 엔진에 직접 넣어 오탐인지 가른다.

    ./venv/Scripts/python.exe -W ignore 81_misfire_words.py

**GMS 호출 0회.** 낱말을 그대로 엔진에 넣는다 — 부분 문자열 매칭이라 문장으로 감쌀
필요가 없다. 결정적이라 몇 번 돌려도 같다.

왜 이 단계가 필요한가
----------------------
80번이 조건을 걸 표면형 10개를 골랐는데 **그 근거가 작성자가 떠올린 문장 11개**였다.
어디에 걸어야 하는지를 어휘 사실로 바꾸려고 2026-09-18 GPT 조사를 받았다
(`꿀.pdf` · 표면형 36개에 대한 향 무관 낱말 목록).

**조사 결과를 그대로 믿지 않는다.** 두 가지를 이 스크립트가 가른다.

    1. 그 낱말이 실제로 엔진에서 오탐을 내는가        <- 여기서 결정적으로 가린다
    2. 그 낱말이 정말 "향과 무관" 한가                <- 사람이 판단한다. 아래 분류

조사가 요청을 벗어난 부분
--------------------------
조사에 *"그 글자열을 포함하지만 향·냄새와 무관한 낱말"* 을 요청했는데 **표면형 자체를
낱말로 낸 것이 14개**였다(`고목`->`고목` · `과육`->`과육` · `침대`->`침대` …).
표면형 자체는 사전이 의도적으로 잡으려는 대상이라 오탐 근거가 되지 않는다.

또 **향·맛 표현을 향 무관으로 분류한 것**이 있다(`새콤달콤` · `풋풋하다` · `말캉말캉` ·
`편백나무` · `흰꽃`). 사전이 그 뜻으로 매핑해 둔 것들이다.

그래서 아래 `CANDIDATES` 에 조사가 준 낱말을 전부 싣되 사람 분류를 함께 적는다.

    keep   향 무관이 맞다. 오탐 근거가 된다
    same   표면형 자체이거나 같은 뜻이다. 근거가 아니다
    scent  향·맛 표현이다. 오히려 살려야 한다

**분류는 결과를 보기 전에 정했다.**

판정 기준 (80번 changelog 에 먼저 적었다)
-------------------------------------------
    조건을 건다      `keep` 낱말이 1개 이상이고 그 낱말이 실제로 엔진에서 오탐을 내고
                    조건을 걸어도 평가셋 손실이 0건일 때
    조건을 안 건다    `keep` 낱말이 0개일 때

출력
-----
표는 표준출력에만 쓴다. 파일을 만들지 않는다 (41번 이후 관례).
"""
import collections
import sys

sys.path.insert(0, "C:/Users/SSAFY/Desktop/S15P21E203/ai")
import nlr_engine as e  # noqa: E402

LEXICON = "data/scent_knowledge/domain_lexicon_v1_14.csv"

# (표면형, 낱말, 분류, 조사가 적은 뜻)
# 2026-09-18 GPT 조사(`꿀.pdf`)가 준 것 전부. 분류는 작성자가 결과를 보기 전에 붙였다.
CANDIDATES = [
    ("꿀", "꿀꿀하다", "keep", "기분이 좋지 않다"),
    ("꿀", "꿀밤", "keep", "머리를 가볍게 때리다"),
    ("꿀", "꿀팁", "keep", "기발한 방법"),
    ("잼", "잼민이", "keep", "초등학생을 낮춰 부르는 신조어"),
    ("나무", "나무젓가락", "keep", "나무로 만든 젓가락"),
    ("나무", "나무라다", "keep", "엄하게 꾸짖다"),
    ("분내", "분내다", "keep", "화내다"),
    ("산림", "산림청", "keep", "정부 기관"),
    ("세탁", "세탁기", "keep", "세탁을 하는 기계"),
    ("세탁", "세탁소", "keep", "빨래를 세탁해 주는 가게"),
    ("우디", "우디", "keep", "토이 스토리 등장 인형 — 같은 글자지만 향과 무관"),
    ("이불", "이불킥", "keep", "부끄러워 이불을 걷어차다"),
    ("초록", "초록불", "keep", "교통 신호의 녹색 불빛"),
    ("잔디", "잔디깎기", "keep", "잔디를 깎는 일"),
    ("빨래", "빨래판", "keep", "빨래할 때 쓰던 도구"),
    ("빨래", "빨래감", "keep", "세탁할 옷감"),
    ("과즙", "과즙기", "keep", "과즙을 짜내는 기계"),
    ("잔디", "잔디밭", "keep", "잔디가 심어진 땅"),

    # 표면형 자체이거나 사전이 의도한 그 뜻이다. 오탐 근거가 아니다
    ("고목", "고목", "same", "오래된 나무 — 사전이 woody 로 매핑한 그 뜻"),
    ("과육", "과육", "same", "과일의 속 — fruity 로 매핑한 그 뜻"),
    ("과즙", "과즙", "same", "과일 즙 — citrus 로 매핑한 그 뜻"),
    ("껍질", "껍질", "same", "겉 부분 — citrus 로 매핑한 그 뜻"),
    ("당밀", "당밀", "same", "sweet 로 매핑한 그 뜻"),
    ("목재", "목재", "same", "woody 로 매핑한 그 뜻"),
    ("물기", "물기", "same", "aquatic/green 으로 매핑한 그 뜻"),
    ("생풀", "생풀", "same", "green 으로 매핑한 그 뜻"),
    ("수액", "수액", "same", "green 으로 매핑한 그 뜻"),
    ("시럽", "시럽", "same", "sweet 로 매핑한 그 뜻"),
    ("이불", "이불", "same", "powdery/soapy 로 매핑한 그 뜻"),
    ("침구", "침구", "same", "powdery/soapy 로 매핑한 그 뜻"),
    ("침대", "침대", "same", "powdery/soapy 로 매핑한 그 뜻"),
    ("톱밥", "톱밥", "same", "woody 로 매핑한 그 뜻"),
    ("해변", "해변", "same", "coconut/tropical 로 매핑한 그 뜻"),

    # 향·맛 표현이다. 오히려 살려야 한다
    ("달달", "달달하다", "scent", "맛이 달다 — caramel/sweet 로 매핑한 그 뜻"),
    ("새콤", "새콤달콤", "scent", "달콤하고 신맛 — citrus 로 매핑한 그 뜻"),
    ("말캉", "말캉말캉", "scent", "부드럽고 물컹 — fruity 로 매핑한 그 뜻"),
    ("탱글", "탱글탱글", "scent", "탱탱하다 — fruity 로 매핑한 그 뜻"),
    ("풋풋", "풋풋하다", "scent", "신선하고 상큼 — fruity 로 매핑한 그 뜻"),
    ("편백", "편백나무", "scent", "woody 로 매핑한 그 뜻"),
    ("흰꽃", "흰꽃", "scent", "흰색 꽃 — floral 로 매핑한 그 뜻"),
]

# 조사가 "없음" 으로 답한 표면형. 판정 기준상 조건을 걸지 않는다
NO_WORD = ["숲", "과숙", "상큼", "풀향"]


def main():
    index = e.load_index(lexicon_csv=LEXICON)

    print("=" * 96)
    print("GPT 어휘 조사 검증 — 낱말을 그대로 엔진에 넣는다. GMS 호출 0회")
    print("=" * 96)
    print(f"사전 {LEXICON}")
    counts = collections.Counter(c for _, _, c, _ in CANDIDATES)
    print(f"조사가 준 낱말 {len(CANDIDATES)}개 — "
          f"향 무관 {counts['keep']} · 표면형 자체 {counts['same']} · 향 표현 {counts['scent']}")
    print(f"조사가 \"없음\" 으로 답한 표면형 {len(NO_WORD)}개 — {' · '.join(NO_WORD)}")
    print()

    by_form = collections.defaultdict(lambda: {"keep": [], "same": [], "scent": []})
    for form, word, kind, meaning in CANDIDATES:
        core = sorted(e.understand(index, word, None)["core"])
        by_form[form][kind].append((word, core, meaning))

    for label, title in [("keep", "향 무관 낱말 — 오탐 근거가 되는 것"),
                         ("same", "표면형 자체 — 근거가 아니다"),
                         ("scent", "향·맛 표현 — 오히려 살려야 한다")]:
        print("=" * 96)
        print(f"■ {title}")
        print("=" * 96)
        for form in sorted(by_form):
            items = by_form[form][label]
            for word, core, meaning in items:
                mark = "오탐" if core else "매칭 안 됨"
                print(f"  [{form:4}] {word:10} -> {str(core):34} {mark:10} {meaning[:34]}")
        print()

    # ---- 판정 ----
    print("=" * 96)
    print("■ 판정 — 표면형별로 조건을 걸 것인가")
    print("=" * 96)
    print(f"{'표면형':8} {'향무관 낱말':>10} {'그중 오탐':>10}   판정")
    decided = []
    all_forms = sorted(set([f for f, _, _, _ in CANDIDATES] + NO_WORD))
    for form in all_forms:
        keeps = by_form[form]["keep"]
        misfiring = [w for w, core, _ in keeps if core]
        verdict = "조건을 건다" if misfiring else "걸지 않는다"
        if misfiring:
            decided.append(form)
        print(f"{form:8} {len(keeps):>10} {len(misfiring):>10}   {verdict}"
              f"   {' · '.join(misfiring) if misfiring else ''}")

    print()
    print(f"조건을 걸 표면형 {len(decided)}개 — {' · '.join(decided)}")
    print()
    print("80번이 고른 10개와 비교 —")
    old = {"꿀", "숲", "잼", "이불", "침구", "침대", "잔디", "초록", "해변", "나무"}
    new = set(decided)
    print(f"  둘 다        {' · '.join(sorted(old & new)) or '(없음)'}")
    print(f"  새로 들어옴   {' · '.join(sorted(new - old)) or '(없음)'}")
    print(f"  빠짐         {' · '.join(sorted(old - new)) or '(없음)'}")


if __name__ == "__main__":
    main()
