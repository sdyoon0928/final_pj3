"""
지식 검색 관련 유틸리티 함수들

이 모듈은 위키백과, SerpAPI 등을 사용한 외부 지식 검색 관련 함수들을 포함합니다.
"""

# 표준 라이브러리
import os

# 외부 모듈
import wikipedia
from serpapi.google_search import GoogleSearch
from rich.console import Console

console = Console()

# API 키
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")


def search_external_knowledge(query: str):
    """위키백과 + SerpAPI 기반 외부 지식 검색"""
    wikipedia.set_lang("ko")   # 한국어 위키백과 사용
    wiki_summary, serp_snippets = "", ""

    # 위키백과 요약 검색
    try:
        wiki_summary = wikipedia.summary(query, sentences=2)
    except Exception:
        pass

    # SerpAPI 검색 (웹 스니펫 추출)
    try:
        if SERPAPI_API_KEY:
            search = GoogleSearch({
                "q": query,
                "hl": "ko",
                "gl": "kr",
                "api_key": SERPAPI_API_KEY,
                "num": 3
            })
            results = search.get_dict()
            snippets = [
                item.get("snippet") for item in results.get("organic_results", [])
                if item.get("snippet")
            ]
            serp_snippets = "\n".join(snippets[:3])
    except Exception:
        pass

    # 최종 문자열 조립
    external_info = ""
    if wiki_summary:
        external_info += f"📚 위키백과 요약:\n{wiki_summary}\n"
    if serp_snippets:
        external_info += f"🌐 웹 검색 결과:\n{serp_snippets}\n"

    return external_info if external_info else None
