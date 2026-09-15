"""자연어 향수 추천 — FastAPI 예시.

`nlr_reference.py` 를 감싸는 얇은 층입니다. 그대로 쓰셔도 되고 참고만 하셔도 됩니다.

띄우는 법
--------
    pip install fastapi uvicorn pandas numpy

    export NLR_PERFUMES_CSV=/data/perfumes.csv
    export NLR_LEXICON_CSV=/data/domain_lexicon_v1_2.csv
    export NLR_ACCORD_CSV=/data/10_accord_dictionary.csv

    uvicorn app_example:app --host 0.0.0.0 --port 8000

    curl -X POST localhost:8000/nlr/recommend \
         -H 'Content-Type: application/json' \
         -d '{"text": "빨래 냄새 나는 향수 찾고 있어"}'

기동 시 한 번만 인덱스를 만듭니다. **요청마다 만들면 안 됩니다** —
`perfumes.csv` 127MB 를 읽고 131,930 x 92 행렬(약 48MB)을 올립니다.

[제안] 이 파일 전체가 제안입니다. 경로·포트·엔드포인트 이름은 담당자분이 정하시면 됩니다.
       바꾸면 안 되는 것은 `nlr_reference.py` 의 검색·정렬 규칙뿐입니다.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from nlr_reference import load_index, recommend

logger = logging.getLogger("nlr")

# [측정] spec.md 3장 1 — 설문 실측 최대 입력이 600자라 500자로는 부족합니다.
MAX_QUERY_CHARS = 1000
# [제안] 요구사항 NLR-01 의 "3~5개"
DEFAULT_TOP_K = 5

_state: dict = {}


def _required_env(name: str) -> str:
    """환경변수를 읽고 없으면 기동을 막는다. str."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"환경변수 {name} 가 필요합니다. "
            "NLR_PERFUMES_CSV / NLR_LEXICON_CSV / NLR_ACCORD_CSV 세 개를 모두 지정하십시오."
        )
    return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    """기동 시 인덱스를 한 번 만들고 종료 시 비운다."""
    started = time.perf_counter()
    _state["index"] = load_index(
        perfumes_csv=_required_env("NLR_PERFUMES_CSV"),
        lexicon_csv=_required_env("NLR_LEXICON_CSV"),
        accord_csv=_required_env("NLR_ACCORD_CSV"),
        verify=True,          # accord 보유 수가 마스터와 다르면 기동을 중단합니다
    )
    elapsed = time.perf_counter() - started
    logger.info("인덱스 적재 완료 — 향수 %s개, %.1f초",
                f"{_state['index']['n_perfumes']:,}", elapsed)
    _state["loaded_seconds"] = round(elapsed, 1)
    yield
    _state.clear()


app = FastAPI(
    title="자연어 향수 추천",
    version="1.0.0",
    description="한국어 문장에서 향 조건을 뽑아 향수를 추천합니다. "
                "규칙은 search_rules.md 를 보십시오.",
    lifespan=lifespan,
)


class RecommendRequest(BaseModel):
    """추천 요청."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=MAX_QUERY_CHARS,
        description="사용자가 입력한 한국어 문장",
        examples=["빨래 냄새 나는 향수 찾고 있어"],
    )
    conditions: dict | None = Field(
        default=None,
        description="LLM 구조화 결과(spec.md 3장 2-a 형식). "
                    "없으면 사전 문자열 매칭만 씁니다. "
                    "커버리지가 77.7%에서 35.7%로 떨어지지만 동작은 합니다.",
        examples=[{"scent_preference": [], "avoid": ["머스크"],
                   "additional_requirements": ["빨래 냄새", "이불 같은 느낌"]}],
    )
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=20)


@app.get("/health")
def health():
    """기동 상태와 적재 규모. dict."""
    index = _state.get("index")
    if index is None:
        raise HTTPException(status_code=503, detail="인덱스가 아직 적재되지 않았습니다")
    return {
        "status": "ok",
        "perfume_count": index["n_perfumes"],
        "accord_count": len(index["accords"]),
        "lexicon_expressions": len(index["lexicon_by_expression"]),
        "loaded_seconds": _state.get("loaded_seconds"),
    }


@app.post("/nlr/recommend")
def nlr_recommend(request: RecommendRequest):
    """한국어 문장으로 향수를 추천한다.

    응답의 `status` 네 가지를 화면에서 구분해 주십시오.

      OK             조건을 다 만족하는 결과입니다
      OK_RELAXED     조건을 넓혀서 찾았습니다. 사용자에게 알려주십시오
      NO_CONDITION   향 조건을 하나도 못 뽑았습니다 (실측 22.3%)
                     인기 향수를 대신 보여주지 마십시오 — 근거가 없습니다
      NO_RESULT      조건은 있는데 결과가 없습니다 (현재 발생하지 않습니다)

    자세한 내용은 search_rules.md 5장.
    """
    index = _state.get("index")
    if index is None:
        raise HTTPException(status_code=503, detail="인덱스가 아직 적재되지 않았습니다")

    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="빈 문자열은 처리하지 않습니다")

    started = time.perf_counter()
    result = recommend(index, text, request.conditions, top_k=request.top_k)
    result["diagnostics"]["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)

    # [제안] 미매칭 로그. spec.md 4.4 — 3회 이상 쌓이면 사전 승격 후보로 올립니다.
    # 어떤 표현이 몇 번 막혔는지가 사전을 키울 유일한 단서이므로 1일차부터 켜 주십시오.
    if result["status"] == "NO_CONDITION":
        logger.info("nlr_unmatched text=%r", text)

    return result
