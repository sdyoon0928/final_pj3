# chatbot/youtube.py
import requests

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

def search_youtube_vlogs(query: str, max_results: int, api_key: str, region_code: str = "KR"):
    """
    query(예: '부산 여행 브이로그')로 유튜브 검색.
    반환: [{title, video_url, thumb_url, channel, published_at}] 리스트
    """
    if not api_key:
        return []

    params = {
        "key": api_key,
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "order": "relevance",
        "safeSearch": "none",
        "regionCode": region_code,
    }
    r = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=12)
    r.raise_for_status()
    items = r.json().get("items", [])
    results = []
    for it in items:
        vid = it["id"]["videoId"]
        sn  = it["snippet"]
        results.append({
            "title": sn.get("title", ""),
            "video_url": f"https://www.youtube.com/watch?v={vid}",
            "thumb_url": (sn.get("thumbnails", {}).get("medium", {}) or sn.get("thumbnails", {}).get("default", {})).get("url", ""),
            "channel": sn.get("channelTitle", ""),
            "published_at": sn.get("publishedAt", ""),
        })
    return results

# chatbot/youtube.py (아래에 추가)
def render_video_cards_html(videos: list) -> str:
    if not videos: 
        return ""
    cards = []
    for v in videos:
        cards.append(f"""
        <a class="yt-card" href="{v['video_url']}" target="_blank" rel="noopener">
          <img src="{v['thumb_url']}" alt="{v['title']}">
          <div class="yt-meta">
            <div class="yt-title">{v['title']}</div>
            <div class="yt-channel">{v['channel']}</div>
          </div>
        </a>
        """)
    return f"""
    <div class="yt-grid">
      {''.join(cards)}
    </div>
    """
