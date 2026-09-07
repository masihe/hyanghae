"""한국 인기 신호 기반 대표 향수 선정과 향 지도 생성.

기존 구매/화해 판정 파일은 읽기만 한다. 구매-화해 overlap과
Commercial Identity-Fragrantica 매칭은 서로 독립된 상태로 보존한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.decomposition import PCA
from sklearn.manifold import trustworthiness
from sklearn.metrics import silhouette_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
import scent_map as sm


ROOT = Path(__file__).resolve().parents[2]  # MAP/
DATA_DIR = ROOT / "data" / "korea_popularity"
RESULTS_DIR = ROOT / "results"
OUTPUT_DIR = ROOT / "output"

PURCHASE_PATH = DATA_DIR / "korea_personal_fragrance_mixed_purchase_candidates.csv"
HWAHAE_PATH = DATA_DIR / "hwahae_personal_fragrance_mixed_overlap.csv"
PERFUME_PATH = ROOT / "perfumes.csv"

INPUT_HASHES = {
    PURCHASE_PATH: "a9cf7d7f73526ada7447e2fa9ea66ead95b0ebec16be3cc40d567693483963aa",
    HWAHAE_PATH: "323e42a736d18fa7052897f416bbb4c73e86fb169854add78d0b8dd5783a0298",
    PERFUME_PATH: "cec1ea0b498853032bcf44d33ad52ac83e2ed2896b67d5a2765d90a0345cc055",
}

MEMBERS_OUT = DATA_DIR / "korea_commercial_identity_members.csv"
COMMERCIAL_OUT = DATA_DIR / "korea_commercial_identities.csv"
FAMILY_OUT = DATA_DIR / "korea_candidate_families.csv"
MAP_IDENTITIES_OUT = DATA_DIR / "korea_map_identities.csv"
TOP200_OUT = DATA_DIR / "korea_representative_perfumes_top200.csv"
RESERVE_OUT = DATA_DIR / "korea_representative_perfumes_reserve20.csv"
REPORT_OUT = DATA_DIR / "korea_representative_perfumes_report.md"
LAYOUT_OUT = RESULTS_DIR / "korea_layout_comparison.csv"
CLUSTER_OUT = RESULTS_DIR / "korea_cluster_comparison.csv"
MAP_OUT = OUTPUT_DIR / "korea_scent_map_v1.json"

ALLOWED_MATCH_STATUS = {"MATCH", "MATCH_REVIEW", "NO_MATCH"}

# progressive_match 의 조기 종료 기준. 고유 Fragrantica ID 가 이 수에 도달하면
# 나머지 family 를 시도하지 않는다. `None` 이면 큐의 669개 family 를 전부 시도한다.
#
# 220 에서 None 으로 바꿨다 (2026-09-07, D15 결정). 이유는 여유분이다 —
# 220 이면 map_ready 225 개 중 200 개를 뽑아 여유가 5건뿐이고, None 이면 279 개 중
# 200 개라 여유가 60건이다. 10단계 Verification 이 확정을 걷어내므로 여유분이 필요하다.
# TOP200 구성은 두 경우가 200/200 동일하다(실측). 대가는 실행 시간뿐이다.
MATCH_TARGET = None

# 사람이 검토·확정한 브랜드 대응표. BRAND_ALIASES 와 달리 코드에 넣지 않고 파일에서 읽는다.
# 아래 canonical_brand() 에서 기존 alias 와 라틴 키 조회가 모두 실패한 뒤에만 쓴다 —
# 순수 가산이라 성능 변화를 이 매핑 때문이라고 지목할 수 있다.
REVIEWED_BRAND_MAPPING_PATH = DATA_DIR / "brand_mapping_reviewed.csv"
REVIEWED_USABLE_STATUS = {"USABLE", "CASE_NORMALIZED"}

# LLM 이 국내 상품명만 보고 복원한 라틴 이름 (Method 3, KO->Latin).
# match_score() 의 추가 채널로만 쓴다 — 기존 romanize 채널을 대체하지 않는다.
# 표현이 없는 identity 는 동작이 완전히 동일하다.
#
# 고정본은 옛 commercial_identity_id 로 키가 잡혀 있고 해시로 잠겨 있다(method3).
# 그래서 파일을 고치지 않고 로드 시점에 재매핑표로 ID 를 번역한다 (9a-4 어댑터).
# 사람이 검토·확정한 매칭 (10d). 코드에 넣지 않고 파일에서 읽는다 — 브랜드 매핑과 같은 원칙.
# `CONFIRM` 은 Verification 이 취소한 판정을 되돌리고, `OTHER` 는 사람이 지정한 다른 ID 를 쓴다.
# `REJECT` 는 override 를 만들지 않는다 (취소된 상태 그대로 지도에서 제외된다).
#
# 이 표는 아래 SNAPSHOT_FRAGRANTICA_MATCHES 와 같은 검증(제품형태·농도 모순)을 통과해야 한다.
# 사람 판정을 코드가 되돌리지 않는다. 다만 검증에서 모순이 잡히면 조용히 넘기지 않고 멈춘다.
REVIEWED_CONFIRMATIONS_PATH = DATA_DIR / "evaluation/confirmation_review_decisions.csv"
# 사용자가 직접 재검토를 요청한 행이다 (`폴로 랄프` — 사람 판정 Ralph 826 vs DEV Gold Polo 890).
# 판정을 뒤집는 것이 아니라 **보류**한다. 재검토 결과가 오면 이 목록에서 빼면 된다.
PENDING_REREVIEW = {"ci_d2fcaaa64889"}

LLM_KO_LATIN_PATH = DATA_DIR / "evaluation/llm_ko_to_latin_outputs.csv"
LLM_KO_LATIN_EXTRA_PATH = DATA_DIR / "evaluation/llm_ko_to_latin_outputs_pipeline.csv"
IDENTITY_REMAP_PATH = DATA_DIR / "identity_remap_brand_mapping.csv"
# UNKNOWN 은 LLM 이 판단 불가라고 표시한 것이다. 빈 표현을 채널로 쓰지 않는다.
LLM_USABLE_STATUS = {"OK", "UNCERTAIN"}
SOURCES = ("musinsa", "oliveyoung", "lotte")
SEED = 42


# Fragrantica의 표기와 로컬 쇼핑몰 표기를 연결하는 명시적 브랜드 근거다.
# 제품명 fuzzy 점수와 달리 이 표는 snapshot-independent 브랜드 alias다.
BRAND_ALIASES = {
    "메종 마르지엘라": "Maison Martin Margiela",
    "메종 마르지엘라 퍼퓸": "Maison Martin Margiela",
    "엘리자베스아덴": "Elizabeth Arden",
    "엘리자베스": "Elizabeth Arden",
    "조말론": "Jo Malone London",
    "다니엘트루스": "Daniel's Truth",
    "포맨트": "Forment",
    "르라보": "Le Labo",
    "바닐라부티크": "Vanilla Boutique",
    "딥티크": "Diptyque",
    "끌로에": "Chloe",
    "바이레도": "Byredo",
    "아뜰리에페이": "Atelier Faye",
    "산타마리아노벨라": "Santa Maria Novella",
    "캘빈클라인": "Calvin Klein",
    "캘빈클라인 퍼퓸": "Calvin Klein",
    "아리아나그란데": "Ariana Grande",
    "입생로랑뷰티": "Yves Saint Laurent",
    "지미추": "Jimmy Choo",
    "살바토레페라가모": "Salvatore Ferragamo",
    "에스티로더": "Estee Lauder",
    "아쿠아디파르마": "Acqua di Parma",
    "몽블랑": "Montblanc",
    "몽블랑 퍼퓸": "Montblanc",
    "버버리": "Burberry",
    "메블릭퍼퓸": "Mebelic",
    "에디션드퍼퓸프레데릭말": "Frederic Malle",
    "나르시소 로드리게즈": "Narciso Rodriguez",
    "존바바토스": "John Varvatos",
    "베르사체": "Versace",
    "베르사체 퍼퓸": "Versace",
    "에스더블유나인틴": "SW19",
    "질스튜어트 뷰티": "Jill Stuart",
    "돌체앤가바나": "Dolce&Gabbana",
    "돌체앤가바나 퍼퓸": "Dolce&Gabbana",
    "이세이미야케": "Issey Miyake",
    "이세이미야케 퍼퓸": "Issey Miyake",
    "롤리타 렘피카": "Lolita Lempicka",
    "마이클코어스": "Michael Kors",
    "데메테르 어스": "Demeter Fragrance",
    "폴로랄프로렌 퍼퓸": "Ralph Lauren",
    "랄프로렌": "Ralph Lauren",
    "로라메르시에": "Laura Mercier",
    "스테판 움베르 루카": "Stephane Humbert Lucas 777",
    "나르시소로드리게즈": "Narciso Rodriguez",
    "제니퍼로페즈": "Jennifer Lopez",
    "코치 프래그런스": "Coach",
    "코치": "Coach",
    "랑방": "Lanvin",
    "랑방 퍼퓸": "Lanvin",
    "비비앙": "Vivienne Westwood",
    "클린": "Clean",
    "겐조": "Kenzo",
    "필로소피": "Philosophy",
    "지미추 퍼퓸": "Jimmy Choo",
    "랑콤": "Lancome",
    "톰포드": "Tom Ford",
    "에르메스": "Hermes",
    "구찌": "Gucci",
    "프라다": "Prada",
    "디올": "Dior",
    "샤넬": "Chanel",
    "CK": "Calvin Klein",
    "아디다스(뷰티)": "Adidas",
    "아디다스 향수": "Adidas",
    "불가리": "Bvlgari",
    "로샤스": "Rochas",
    "라리끄": "Lalique",
    "몽탈": "Montale",
    "만세라": "Mancera",
    "니샤네": "Nishane",
    "에센셜퍼퓸": "Essential Parfums",
    "바나나리퍼블릭": "Banana Republic",
    "재규어": "Jaguar",
    "랑세": "Rance 1795",
    "까보틴": "Gres",
    "그레": "Grès",
    "비엠더블유": "BMW Fragrances",
    "BMW": "BMW Fragrances",
    "리플레이": "Replay",
    "투미": "TUMI",
    "트루사르디": "Trussardi",
    "메모": "Memo Paris",
    "메르세데스 벤츠": "Mercedes-Benz",
    "에따 리브르 도랑쥬": "Etat Libre d'Orange",
    "더바디샵": "The Body Shop",
    "러쉬": "Lush",
    "엑스니힐로": "Ex Nihilo",
    "겐조 퍼퓸": "Kenzo",
    "아리아나 그란데": "Ariana Grande",
    "사브리나카펜터": "Sabrina Carpenter",
    "사브리나 카펜터": "Sabrina Carpenter",
    "마크제이콥스": "Marc Jacobs",
    "록시땅": "L'Occitane en Provence",
    "이솝": "Aesop",
    "벤틀리": "Bentley",
    "니코스": "Nikos",
    "타미힐피거": "Tommy Hilfiger",
    "케네스콜": "Kenneth Cole",
    "아뜰리에데조": "Atelier des Ors",
    "베르두": "Parfums Berdoues",
    "베르두콜렉션": "Parfums Berdoues",
    "포르쉐디자인": "Porsche Design",
    "파코라반": "Paco Rabanne",
    "라코스테": "Lacoste Fragrances",
    "휴고보스": "Hugo Boss",
    "모스키노": "Moschino",
    "안나수이": "Anna Sui",
    "데이비드베컴": "David Beckham",
    "아자로": "Azzaro",
    "페라리": "Ferrari",
    "폴스미스": "Paul Smith",
    "빅터앤롤프": "Viktor&Rolf",
    "끌리니끄": "Clinique",
    "클리니크": "Clinique",
}

PROMO_WORDS = (
    "단독기획", "기획", "증정", "정품", "리뷰이벤트", "NEW", "PICK", "특가",
    "본품", "택1", "택 1", "세트", "바이알", "미니어처", "무료배송", "공식",
    "단품", "랜덤", "리뉴얼출시", "스테디셀러", "올영1위", "포카", "컬래버",
)
FORM_WORDS = (
    "오 드 퍼퓸", "오드퍼퓸", "오 드 뚜왈렛", "오드뚜왈렛", "오 드 코롱", "오드코롱",
    "퍼퓸", "향수", "헤어", "바디", "미스트", "솔리드", "고체", "밤", "크림", "젤", "스틱", "롤온",
)

# 2026-09-05/06 snapshot에서 로컬 이름과 Fragrantica 후보 이름을 직접 대조한
# 보수적 확정값이다. 일반 fuzzy 규칙과 분리하며, 키가 정확히 일치할 때만 쓴다.
SNAPSHOT_FRAGRANTICA_MATCHES = {
    ("Maison Martin Margiela", "레플리카 레이지 선데이 모닝", "EDT"): 20542,
    ("Ralph Lauren", "폴로 랄프", "EDT"): 890,
    ("John Varvatos", "아티산 퓨어", "EDT"): 46623,
    ("Lanvin", "에끌라 드 아르페쥬", "EDP"): 9110,
    ("Maison Martin Margiela", "레플리카 네버 엔딩 썸머", "EDT"): 103564,
    ("Maison Martin Margiela", "레플리카 세일링 데이", "EDT"): 47891,
    ("Narciso Rodriguez", "포 힘 블루 느와르", "EDT"): 31247,
    ("Versace", "베르사체 크리스탈 에메랄드", "EDP"): 115545,
    ("Versace", "블루진", "EDT"): 637,
    ("Versace", "뿌르 옴므", "EDT"): 2318,
    ("John Varvatos", "아티산 포레스트", "EDP"): 113867,
    ("Maison Martin Margiela", "레플리카 스프링타임 인 어 파크", "EDT"): 55927,
    ("Montblanc", "스타워커", "EDT"): 4023,
    ("Maison Martin Margiela", "레플리카 체이싱 선셋", "EDT"): 124286,
    ("Sabrina Carpenter", "체리베이비", "EDP"): 95861,
    ("Ariana Grande", "땡큐 넥스트", "EDP"): 56741,
    ("Ariana Grande", "스위트 라이크 캔디 중", "EDP"): 39970,
    ("Lanvin", "레 플레르 드 써니 매그놀리아", "EDT"): 69742,
    ("Burberry", "위크엔드 우먼", "EDP"): 1000,
    ("Burberry", "터치 포 맨", "EDT"): 815,
    ("Chloé", "로즈탠저린", "EDT"): 62372,
    ("Ariana Grande", "땡큐 넥스트 중", "EDP"): 56741,
    ("Lanvin", "에끌라 드 아르페쥬 화이트 티", "EDP"): 131298,
    ("Mercedes-Benz", "맨 프레쉬", "EDT"): 123200,
    ("Montblanc", "레전드", "EDT"): 11784,
    ("Ariana Grande", "땡큐 넥스트 2 0 중", "EDP"): 68367,
    ("Clean", "애플블로썸 30 중", "EDP"): 82586,
    ("Narciso Rodriguez", "포 허 인텐스", "EDP"): 101595,
    ("Dolce&Gabbana", "리뉴얼 라이트블루 뿌르 옴므", "EDT"): 1068,
    ("Lanvin", "레 플레르 드 스위트 자스민", "EDT"): 83028,
    ("Ariana Grande", "문라이트", "EDP"): 46410,
    ("Narciso Rodriguez", "포 힘 블루 누와르", "EDT"): 31247,
    ("Marc Jacobs", "퍼펙트", "EDP"): 62021,
    ("Kenzo", "옴므 오 마린", "EDT"): 80042,
    ("Lalique", "솔레이 루나", "EDP"): 96192,
    ("BMW Fragrances", "더 센트 오브 베르가무드", "EDP"): 106298,
    ("Mancera", "인텐스 세드라 부아제", "EXTRAIT"): 72796,
    ("Kenneth Cole", "맨카인드 라이즈", "EDT"): 94718,
    ("Mancera", "시실리", "EDP"): 42670,
    ("Mancera", "로즈 그리디", "EDP"): 18042,
    ("Rance 1795", "오드라 꾸론느", "EDT"): 6420,
    ("Versace", "브라이트 크리스탈 1종", "EDT"): 632,
    ("Nishane", "멘트 투 비 씬 엑스트레 드", "EXTRAIT"): 116224,
    ("Banana Republic", "피오니 & 페퍼콘", "EDP"): 63829,
    ("Bentley", "모멘텀 언브레이커블", "EDP"): 69281,
    ("Banana Republic", "벨벳 포메그레네이트 75ml", "EDP"): 74739,
    ("Versace", "브라이트 크리스탈 앱솔루", "EDP"): 21547,
    ("Replay", "탱크 플레이트 포 맨", "EDT"): 50767,
    ("Montale", "바닐 압솔뤼", "EDP"): 4064,
    ("Trussardi", "르비드밀라노 워킹인 포르타 베네치아", "EDP"): 73546,
    ("Montale", "인피니티", "EDP"): 81773,
    ("TUMI", "키네틱", "EDP"): 76413,
    ("TUMI", "컨티넘 12 00", "EDP"): 70278,
    ("Kenneth Cole", "블랙 포 허", "EDP"): 877,
    ("Lalique", "솔레이 비브랑", "EDP"): 72448,
    ("Montale", "프리티 프루티", "EDP"): 12301,
    ("Montale", "로즈 엘릭시르", "EDP"): 9222,
    ("Montale", "크리스탈 플라워즈", "EDP"): 3772,
    ("Rance 1795", "르와엠페러 포 맨", "EDP"): 11896,
    ("Montale", "로즈 머스크", "EDP"): 1148,
    ("Rance 1795", "조세핀 포 우먼", "EDP"): 1929,
    ("Jo Malone London", "우드 세이지 앤 씨 솔트 코롱", "UNSPECIFIED"): 74041,
    ("Byredo", "발 다프리크", "EDP"): 6458,
    ("Diptyque", "플레르 드 뽀", "EDP"): 131717,
    ("Tom Ford", "네롤리 포르토피노", "EDP"): 12192,
    ("Jo Malone London", "잉글리쉬 오크 앤 헤이즐넛 코롱", "UNSPECIFIED"): 46187,
    ("Gucci", "플로라 골저스가드니아", "EDP"): 68578,
    ("Byredo", "모하비 고스트", "EDP"): 27040,
    ("Salvatore Ferragamo", "인칸토 참", "EDT"): 653,
    ("Estée Lauder", "플레져 스프레이", "EDP"): 536,
    ("Jo Malone London", "와일드 블루벨 코롱", "UNSPECIFIED"): 12310,
    ("Jo Malone London", "라임 바질 앤 만다린 코롱", "UNSPECIFIED"): 5585,
    ("Frederic Malle", "포트레이트 오브 어 레이디", "UNSPECIFIED"): 10464,
    ("Yves Saint Laurent", "몽파리 루미에르", "EDT"): 72606,
    ("Elizabeth Arden", "그린티 센트 스프레이", "EDC"): 83,
    ("Elizabeth Arden", "그린티 센트 스프레이", "UNSPECIFIED"): 83,
    ("Clean", "클리어 쿨 코튼", "EDP"): 23032,
    ("Calvin Klein", "씨케이원", "EDT"): 276,
    ("Clean", "클래식 소프트 런드리", "EDP"): 75629,
    ("John Varvatos", "아티산 중", "EDT"): 5534,
    ("Kenzo", "플라워바이", "EDP"): 72,
    ("Calvin Klein", "CK 에브리원", "EDP"): 71607,
    ("Marc Jacobs", "데이지 오 쏘 프레쉬", "EDT"): 10858,
    ("Montale", "데이 드림즈", "EDP"): 45055,
    ("Grès", "카보틴 로즈", "EDT"): 4859,
    ("Grès", "카보샤 셰리", "EDP"): 55532,
    ("Mancera", "로즈 바닐", "EDP"): 15210,
    ("Montale", "오드 포레스트", "EDP"): 9559,
    ("Montale", "인텐스 카페", "EDP"): 18021,
    ("Yves Saint Laurent", "리브르", "EDT"): 56077,
    ("Byredo", "인플로레센스", "EDP"): 17798,
    ("Forment", "시그니처 코튼허그", "PARFUM_UNSPECIFIED"): 75979,
    ("Maison Martin Margiela", "레플리카 웬 더 레인 스탑스", "EDT"): 70985,
    ("Maison Martin Margiela", "레플리카 업 앳 던", "EDT"): 120743,
    ("Adidas", "아디다스 바이브 스파크 업", "EDP"): 98468,
    ("The Body Shop", "화이트 머스크 98139", "EDT"): 2432,
    ("Jill Stuart", "LIMITED 크리스탈 블룸 썸씽 퓨어 블루 000원 상당", "EDP"): 45086,
    ("Sabrina Carpenter", "스위트투스", "EDP"): 76824,
    ("Clean", "웜코튼 중", "EDP"): 3024,
    ("Narciso Rodriguez", "포 허 퓨어 머스크 블랑", "UNSPECIFIED"): 122211,
    ("Jimmy Choo", "아이원추 르 파팡", "PARFUM_UNSPECIFIED"): 95156,
    ("Dolce&Gabbana", "리뉴얼 라이트블루", "EDT"): 485,
    ("Clean", "스트로베리필즈 중", "EDP"): 104123,
    ("Philosophy", "어메이징 그레이스", "EDP"): 4849,
    ("Clean", "퓨어솝 중", "EDP"): 68416,
    ("Dolce&Gabbana", "베스트 리뉴얼 라이트블루 뿌르 옴므", "EDT"): 1068,
    ("Chloé", "노마드", "EDT"): 53224,
    ("Memo Paris", "셔우드", "EDP"): 77998,
    ("Banana Republic", "미드나잇 아워", "EDP"): 74740,
    ("Banana Republic", "퓨어 화이트", "EDP"): 45029,
    ("Rance 1795", "조세핀 포 우먼 3종", "EDP"): 1929,
    ("BMW Fragrances", "더 센트 오브 앰버니스", "EDP"): 106299,
    ("Rance 1795", "헬레네 포 우먼", "EDP"): 10728,
    ("Mancera", "패블러스 유주", "EDP"): 75731,
    ("Rance 1795", "프랑수와찰스 포 맨", "EDP"): 3172,
    ("Rance 1795", "마틸드 3종", "EDP"): 87956,
    ("Replay", "시그니처 시크릿 포 우먼", "EDT"): 49827,
    ("TUMI", "어웨이큰 08 00", "EDP"): 62766,
    ("Replay", "소스 오브 라이프 포 우먼", "EDP"): 88050,
    ("Trussardi", "르비드밀라노 디이탈리안 아티스트 오브 비아솔페리노EDP", "UNSPECIFIED"): 73547,
    ("Trussardi", "르비드밀라노 디스트릭트 오브 노로", "EDP"): 80039,
    ("Mancera", "엠버 피버", "EDP"): 57879,
    ("Trussardi", "르비드밀라노 비하인드 더 커튼 피아차 라스칼라", "EDP"): 59828,
    ("Trussardi", "르비드밀라노 비하인더커튼 피아차 라스칼라EDP", "UNSPECIFIED"): 59828,
    ("Trussardi", "르비드밀라노 아이비콜리 피오리 치아리", "EDP"): 59830,
    ("Trussardi", "르비드밀라노 아이비콜리 비아 피오리 치아리EDP", "UNSPECIFIED"): 59830,
    ("Parfums Berdoues", "그랑크뤼 과리아 모라다", "EDP"): 59840,
    ("TUMI", "언와인드 20 00", "EDP"): 62770,
    ("Replay", "시그니처 러버즈 포 맨", "EDT"): 60321,
    ("Bentley", "포맨 아쥬르", "EDT"): 21856,
    ("Parfums Berdoues", "그랑크뤼 바니라 무레아", "EDP"): 38167,
    ("Diptyque", "오르페옹", "EDP"): 65738,
    ("Le Labo", "어나더 13", "EDP"): 10131,
    ("Diptyque", "오 로즈", "EDT"): 14214,
    ("Aesop", "테싯", "EDP"): 32134,
    ("Diptyque", "필로시코스", "EDT"): 72040,
    ("Chanel", "샹스 오 후레쉬", "EDT"): 1483,
    ("Chanel", "알뤼르 옴므 스포츠", "EDT"): 607,
    ("Chanel", "샹스 오 땅드르 오 드 빠르펭", "UNSPECIFIED"): 52359,
    ("Aesop", "로즈", "EDP"): 64167,
    ("Byredo", "집시 워터", "EDP"): 3575,
    ("Jo Malone London", "피오니 앤 블러쉬 스웨이드 코롱", "UNSPECIFIED"): 18767,
    ("Dior", "소바쥬", "EDT"): 31861,
    ("Diptyque", "필로시코스", "EDP"): 3865,
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha1(value.encode('utf-8')).hexdigest()[:12]}"


def latin_key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


CHO = ("g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h")
JUNG = ("a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i")
JONG = ("", "k", "k", "ks", "n", "nj", "nh", "t", "l", "lk", "lm", "lp", "ls", "lt", "lp", "lh", "m", "p", "ps", "t", "t", "ng", "t", "t", "k", "t", "p", "h")


def romanize(value: object) -> str:
    out = []
    for char in unicodedata.normalize("NFKC", str(value or "")).lower():
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            n = code - 0xAC00
            out.append(CHO[n // 588] + JUNG[(n % 588) // 28] + JONG[n % 28])
        elif char.isascii() and char.isalnum():
            out.append(char)
        else:
            out.append(" ")
    return re.sub(r"\s+", " ", "".join(out)).strip()


def phonetic_key(value: object) -> str:
    s = romanize(value)
    replacements = (("ph", "f"), ("v", "b"), ("c", "k"), ("q", "k"),
                    ("x", "ks"), ("z", "s"), ("eo", "o"), ("ae", "e"),
                    ("eu", ""), ("ui", "i"), ("w", ""), ("y", ""),
                    ("r", "l"))
    for old, new in replacements:
        s = s.replace(old, new)
    s = re.sub(r"[aeiou\W_]", "", s)
    return re.sub(r"(.)\1+", r"\1", s)


def detect_concentration(value: object) -> str:
    s = unicodedata.normalize("NFKC", str(value or "")).upper()
    if re.search(r"\b(EXTRAIT|EXDP)\b|엑스트레", s):
        return "EXTRAIT"
    if re.search(r"\bEDP\b|EAU\s+DE\s+PARFUM|오\s*드\s*퍼퓸|오드퍼퓸", s):
        return "EDP"
    if re.search(r"\bEDT\b|EAU\s+DE\s+TOILETTE|오\s*드\s*뚜왈렛|오드뚜왈렛", s):
        return "EDT"
    if re.search(r"\bEDC\b|EAU\s+DE\s+COLOGNE|오\s*드\s*코롱|오드코롱", s):
        return "EDC"
    if re.search(r"\bPARFUM\b|퍼퓸", s):
        return "PARFUM_UNSPECIFIED"
    return "UNSPECIFIED"


def detect_form(value: object) -> str:
    s = str(value or "").lower()
    if "헤어" in s or "hair" in s:
        return "HAIR_FRAGRANCE"
    if "바디" in s or "body mist" in s:
        return "BODY_FRAGRANCE"
    if any(x in s for x in ("고체", "솔리드", "solid perfume")):
        return "SOLID_FRAGRANCE"
    if any(x in s for x in ("퍼퓸밤", "퍼퓸 밤", "balm", "스틱", "stick")):
        return "BALM_OR_STICK"
    if any(x in s for x in ("롤온", "roll-on", "roll on")):
        return "ROLL_ON"
    return "LIQUID_PERFUME"


def load_reviewed_brand_mapping() -> dict[str, str]:
    """검토 확정된 국내 브랜드 -> Fragrantica 브랜드. 카탈로그에서 확인된 것만 쓴다.

    NOT_IN_CATALOG / AMBIGUOUS_REVIEW_VALUE 는 사람 판정이 MATCH 여도 로컬 스냅샷에서
    쓸 수 없으므로 제외한다. 파일이 없으면 빈 표를 돌려준다(모듈은 어떤 상태에서도 import 가능).
    """
    if not REVIEWED_BRAND_MAPPING_PATH.exists():
        return {}
    frame = pd.read_csv(REVIEWED_BRAND_MAPPING_PATH, encoding="utf-8-sig", keep_default_na=False)
    usable = frame[frame.catalog_status.isin(REVIEWED_USABLE_STATUS)]
    assert usable.korea_brand.is_unique, "검토 매핑에 같은 국내 브랜드가 두 번 있다"
    return dict(zip(usable.korea_brand, usable.fragrantica_brand))


REVIEWED_BRAND_MAPPING = load_reviewed_brand_mapping()


def load_llm_ko_latin() -> dict[str, str]:
    """commercial_identity_id -> LLM 이 복원한 라틴 향 이름.

    고정본은 옛 ID 를 쓰므로 재매핑표로 신규 ID 로 옮긴다. 분할돼 대응이 모호한 ID 는
    버린다 — 어느 쪽에 붙일지 코드가 정할 근거가 없다.
    파이프라인용 추가 생성분(`_pipeline.csv`)은 처음부터 신규 ID 로 키를 잡으므로 그대로 쓴다.
    파일이 없으면 빈 표를 돌려준다(모듈은 어떤 상태에서도 import 가능하고 동작이 불변이다).
    """
    def usable(path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        frame = pd.read_csv(path, keep_default_na=False)
        frame = frame[frame.reconstruction_status.isin(LLM_USABLE_STATUS)]
        frame = frame[frame.reconstructed_fragrance_latin.astype(str).str.strip() != ""]
        assert frame.commercial_identity_id.is_unique, f"{path.name} 에 같은 identity 가 두 번 있다"
        return dict(zip(frame.commercial_identity_id, frame.reconstructed_fragrance_latin))

    frozen = usable(LLM_KO_LATIN_PATH)
    if frozen and IDENTITY_REMAP_PATH.exists():
        remap = pd.read_csv(IDENTITY_REMAP_PATH, encoding="utf-8-sig", keep_default_na=False)
        counts = remap.old_commercial_identity_id.value_counts()
        translated = {}
        for old, name in frozen.items():
            rows = remap.new_commercial_identity_id[remap.old_commercial_identity_id == old]
            if counts.get(old, 0) == 1 and len(rows) == 1:
                translated[rows.iloc[0]] = name
        frozen = translated
    return {**frozen, **usable(LLM_KO_LATIN_EXTRA_PATH)}


LLM_KO_LATIN_NAMES = load_llm_ko_latin()


def load_reviewed_confirmations() -> dict[str, int]:
    """commercial_identity_id -> 사람이 확정한 Fragrantica ID (10d).

    `CONFIRM` 은 `refused_fragrantica_id`, `OTHER` 는 `human_fragrantica_id` 를 쓴다.
    `REJECT` 와 재검토 보류분은 넣지 않는다. 파일이 없으면 빈 표를 돌려준다.
    """
    if not REVIEWED_CONFIRMATIONS_PATH.exists():
        return {}
    frame = pd.read_csv(REVIEWED_CONFIRMATIONS_PATH, encoding="utf-8-sig", keep_default_na=False)
    frame = frame[frame.commercial_identity_id.astype(str).str.strip() != ""]
    assert frame.human_decision.isin(["CONFIRM", "REJECT", "OTHER", ""]).all(), \
        f"허용되지 않은 human_decision: {sorted(set(frame.human_decision))}"
    assert frame.commercial_identity_id.is_unique, "검토 결과에 같은 identity 가 두 번 있다"
    out = {}
    for row in frame.itertuples(index=False):
        if row.commercial_identity_id in PENDING_REREVIEW:
            continue
        raw = (row.human_fragrantica_id if row.human_decision == "OTHER"
               else row.refused_fragrantica_id if row.human_decision == "CONFIRM" else "")
        if str(raw).strip() == "":
            continue
        out[str(row.commercial_identity_id)] = int(float(raw))
    return out


REVIEWED_CONFIRMATIONS = load_reviewed_confirmations()


def canonical_brand(raw_brand: object, product: object, brand_index: dict[str, str]) -> tuple[str, str]:
    raw = str(raw_brand or "").strip()
    title = str(product or "")
    if raw == "향수존":
        found = [a for a in BRAND_ALIASES if a.lower() in title.lower()]
        if found:
            raw = max(found, key=len)
        else:
            bracket = re.match(r"\s*\[([^\]]+)\]", title)
            raw = bracket.group(1).strip() if bracket else title.split()[0]
    alias = BRAND_ALIASES.get(raw, raw)
    key = latin_key(alias)
    if key and key in brand_index:
        return brand_index[key], f"exact_or_alias:{raw}->{brand_index[key]}"
    raw_key = latin_key(raw)
    if raw_key and raw_key in brand_index:
        return brand_index[raw_key], f"exact_latin:{raw}"
    reviewed = REVIEWED_BRAND_MAPPING.get(raw)
    if reviewed:
        reviewed_key = latin_key(reviewed)
        if reviewed_key in brand_index:
            return brand_index[reviewed_key], f"reviewed_brand_mapping:{raw}->{brand_index[reviewed_key]}"
    return alias, f"unresolved_brand:{raw}"


def clean_scent_name(product: object, raw_brand: object, canonical: str) -> str:
    s = unicodedata.normalize("NFKC", str(product or ""))
    s = re.sub(r"[\[\](){}<>]", " ", s)
    s = re.sub(r"\b\d+(?:\.\d+)?\s*(?:ml|mL|ML|g|G)\b", " ", s)
    s = re.sub(r"\b\d+\s*(?:종|개|PACK|pack)\b", " ", s)
    s = re.sub(r"\b\d+\s*m\b", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\+[^,;/]*", " ", s)
    for word in PROMO_WORDS + FORM_WORDS:
        s = re.sub(re.escape(word), " ", s, flags=re.IGNORECASE)
    for word in (str(raw_brand or ""), canonical):
        if word:
            s = re.sub(re.escape(word), " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\b(?:EDP|EDT|EDC|EXDP|PFM)I?\b", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"[^0-9A-Za-z가-힣&]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def family_name_key(scent_name: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", scent_name.lower())


def make_identity_rows(purchase: pd.DataFrame, hwahae: pd.DataFrame, brand_index: dict[str, str]):
    rows = []
    purchase_lookup = {}
    for r in purchase.itertuples(index=False):
        brand, brand_basis = canonical_brand(r.brand_raw, r.product_name_raw, brand_index)
        identity_brand = str(r.brand_raw)
        if identity_brand == "향수존" and "->" in brand_basis:
            identity_brand = brand_basis.split(":", 1)[1].split("->", 1)[0]
        scent = clean_scent_name(r.product_name_raw, identity_brand, brand)
        conc = detect_concentration(r.product_name_raw)
        form = detect_form(r.product_name_raw)
        key = "|".join((latin_key(brand), family_name_key(scent), conc, form))
        ci = stable_id("ci", "purchase|" + key)
        purchase_lookup[(str(r.source), int(r.source_rank))] = ci
        rows.append({
            "commercial_identity_id": ci, "origin": "purchase", "source": r.source,
            "source_rank": int(r.source_rank), "source_product_id": r.source_product_id,
            "brand_raw": r.brand_raw, "product_name_raw": r.product_name_raw,
            "canonical_brand": brand, "brand_basis": brand_basis,
            "fragrance_name_normalized": scent, "concentration": conc, "product_form": form,
            "purchase_overlap_status": "", "purchase_overlap_basis": "",
            "matched_purchase_commercial_identity_id": "",
        })

    for r in hwahae.itertuples(index=False):
        status = str(r.overlap_status)
        if status not in ALLOWED_MATCH_STATUS:
            raise ValueError(f"unexpected overlap status: {status}")
        brand, brand_basis = canonical_brand(r.hwahae_brand, r.hwahae_product, brand_index)
        scent = clean_scent_name(r.hwahae_product, r.hwahae_brand, brand)
        conc = detect_concentration(r.hwahae_product)
        form = detect_form(r.hwahae_product)
        matched_ci = ""
        if pd.notna(r.matched_purchase_source) and pd.notna(r.matched_purchase_source_rank):
            matched_ci = purchase_lookup.get((str(r.matched_purchase_source), int(r.matched_purchase_source_rank)), "")
        if status == "MATCH" and not matched_ci:
            raise ValueError(f"Hwahae rank {r.hwahae_rank}: MATCH reference not found")
        key = "|".join((latin_key(brand), family_name_key(scent), conc, form))
        ci = matched_ci if status == "MATCH" else stable_id("ci", f"hwahae|{r.hwahae_rank}|{key}")
        rows.append({
            "commercial_identity_id": ci, "origin": "hwahae", "source": "hwahae",
            "source_rank": int(r.hwahae_rank), "source_product_id": r.hwahae_source_product_id,
            "brand_raw": r.hwahae_brand, "product_name_raw": r.hwahae_product,
            "canonical_brand": brand, "brand_basis": brand_basis,
            "fragrance_name_normalized": scent, "concentration": conc, "product_form": form,
            "purchase_overlap_status": status, "purchase_overlap_basis": r.match_basis,
            "matched_purchase_commercial_identity_id": matched_ci,
        })
    return pd.DataFrame(rows)


def aggregate_commercial(members: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ci, g in members.groupby("commercial_identity_id", sort=False):
        p = g[g.origin == "purchase"]
        h = g[g.origin == "hwahae"]
        first = g.iloc[0]
        scent = first.fragrance_name_normalized
        family_key = f"{latin_key(first.canonical_brand)}|{family_name_key(scent)}"
        statuses = sorted(set(h.purchase_overlap_status) - {""})
        row = {
            "commercial_identity_id": ci,
            "canonical_brand": first.canonical_brand,
            "fragrance_name_normalized": scent,
            "concentration": first.concentration,
            "product_form": first.product_form,
            "candidate_family_id": stable_id("cf", family_key),
            "has_purchase_signal": bool(len(p)), "has_hwahae_signal": bool(len(h)),
            "best_hwahae_rank": int(h.source_rank.min()) if len(h) else np.nan,
            "purchase_overlap_status": "|".join(statuses),
            "purchase_overlap_basis": " | ".join(sorted(set(h.purchase_overlap_basis.dropna()) - {""})),
            "matched_purchase_commercial_identity_id": "|".join(sorted(set(h.matched_purchase_commercial_identity_id) - {""})),
            "member_count": len(g), "purchase_member_count": len(p), "hwahae_member_count": len(h),
            "member_refs": "|".join(f"{x.source}:{int(x.source_rank)}" for x in g.itertuples()),
            "fragrantica_match_attempted": False, "fragrantica_match_status": "",
            "fragrantica_id": np.nan, "fragrantica_match_basis": "",
            "fragrantica_candidate_ids": "", "fragrantica_match_score": np.nan,
            "fragrantica_candidate_names": "", "fragrantica_match_margin": np.nan,
        }
        for source in SOURCES:
            ranks = p.loc[p.source == source, "source_rank"]
            row[f"best_{source}_rank"] = int(ranks.min()) if len(ranks) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def rrf_for_row(row, k: int = 60, excluded_source: str | None = None) -> float:
    score = 0.0
    for source in SOURCES:
        if source == excluded_source:
            continue
        rank = row[f"best_{source}_rank"]
        if pd.notna(rank):
            score += 1.0 / (k + float(rank))
    return score


def aggregate_families(commercial: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for family_id, g in commercial.groupby("candidate_family_id", sort=False):
        first = g.iloc[0]
        row = {
            "candidate_family_id": family_id, "canonical_brand": first.canonical_brand,
            "normalized_fragrance_name": first.fragrance_name_normalized,
            "commercial_identity_count": len(g),
            "has_hwahae_signal": bool(g.has_hwahae_signal.any()),
            "best_hwahae_rank": g.best_hwahae_rank.min(),
            "commercial_identity_ids": "|".join(g.commercial_identity_id),
        }
        for source in SOURCES:
            row[f"best_{source}_rank"] = g[f"best_{source}_rank"].min()
        row["family_priority_rrf"] = rrf_for_row(row, 60)
        rows.append(row)
    out = pd.DataFrame(rows)
    return out.sort_values(["has_hwahae_signal", "family_priority_rrf", "best_hwahae_rank"],
                           ascending=[False, False, True], na_position="last").reset_index(drop=True)


def match_channels(query: str, candidate: str, llm_query: str = "") -> dict[str, float]:
    """국내 향 이름과 후보 이름의 채널별 유사도.

    `llm_query` 는 LLM 이 복원한 라틴 이름이다. 주어지면 채널이 둘 늘어난다.
    빈 문자열이면 LLM 채널이 0.0 이라 최댓값이 기존 세 채널과 완전히 동일하다.

    `match_score` 는 이 값들의 최댓값이다. 어느 채널이 판정을 끌었는지 알아야 하는
    Verification(10b)이 같은 정의를 봐야 해서 dict 로 꺼냈다.
    """
    q = latin_key(romanize(query))
    c = latin_key(candidate)
    qp, cp = phonetic_key(query), phonetic_key(candidate)
    ql = latin_key(llm_query)
    ratio = lambda a, b: SequenceMatcher(None, a, b).ratio() if a and b else 0.0
    contains = lambda a, b: (min(len(a), len(b)) / max(len(a), len(b))
                             if a and b and (a in b or b in a) else 0.0)
    return {
        "direct": ratio(q, c),
        "phonetic": ratio(qp, cp),
        # 기존 contains 는 q/c 가 비어도 "" in "" 이 True 라 0.0 으로 떨어졌다. 동작 동일.
        "contains": contains(q, c),
        "llm_direct": ratio(ql, c),
        "llm_contains": contains(ql, c),
    }


def match_score(query: str, candidate: str, llm_query: str = "") -> float:
    return max(match_channels(query, candidate, llm_query).values())


# ---- Verification (10b, D16·D17) ----
# 자동 확정을 취소하는 두 조건. DEV 61건에서 차원별 분리력을 먼저 재고 조합했다.
#
# ① 음성 키 단독 — `phonetic_key` 는 모음을 전부 지우고 r/l·v/b 등을 합친다.
#    그래서 `우먼`(woman) 과 `Man` 이 둘 다 "mn" 이 된다. 이 키만으로 이긴 확정은
#    증거가 아니다. 표본과 무관하게 시연 가능한 알고리즘 결함이라 항상 적용한다.
# ② 기본명 애매성 — 고른 후보의 이름을 접두사로 갖는 카탈로그 변형이 여러 개면,
#    기본명에 일치했다는 사실 자체가 "변형 중 어느 것인지 모른다" 는 뜻이다.
#    `Miss Dior` 는 변형 46개의 기본명이고, 정답은 22위의 `Miss Dior Eau de Parfum` 이었다.
#
# retrieval 에서는 두 신호를 빼지 않는다. recall 이 필요한 곳과 precision 이 필요한 곳이 다르다.
VERIFICATION_ENABLED = True
VARIANT_SIBLING_LIMIT = 5


def candidate_concentrations(name: str, description: str) -> set[str]:
    text = f"{name} {description}"
    found = set()
    for token, pattern in {
        "EXTRAIT": r"\bextrait\b", "EDP": r"\beau de parfum\b|\bedp\b",
        "EDT": r"\beau de toilette\b|\bedt\b", "EDC": r"\beau de cologne\b|\bedc\b",
    }.items():
        if re.search(pattern, text, re.I):
            found.add(token)
    return found


def form_compatible(query_form: str, candidate_name: str) -> bool:
    candidate_form = detect_form(candidate_name)
    if query_form == "LIQUID_PERFUME":
        return candidate_form == "LIQUID_PERFUME"
    return query_form == candidate_form


def verification_refusal(row, best_core: str, best_key: str, best_id: int,
                         llm_query: str, brand_rows: pd.DataFrame) -> str:
    """자동 확정을 취소해야 하는 이유. 없으면 빈 문자열 (10b).

    `VERIFICATION_ENABLED` 가 False 면 항상 빈 문자열이라 도입 전 수치를 재현할 수 있다.
    """
    if not VERIFICATION_ENABLED:
        return ""
    channels = match_channels(row.fragrance_name_normalized, best_core, llm_query)
    top = max(channels.values())
    others = max(channels[k] for k in ("direct", "contains", "llm_direct", "llm_contains"))
    if channels["phonetic"] >= top and others < top:
        return "phonetic key only"

    # 후보 풀 전체에서 고른 이름을 접두사로 갖는 더 긴 변형의 수. 상위 5개만 보면 안 된다 —
    # D016 의 정답은 22위였다.
    variants = 0
    if best_key:
        for p in brand_rows.itertuples(index=False):
            if int(p.id) == best_id:
                continue
            core = latin_key(re.sub(re.escape(str(p.brand)), " ", str(p.name), flags=re.IGNORECASE))
            if core.startswith(best_key) and core != best_key:
                variants += 1
    if variants >= VARIANT_SIBLING_LIMIT:
        return f"base name with {variants} catalog variants"
    return ""


def match_one(row, brand_rows: pd.DataFrame) -> dict:
    result = {
        "fragrantica_match_attempted": True, "fragrantica_match_status": "NO_MATCH",
        "fragrantica_id": np.nan, "fragrantica_match_basis": "compatible candidate not found",
        "fragrantica_candidate_ids": "", "fragrantica_match_score": np.nan,
        "fragrantica_candidate_names": "", "fragrantica_match_margin": np.nan,
        "fragrantica_verification_refusal": "",
    }
    if brand_rows.empty or str(row.fragrance_name_normalized).strip() == "":
        result["fragrantica_match_basis"] = "brand unresolved or fragrance name empty"
        return result

    # 사람 검토 확정(10d)이 스냅샷 표보다 우선한다. 둘 다 같은 검증을 통과해야 한다.
    override_key = (str(row.canonical_brand), str(row.fragrance_name_normalized), str(row.concentration))
    override_id = REVIEWED_CONFIRMATIONS.get(str(row.commercial_identity_id))
    override_source = "human confirmation review"
    if override_id is None:
        override_id = SNAPSHOT_FRAGRANTICA_MATCHES.get(override_key)
        override_source = "snapshot manual confirmation"
    if override_id is not None:
        exact = brand_rows[brand_rows.id == override_id]
        if len(exact) != 1:
            raise ValueError(f"invalid Fragrantica override ({override_source}): "
                             f"{override_key} -> {override_id}")
        p = exact.iloc[0]
        if not form_compatible(row.product_form, p["name"]):
            raise ValueError(f"form conflict in override ({override_source}): {override_key}")
        p_concs = candidate_concentrations(p["name"], p.description)
        if row.concentration in {"EDP", "EDT", "EDC", "EXTRAIT"} and p_concs and row.concentration not in p_concs:
            raise ValueError(f"concentration conflict in override ({override_source}): {override_key}")
        result.update({
            "fragrantica_match_status": "MATCH", "fragrantica_id": override_id,
            "fragrantica_match_basis": f"{override_source}: brand, fragrance name, concentration/form compatible",
            "fragrantica_candidate_ids": str(override_id), "fragrantica_candidate_names": str(p["name"]),
            "fragrantica_match_score": 1.0, "fragrantica_match_margin": np.nan,
        })
        return result

    llm_query = LLM_KO_LATIN_NAMES.get(str(row.commercial_identity_id), "")
    candidates = []
    for p in brand_rows.itertuples(index=False):
        if not form_compatible(row.product_form, p.name):
            continue
        p_concs = candidate_concentrations(p.name, p.description)
        q_conc = row.concentration
        if q_conc in {"EDP", "EDT", "EDC", "EXTRAIT"} and p_concs and q_conc not in p_concs:
            continue
        candidate_name = re.sub(re.escape(str(p.brand)), " ", str(p.name), flags=re.IGNORECASE)
        candidate_name = re.sub(r"\s+", " ", candidate_name).strip()
        score = match_score(row.fragrance_name_normalized, candidate_name, llm_query)
        candidates.append((score, int(p.id), p.name, p_concs))
    candidates.sort(reverse=True)
    top = candidates[:5]
    result["fragrantica_candidate_ids"] = "|".join(str(x[1]) for x in top)
    result["fragrantica_candidate_names"] = "|".join(x[2] for x in top)
    if not top:
        return result
    best = top[0]
    result["fragrantica_match_score"] = round(best[0], 6)
    margin = best[0] - (top[1][0] if len(top) > 1 else 0.0)
    result["fragrantica_match_margin"] = round(margin, 6)
    best_core = re.sub(re.escape(str(row.canonical_brand)), " ", str(best[2]), flags=re.IGNORECASE)
    best_core = re.sub(r"\s+", " ", best_core).strip()
    best_key = latin_key(best_core)
    exact = latin_key(romanize(row.fragrance_name_normalized)) == best_key
    llm_exact = bool(llm_query) and latin_key(llm_query) == best_key
    exact = exact or llm_exact
    strong = exact or (best[0] >= 0.90 and margin >= 0.03) or (best[0] >= 0.84 and margin >= 0.10)
    plausible = best[0] >= 0.68
    conc_basis = "concentration compatible" if best[3] else "no conflicting concentration record"

    # 확정 후보였던 것만 검사한다. `strong` 이 아닌 것에까지 적용하면 원래 NO_MATCH 였던
    # 것이 MATCH_REVIEW 로 올라가 사람 검토 큐가 관계없는 건으로 불어난다.
    refusal = verification_refusal(row, best_core, best_key, best[1], llm_query,
                                   brand_rows) if strong else ""
    if refusal:
        strong = False
        result["fragrantica_verification_refusal"] = refusal

    if strong:
        result.update({
            "fragrantica_match_status": "MATCH", "fragrantica_id": best[1],
            "fragrantica_match_basis": (
                f"brand exact/explicit alias; name {'exact' if exact else 'unique high similarity'} "
                f"score={best[0]:.3f} margin={margin:.3f}; {conc_basis}; form compatible"
                + ("; llm reconstructed name exact" if llm_exact else "")
            ),
        })
    elif plausible or refusal:
        result.update({
            "fragrantica_match_status": "MATCH_REVIEW",
            "fragrantica_match_basis": (
                f"candidate retrieval only; name score={best[0]:.3f} margin={margin:.3f}; "
                f"manual confirmation required; {conc_basis}"
                + (f"; verification refused: {refusal}" if refusal else "")
            ),
        })
    return result


def match_queue(families: pd.DataFrame) -> tuple[list[str], pd.DataFrame]:
    """매칭을 시도하는 family 순서. 화해 신호 먼저, 그다음 구매 RRF 내림차순.

    progressive_match 가 쓰는 순서 그대로다. 이 순서를 다른 곳에서도 참조해야 해서
    함수로 꺼냈다 (LLM 생성 대상을 인기순으로 뽑을 때).
    """
    hw = families[families.has_hwahae_signal]
    queue = list(hw.candidate_family_id)
    purchase = families[families.family_priority_rrf > 0].sort_values("family_priority_rrf", ascending=False)
    queue.extend(x for x in purchase.candidate_family_id if x not in set(queue))
    return list(dict.fromkeys(queue)), hw


def progressive_match(commercial: pd.DataFrame, families: pd.DataFrame, perfumes: pd.DataFrame):
    brand_groups = {latin_key(k): v.copy() for k, v in perfumes.groupby("brand", sort=False)}
    queue, hw = match_queue(families)

    initial = len(hw) + min(150, len([x for x in queue if x not in set(hw.candidate_family_id)]))
    batch_ends = list(range(initial, len(queue) + 50, 50))
    attempted_families = set()
    start = time.perf_counter()
    for end in batch_ends:
        for family_id in queue[:min(end, len(queue))]:
            if family_id in attempted_families:
                continue
            attempted_families.add(family_id)
            idx = commercial.index[commercial.candidate_family_id == family_id]
            for i in idx:
                brand = commercial.at[i, "canonical_brand"]
                result = match_one(commercial.loc[i], brand_groups.get(latin_key(brand), pd.DataFrame()))
                for key, value in result.items():
                    commercial.at[i, key] = value
        matched_ids = commercial.loc[commercial.fragrantica_match_status == "MATCH", "fragrantica_id"].dropna().nunique()
        if (MATCH_TARGET is not None and matched_ids >= MATCH_TARGET
                and set(hw.candidate_family_id).issubset(attempted_families)):
            break
        if end >= len(queue):
            break
    elapsed = time.perf_counter() - start
    return commercial, elapsed, len(attempted_families), len(queue)


def build_map_identities(commercial: pd.DataFrame, perfumes: pd.DataFrame) -> pd.DataFrame:
    matched = commercial[commercial.fragrantica_match_status == "MATCH"].copy()
    perfume_by_id = perfumes.set_index("id")
    rows = []
    for fid, g in matched.groupby("fragrantica_id", sort=False):
        fid = int(fid)
        p = perfume_by_id.loc[fid]
        row = {
            "map_identity_id": f"fragrantica:{fid}", "fragrantica_id": fid,
            "fragrantica_brand": p.brand, "fragrantica_name": p["name"], "fragrantica_year": p.year,
            "commercial_identity_ids": "|".join(g.commercial_identity_id),
            "commercial_identity_count": len(g),
            "has_purchase_signal": bool(g.has_purchase_signal.any()),
            "has_hwahae_signal": bool(g.has_hwahae_signal.any()),
            "best_hwahae_rank": g.best_hwahae_rank.min(),
            "purchase_overlap_statuses": "|".join(sorted(set(g.purchase_overlap_status) - {""})),
            "accord_count": len(sm.parse_accords(p.accords)),
            "note_count": sum(len(str(p[c]).split("|")) for c in sm.NOTE_COLS if pd.notna(p[c]) and str(p[c]).strip()),
            "map_identity_conflict": False,
        }
        for source in SOURCES:
            row[f"best_{source}_rank"] = g[f"best_{source}_rank"].min()
        for k in (20, 60, 100):
            row[f"purchase_rrf_k{k}"] = rrf_for_row(row, k)
        for source in SOURCES:
            row[f"purchase_rrf_without_{source}"] = rrf_for_row(row, 60, source)
        row["map_ready"] = bool(row["accord_count"] > 0 and row["note_count"] > 0 and not row["map_identity_conflict"])
        rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["has_hwahae_signal", "best_hwahae_rank", "purchase_rrf_k60"],
                           ascending=[False, True, False], na_position="last").reset_index(drop=True)


def select_representatives(map_ids: pd.DataFrame) -> pd.DataFrame:
    ready = map_ids[map_ids.map_ready].copy()
    hw = ready[ready.has_hwahae_signal].sort_values(["best_hwahae_rank", "purchase_rrf_k60"], ascending=[True, False])
    chosen_ids = list(hw.map_identity_id)
    purchase = ready[ready.has_purchase_signal].sort_values(
        ["purchase_rrf_k60", "best_hwahae_rank"], ascending=[False, True], na_position="last")
    chosen_ids.extend(x for x in purchase.map_identity_id if x not in set(chosen_ids))
    chosen_ids = list(dict.fromkeys(chosen_ids))
    order = {mid: i + 1 for i, mid in enumerate(chosen_ids)}
    out = map_ids.copy()
    out["selection_rank"] = out.map_identity_id.map(order)
    out["selection_status"] = "NOT_SELECTED"
    out.loc[out.selection_rank.between(1, 200), "selection_status"] = "TOP200"
    out.loc[out.selection_rank.between(201, 220), "selection_status"] = "RESERVE"
    hw_ids = set(hw.map_identity_id)
    out["selection_basis"] = np.where(
        out.map_identity_id.isin(hw_ids), "HWAHAE_MAP_READY_INCLUSION",
        np.where(out.selection_status.isin(["TOP200", "RESERVE"]), "PURCHASE_RRF_FILL", "BELOW_CUTOFF"),
    )
    return out.sort_values("selection_rank", na_position="last").reset_index(drop=True)


def selection_ids(map_ids: pd.DataFrame, score_col: str, n: int = 200) -> list[str]:
    ready = map_ids[map_ids.map_ready]
    hw = ready[ready.has_hwahae_signal].sort_values(["best_hwahae_rank", score_col], ascending=[True, False])
    ordered = list(hw.map_identity_id)
    purchase = ready[ready.has_purchase_signal].sort_values(
        [score_col, "best_hwahae_rank"], ascending=[False, True], na_position="last")
    ordered.extend(x for x in purchase.map_identity_id if x not in set(ordered))
    return list(dict.fromkeys(ordered))[:n]


def set_overlap_metrics(reference: list[str], alternative: list[str]) -> tuple[int, float]:
    a, b = set(reference), set(alternative)
    return len(a & b), len(a & b) / len(a | b) if a | b else 1.0


def knn_from_distance(distance: np.ndarray, k: int) -> np.ndarray:
    d = distance.copy()
    np.fill_diagonal(d, np.inf)
    return np.argpartition(d, kth=k, axis=1)[:, :k]


def knn_overlap(distance: np.ndarray, coords: np.ndarray, k: int = 10) -> float:
    from scipy.spatial.distance import pdist, squareform
    low = squareform(pdist(coords))
    a, b = knn_from_distance(distance, k), knn_from_distance(low, k)
    return float(np.mean([len(set(x) & set(y)) / k for x, y in zip(a, b)]))


def build_map(selected: pd.DataFrame, perfumes: pd.DataFrame):
    import umap

    ordered = selected.sort_values("selection_rank")
    ids = ordered.fragrantica_id.astype(int).tolist()
    rows = perfumes.set_index("id").loc[ids].reset_index()
    known_notes = set(sm.load_note_idf())
    rows["accord_list"] = rows.accords.map(sm.parse_accords)
    rows["note_set"] = rows.apply(sm.parse_notes, axis=1, known_vocab=known_notes)
    idf = sm.load_note_idf()
    similarity, _, _ = sm.base_similarity(rows.accord_list.tolist(), rows.note_set.tolist(), idf)
    distance = 1.0 - similarity
    np.fill_diagonal(distance, 0.0)
    accords, accord_vocab = sm.build_accord_matrix(rows.accord_list.tolist())
    notes, note_weights, _, _ = sm.build_note_matrix(rows.note_set.tolist(), idf)
    features = np.hstack((accords, notes * note_weights))
    norm = np.linalg.norm(features, axis=1, keepdims=True)
    features = np.divide(features, norm, out=np.zeros_like(features), where=norm > 0)

    layouts = {"pca": PCA(n_components=2, random_state=SEED).fit_transform(features)}
    for nn in (10, 15, 30):
        for md in (0.1, 0.3):
            name = f"umap_nn{nn}_md{md}"
            layouts[name] = umap.UMAP(n_components=2, metric="precomputed", n_neighbors=nn,
                                      min_dist=md, random_state=SEED).fit_transform(distance)
    layout_rows = []
    for name, coords in layouts.items():
        layout_rows.append({
            "layout": name,
            "trust_at_10": trustworthiness(distance, coords, n_neighbors=10, metric="precomputed"),
            "trust_at_20": trustworthiness(distance, coords, n_neighbors=20, metric="precomputed"),
            "knn_overlap_at_10": knn_overlap(distance, coords, 10),
        })
    layout_df = pd.DataFrame(layout_rows)
    umap_df = layout_df[layout_df.layout.str.startswith("umap")]
    best_layout = umap_df.sort_values(["knn_overlap_at_10", "trust_at_10"], ascending=False).iloc[0].layout
    coords = np.asarray(layouts[best_layout], dtype=float)

    cluster_rows, labels_by_k = [], {}
    for k in range(2, min(16, len(rows))):
        labels = AgglomerativeClustering(n_clusters=k, metric="precomputed", linkage="average").fit_predict(distance)
        counts = np.bincount(labels)
        cluster_rows.append({
            "cluster_count": k, "silhouette": silhouette_score(distance, labels, metric="precomputed"),
            "min_cluster_size": int(counts.min()), "max_cluster_size": int(counts.max()),
            "max_cluster_share": float(counts.max() / len(labels)),
        })
        labels_by_k[k] = labels
    cluster_df = pd.DataFrame(cluster_rows)
    valid = cluster_df[(cluster_df.min_cluster_size >= 3) & (cluster_df.max_cluster_share <= 0.5)]
    chosen = valid if len(valid) else cluster_df
    best_k = int(chosen.sort_values("silhouette", ascending=False).iloc[0].cluster_count)
    labels = labels_by_k[best_k]

    cluster_names = {}
    for label in sorted(set(labels)):
        idx = np.flatnonzero(labels == label)
        means = accords[idx].mean(axis=0)
        top = [accord_vocab[i] for i in np.argsort(means)[::-1][:3] if means[i] > 0]
        cluster_names[int(label)] = " / ".join(top)

    nn = knn_from_distance(distance, min(10, len(rows) - 1))
    points = []
    selection_by_id = ordered.set_index("fragrantica_id")
    for i, p in rows.iterrows():
        sel = selection_by_id.loc[int(p.id)]
        points.append({
            "map_identity_id": sel.map_identity_id, "fragrantica_id": int(p.id),
            "brand": p.brand, "name": p["name"], "year": None if pd.isna(p.year) else int(p.year),
            "selection_rank": int(sel.selection_rank), "selection_basis": sel.selection_basis,
            "has_purchase_signal": bool(sel.has_purchase_signal), "has_hwahae_signal": bool(sel.has_hwahae_signal),
            "purchase_rrf_k60": float(sel.purchase_rrf_k60),
            "x": float(coords[i, 0]), "y": float(coords[i, 1]),
            "cluster": int(labels[i]), "cluster_label": cluster_names[int(labels[i])],
            "top_accords": [a for a, _ in p.accord_list[:5]],
            "neighbors": [int(rows.iloc[j].id) for j in nn[i]],
        })
    payload = {
        "schema_version": 1, "selection": "Korean purchase RRF + Hwahae map-ready inclusion",
        "layout": best_layout, "cluster_count": best_k,
        "cluster_labels": {str(k): v for k, v in cluster_names.items()}, "points": points,
    }
    return payload, layout_df, cluster_df


def write_report(members, commercial, families, map_ids, elapsed, attempted_families, family_queue_count,
                 layout_df=None, cluster_df=None, map_payload=None):
    overlap_counts = members[members.origin == "hwahae"].purchase_overlap_status.value_counts()
    match_counts = commercial.loc[commercial.fragrantica_match_attempted, "fragrantica_match_status"].value_counts()
    attempted = int(commercial.fragrantica_match_attempted.sum())
    skipped = len(commercial) - attempted
    ready = int(map_ids.map_ready.sum()) if len(map_ids) else 0
    top = int((map_ids.selection_status == "TOP200").sum()) if len(map_ids) else 0
    reserve = int((map_ids.selection_status == "RESERVE").sum()) if len(map_ids) else 0
    base_ids = selection_ids(map_ids, "purchase_rrf_k60") if len(map_ids) else []
    sensitivity = []
    for label, col in (
        ("RRF k=20", "purchase_rrf_k20"), ("RRF k=100", "purchase_rrf_k100"),
        ("leave out musinsa", "purchase_rrf_without_musinsa"),
        ("leave out oliveyoung", "purchase_rrf_without_oliveyoung"),
        ("leave out lotte", "purchase_rrf_without_lotte"),
    ):
        overlap, jaccard = set_overlap_metrics(base_ids, selection_ids(map_ids, col)) if len(map_ids) else (0, 0.0)
        sensitivity.append((label, overlap, jaccard))
    lines = [
        "# 한국 인기 신호 기반 대표 향수 선정 및 향 지도 생성", "",
        "## 입력과 identity", "",
        f"- 구매 판매상품 행: {int((members.origin == 'purchase').sum())}",
        f"- 화해 행: {int((members.origin == 'hwahae').sum())}",
        f"- Commercial Identity: {len(commercial)}", f"- Candidate Family: {len(families)}",
        f"- Fragrantica MATCH 기반 Map Identity: {len(map_ids)}", f"- map-ready Map Identity: {ready}", "",
        "## 독립 상태 집계", "",
        "### purchase_overlap_status (화해 100개)", "",
    ]
    lines += [f"- {s}: {int(overlap_counts.get(s, 0))}" for s in ("MATCH", "MATCH_REVIEW", "NO_MATCH")]
    lines += ["", "### fragrantica_match_status (시도한 Commercial Identity)", ""]
    lines += [f"- {s}: {int(match_counts.get(s, 0))}" for s in ("MATCH", "MATCH_REVIEW", "NO_MATCH")]
    lines += [
        f"- fragrantica_attempted_identity_count: {attempted}",
        f"- fragrantica_skipped_identity_count: {skipped}",
        f"- fragrantica_skipped_ratio: {skipped / len(commercial):.4f}",
        f"- fragrantica_elapsed_time: {elapsed:.3f} seconds",
        f"- attempted Candidate Family: {attempted_families} / queue {family_queue_count}", "",
        "## 선정", "",
        f"- TOP200: {top}", f"- reserve: {reserve}",
        f"- 화해 map-ready inclusion: {int(((map_ids.selection_basis == 'HWAHAE_MAP_READY_INCLUSION') & map_ids.selection_status.isin(['TOP200','RESERVE'])).sum()) if len(map_ids) else 0}",
        "- 화해 rank와 구매 rank는 직접 합산하지 않았다.",
        "- 브랜드·향 계열·군집 quota 및 Fragrantica 글로벌 인기도를 사용하지 않았다.", "",
        "### RRF 민감도 (기준 k=60 TOP200과 비교)", "",
        "| 조건 | 공통 identity | Jaccard |", "|---|---:|---:|",
    ]
    lines += [f"| {label} | {overlap} | {jaccard:.4f} |" for label, overlap, jaccard in sensitivity]
    lines += ["",
        "## 남은 검토", "",
        f"- purchase_overlap_status=MATCH_REVIEW: {int(overlap_counts.get('MATCH_REVIEW', 0))}",
        f"- fragrantica_match_status=MATCH_REVIEW: {int(match_counts.get('MATCH_REVIEW', 0))}",
        "- Fragrantica MATCH_REVIEW는 fuzzy 후보 탐색 결과일 뿐 자동 확정하지 않았다.",
        "- 점진적 매칭 결과 map-ready 220개 미만이면 TOP200/reserve를 완성하지 않고 실제 수만 기록한다.", "",
        "## 지도", "",
        "- TOP200이 200개일 때만 accord·note 기반 UMAP과 사후 군집 검증을 생성한다.",
        "- 군집 수는 2~15를 평가해 silhouette와 크기 조건으로 선택하며 사전에 4개로 고정하지 않는다.",
    ]
    if layout_df is not None and map_payload is not None:
        chosen_layout = map_payload["layout"]
        chosen_row = layout_df.set_index("layout").loc[chosen_layout]
        best_cluster = cluster_df.set_index("cluster_count").loc[map_payload["cluster_count"]]
        lines += [
            f"- 선택 layout: {chosen_layout}",
            f"- trust@10: {chosen_row.trust_at_10:.4f}",
            f"- kNN overlap@10: {chosen_row.knn_overlap_at_10:.4f}",
            f"- 사후 선택 cluster 수: {map_payload['cluster_count']}",
            f"- cluster silhouette: {best_cluster.silhouette:.4f}",
        ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate(members, commercial, map_ids, original_hashes):
    hw = members[members.origin == "hwahae"]
    assert len(hw) == 100
    assert set(hw.purchase_overlap_status) <= ALLOWED_MATCH_STATUS
    source_overlap = pd.read_csv(HWAHAE_PATH).overlap_status.astype(str).tolist()
    assert hw.purchase_overlap_status.astype(str).tolist() == source_overlap
    purchase_ids = set(members.loc[members.origin == "purchase", "commercial_identity_id"])
    for ref in hw.matched_purchase_commercial_identity_id.dropna():
        if ref:
            assert ref in purchase_ids
    attempted = commercial.fragrantica_match_attempted
    assert commercial.loc[~attempted, "fragrantica_match_status"].eq("").all()
    assert set(commercial.loc[attempted, "fragrantica_match_status"]) <= ALLOWED_MATCH_STATUS
    assert commercial.loc[commercial.fragrantica_match_status == "MATCH", "fragrantica_id"].notna().all()
    assert not commercial.loc[commercial.fragrantica_match_status != "MATCH", "fragrantica_id"].notna().any()
    if len(map_ids):
        assert not map_ids.fragrantica_id.duplicated().any()
        assert map_ids.loc[map_ids.map_ready, "accord_count"].gt(0).all()
        assert map_ids.loc[map_ids.map_ready, "note_count"].gt(0).all()
        hw_no_overlap_ready = map_ids[
            map_ids.has_hwahae_signal & map_ids.map_ready & map_ids.purchase_overlap_statuses.str.contains("NO_MATCH", na=False)
        ]
        assert hw_no_overlap_ready.selection_basis.eq("HWAHAE_MAP_READY_INCLUSION").all()
        matched_overlap_no_fragrantica = commercial[
            commercial.purchase_overlap_status.str.contains("MATCH", na=False)
            & (commercial.fragrantica_match_status != "MATCH")
        ]
        mapped_commercial = "|".join(map_ids.commercial_identity_ids.astype(str))
        assert all(ci not in mapped_commercial for ci in matched_overlap_no_fragrantica.commercial_identity_id)
    for path, before in original_hashes.items():
        assert sha256(path) == before, f"input changed: {path}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-map", action="store_true", help="identity/matching/selection outputs only")
    parser.add_argument("--out-suffix", default="",
                        help="append to every output filename stem so existing outputs stay untouched")
    args = parser.parse_args()
    if args.out_suffix:
        # 기존 산출물을 남긴 A/B 비교를 위해 출력 경로만 갈아끼운다. 계산 로직은 그대로다.
        scope = globals()
        for name in ("MEMBERS_OUT", "COMMERCIAL_OUT", "FAMILY_OUT", "MAP_IDENTITIES_OUT",
                     "TOP200_OUT", "RESERVE_OUT", "REPORT_OUT", "LAYOUT_OUT", "CLUSTER_OUT", "MAP_OUT"):
            path = scope[name]
            scope[name] = path.with_name(f"{path.stem}{args.out_suffix}{path.suffix}")
        print(f"출력 접미어 '{args.out_suffix}' 적용. 기존 산출물은 건드리지 않는다")
    print(f"검토 브랜드 매핑 {len(REVIEWED_BRAND_MAPPING)}건 로드")
    original_hashes = {path: sha256(path) for path in INPUT_HASHES}
    for path, expected in INPUT_HASHES.items():
        if original_hashes[path] != expected:
            raise RuntimeError(f"unexpected input snapshot: {path} ({original_hashes[path]})")

    purchase = pd.read_csv(PURCHASE_PATH)
    hwahae = pd.read_csv(HWAHAE_PATH)
    perfume_cols = ["id", "name", "brand", "year", "description", "accords"] + sm.NOTE_COLS
    perfumes = pd.read_csv(PERFUME_PATH, usecols=perfume_cols, low_memory=False)
    brand_index = {latin_key(x): x for x in perfumes.brand.dropna().unique() if latin_key(x)}

    members = make_identity_rows(purchase, hwahae, brand_index)
    commercial = aggregate_commercial(members)
    families = aggregate_families(commercial)
    commercial, elapsed, attempted_families, queue_count = progressive_match(commercial, families, perfumes)
    map_ids = build_map_identities(commercial, perfumes)
    map_ids = select_representatives(map_ids) if len(map_ids) else map_ids

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    members.to_csv(MEMBERS_OUT, index=False)
    commercial.to_csv(COMMERCIAL_OUT, index=False)
    families.to_csv(FAMILY_OUT, index=False)
    map_ids.to_csv(MAP_IDENTITIES_OUT, index=False)
    map_ids[map_ids.selection_status == "TOP200"].to_csv(TOP200_OUT, index=False)
    map_ids[map_ids.selection_status == "RESERVE"].to_csv(RESERVE_OUT, index=False)

    payload = layout_df = cluster_df = None
    if not args.skip_map and (map_ids.selection_status == "TOP200").sum() == 200:
        payload, layout_df, cluster_df = build_map(map_ids[map_ids.selection_status == "TOP200"], perfumes)
        layout_df.to_csv(LAYOUT_OUT, index=False)
        cluster_df.to_csv(CLUSTER_OUT, index=False)
        MAP_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(members, commercial, families, map_ids, elapsed, attempted_families, queue_count,
                 layout_df, cluster_df, payload)
    validate(members, commercial, map_ids, original_hashes)

    print(f"purchase rows={len(purchase)} hwahae rows={len(hwahae)}")
    print(f"commercial identities={len(commercial)} candidate families={len(families)}")
    print("purchase overlap=" + json.dumps(members[members.origin == 'hwahae'].purchase_overlap_status.value_counts().to_dict()))
    print("fragrantica match=" + json.dumps(commercial.loc[commercial.fragrantica_match_attempted, 'fragrantica_match_status'].value_counts().to_dict()))
    print(f"map identities={len(map_ids)} map-ready={int(map_ids.map_ready.sum()) if len(map_ids) else 0}")
    print(f"top200={int((map_ids.selection_status == 'TOP200').sum()) if len(map_ids) else 0} reserve={int((map_ids.selection_status == 'RESERVE').sum()) if len(map_ids) else 0}")


if __name__ == "__main__":
    main()
