"""
유튜브 관련 유틸리티 함수들

이 모듈은 유튜브 API를 사용한 영상 검색 및 렌더링 관련 함수들을 포함합니다.
"""

# 표준 라이브러리
import os
import re

# 외부 모듈
from googleapiclient.discovery import build
from rich.console import Console

console = Console()

# API 키
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# 불용어 목록
# 불용어 목록
STOPWORDS = [
    "추천","일정","시간","도착","출발","점심","저녁","식사",
    "활동","옵션","코스","계획",
    "그럼","그러면","관련된","보여줘","해줘"
]


def clean_query(text: str):
    """질문에서 불필요한 단어 제거 (카카오 API 검색 정확도 향상)"""
    text = re.sub(r"[^가-힣A-Za-z0-9 ]", " ", text)
    tokens = [t for t in text.split() if t not in STOPWORDS and len(t) > 1]
    return " ".join(tokens)


def yt_search(query: str, max_results: int = 3):
    """유튜브 API를 사용해 여행 브이로그, 맛집 리뷰 등 다양한 영상 검색"""
    if not YOUTUBE_API_KEY:
        return []
    
    # 유튜브 API 클라이언트 생성
    yt = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    
    # 검색어 정리 (불필요한 접속사, 조사, 문장 끝 표현 제거)
    cleaned_query = clean_query(query)
    
    # ✅ 개선된 검색어 생성 시스템
    search_queries = []
    
    # 장소명만 추출 (브이로그, 맛집 등의 키워드 제거)
    place_name = cleaned_query
    
    # 불필요한 키워드들을 제거
    remove_keywords = ["브이로그", "vlog", "VLOG", "보여줘", "추천", "관련", "영상", "비디오"]
    for keyword in remove_keywords:
        if keyword in cleaned_query:
            place_name = place_name.replace(keyword, "").strip()
    
    # 맛집, 카페 키워드는 별도 처리
    if "맛집" in cleaned_query:
        place_name = place_name.replace("맛집", "").strip()
    if "카페" in cleaned_query:
        place_name = place_name.replace("카페", "").strip()
    
    # 장소명이 비어있거나 너무 짧으면 원본 쿼리 사용
    if not place_name or len(place_name) < 2:
        place_name = cleaned_query
    
    # ✅ 검색어 타입에 따른 정확한 검색어 생성
    if "브이로그" in cleaned_query or "vlog" in cleaned_query.lower():
        # 브이로그 검색 - 더 구체적인 키워드 사용
        search_queries.append(f'"{place_name}" 브이로그 여행')
        search_queries.append(f'"{place_name}" vlog travel')
        search_queries.append(f'"{place_name}" 여행 브이로그')
    elif "카페" in cleaned_query:
        # 카페 검색 - 카페 관련 브이로그만
        search_queries.append(f'"{place_name}" 카페 브이로그')
        search_queries.append(f'"{place_name}" 카페 vlog')
        search_queries.append(f'"{place_name}" 카페 여행')
    elif "맛집" in cleaned_query or "음식" in cleaned_query or "식당" in cleaned_query:
        # 맛집 검색
        search_queries.append(f'"{place_name}" 맛집 브이로그')
        search_queries.append(f'"{place_name}" 맛집 vlog')
        search_queries.append(f'"{place_name}" 음식 브이로그')
    else:
        # 기본적으로 여행 브이로그 우선 검색
        search_queries.append(f'"{place_name}" 여행 브이로그')
        search_queries.append(f'"{place_name}" travel vlog')
        search_queries.append(f'"{place_name}" 브이로그')
    
    all_items = []
    
    # ✅ 여러 검색어로 검색하여 더 많은 결과 수집
    for search_query in search_queries[:2]:  # 최대 2개 검색어만 사용
        try:
            resp = yt.search().list(
                q=search_query,
                part="snippet",
                type="video",
                maxResults=max_results,
                relevanceLanguage="ko",
                regionCode="KR",
                safeSearch="strict",  # ✅ strict로 변경하여 더 안전한 검색
                order="relevance",  # 관련성 순으로 정렬
                videoDuration="medium",  # ✅ 중간 길이 영상만 (너무 짧거나 긴 영상 제외)
                videoDefinition="high"  # ✅ 고화질 영상만
            ).execute()
            
            # ✅ 검색 결과 파싱 및 필터링
            for it in resp.get("items", []):
                vid = it["id"]["videoId"]
                sn = it["snippet"]
                title = sn["title"]
                description = sn.get("description", "")
                
                # ✅ 부적절한 키워드 필터링
                inappropriate_keywords = [
                    "몰래카메라", "노상방뇨", "가만히 서있다가", "옷이 벗겨진", 
                    "와이프", "순발력", "지렸다", "커플", "자세", "shorts"
                ]
                
                # 제목이나 설명에 부적절한 키워드가 포함되어 있으면 제외
                if any(keyword in title.lower() or keyword in description.lower() 
                       for keyword in inappropriate_keywords):
                    console.log(f"부적절한 영상 제외: {title}")
                    continue
                
                # ✅ 여행/브이로그 관련 키워드가 포함되어 있는지 확인
                travel_keywords = [
                    "여행", "브이로그", "vlog", "travel", "관광", "맛집", "카페", 
                    "부산", "서울", "제주", "경주", "강릉", "대구", "인천", "광주", "대전", "울산",
                    "독도", "울릉도", "영월", "강원도", "전주", "여수", "목포"  # "영월" 등 추가----
                ]
                
                # 제목이나 설명에 여행 관련 키워드가 하나라도 포함되어 있어야 함
                if not any(keyword in title.lower() or keyword in description.lower() 
                          for keyword in travel_keywords):
                    console.log(f"여행 관련 키워드 없음: {title}")
                    continue
                
                # 중복 제거를 위해 video_id로 체크
                if not any(item["video_id"] == vid for item in all_items):
                    all_items.append({
                        "video_id": vid,
                        "title": sn["title"],
                        "channel": sn["channelTitle"],
                        "thumb": sn["thumbnails"]["medium"]["url"],
                        "published": sn["publishedAt"],
                        "desc": sn.get("description", ""),
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "search_query": search_query  # 어떤 검색어로 찾았는지 기록
                    })
                    console.log(f"✅ 적절한 영상 추가: {title}")
        except Exception as e:
            console.log(f"유튜브 검색 오류 ({search_query}): {e}")
            return {
                "success": False,
                "videos": [],
                "message": f"유튜브 검색 중 오류가 발생했습니다. ({str(e)})",
                "html": ""
            }

    
    # 최대 결과 수만큼만 반환
    final_results = all_items[:max_results]
    
    # 결과가 있으면 사용자 친화적인 메시지와 함께 반환
    if final_results:
        console.log(f"✅ 유튜브 검색 성공: {len(final_results)}개 영상 발견")
        return {
            "success": True,
            "videos": final_results,
            "message": f"'{query}'에 대한 {len(final_results)}개의 관련 영상을 찾았습니다!",
            "html": _render_yt_cards(final_results)
        }
    else:
        console.log(f"❌ 유튜브 검색 실패: '{query}'에 대한 결과 없음")
        return {
            "success": False,
            "videos": [],
            "message": f"죄송합니다. '{query}'에 대한 관련 영상을 찾지 못했습니다.",
            "html": ""
        }


def _render_yt_cards(videos: list) -> str:
    """검색된 유튜브 영상 리스트를 카드 형태 HTML로 변환"""
    if not videos:
        return ""
    
    # videos가 딕셔너리인 경우 (새로운 형식)
    if isinstance(videos, dict) and 'videos' in videos:
        videos = videos['videos']
    
    cards = []
    for v in videos:
        cards.append(f"""
        <a class="yt-card" href="{v['url']}" target="_blank" rel="noopener" 
           style="display:block;border:1px solid #eee;border-radius:12px;
                  overflow:hidden;background:#fff;text-decoration:none;
                  box-shadow:0 4px 12px rgba(0,0,0,0.05);">
          <img src="{v['thumb']}" alt="{v['title']}" 
               style="width:100%;height:110px;object-fit:cover;display:block;">
          <div style="padding:8px 10px;">
            <div style="font-size:14px;line-height:1.3;color:#222;
                        max-height:2.6em;overflow:hidden;display:-webkit-box;
                        -webkit-line-clamp:2;-webkit-box-orient:vertical;">
              {v['title']}
            </div>
            <div style="margin-top:4px;font-size:12px;color:#777;">
              {v['channel']}
            </div>
          </div>
        </a>
        """)
    return f"""
    <div class="yt-grid" style="margin-top:12px;display:grid;
                grid-template-columns:repeat(auto-fill,minmax(180px,1fr));
                gap:12px;">
      {''.join(cards)}
    </div>
    """


def _wants_vlog(user_text: str) -> bool:
    """사용자가 브이로그(유튜브 영상)를 원했는지 판별"""
    q = (user_text or "").lower()
    keys = ["브이로그", "vlog", "유튜브", "youtube", "영상 추천", "여행 브이로그"]
    return any(k in q for k in keys)
