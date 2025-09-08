from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from openai import OpenAI
from .models import ChatMessage, ChatSession, Place, Schedule   # ✅ 일정/채팅/장소 모델
import os, re, requests, json
from googleapiclient.discovery import build
from markdown import markdown
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

# LangChain 관련
import wikipedia
from serpapi.google_search import GoogleSearch
from langchain.agents import initialize_agent, Tool
from langchain_community.chat_models import ChatOpenAI

# -------------------- API 키 --------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
KAKAO_API_KEY = os.getenv("KAKAO_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

# OpenAI 기본 클라이언트 (LangChain이 아닌 직접 호출용)
client = OpenAI(api_key=OPENAI_API_KEY)


# -------------------- 유튜브 검색 함수 --------------------
def yt_search(query: str, max_results: int = 3):
    """유튜브 API로 여행 브이로그 검색"""
    if not YOUTUBE_API_KEY:
        return []
    yt = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    resp = yt.search().list(
        q=f"{query} 여행 브이로그 추천",
        part="snippet",
        type="video",
        maxResults=max_results,
        relevanceLanguage="ko",
        regionCode="KR",
        safeSearch="moderate"
    ).execute()

    items = []
    for it in resp.get("items", []):
        vid = it["id"]["videoId"]
        sn = it["snippet"]
        items.append({
            "video_id": vid,
            "title": sn["title"],
            "channel": sn["channelTitle"],
            "thumb": sn["thumbnails"]["medium"]["url"],
            "published": sn["publishedAt"],
            "desc": sn.get("description", ""),
            "url": f"https://www.youtube.com/watch?v={vid}"
        })
    return items


def _render_yt_cards(videos: list) -> str:
    """검색된 유튜브 영상을 카드 형태 HTML로 변환"""
    if not videos:
        return ""
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
    <div class="yt-grid" 
         style="margin-top:12px;display:grid;
                grid-template-columns:repeat(auto-fill,minmax(180px,1fr));
                gap:12px;">
      {''.join(cards)}
    </div>
    """


def _wants_vlog(user_text: str) -> bool:
    """사용자가 브이로그(유튜브 영상)를 요청했는지 판별"""
    q = (user_text or "").lower()
    keys = ["브이로그", "vlog", "유튜브", "youtube", "영상 추천", "여행 브이로그"]
    return any(k in q for k in keys)


# -------------------- 카카오 지도 --------------------
STOPWORDS = ["추천","일정","시간","도착","출발","점심","저녁","식사","활동","옵션","여행","코스","계획"]

def clean_query(text: str):
    """질문에서 불필요 단어 제거"""
    text = re.sub(r"[^가-힣A-Za-z0-9 ]", " ", text)
    tokens = [t for t in text.split() if t not in STOPWORDS and len(t) > 1]
    return " ".join(tokens)

def kakao_geocode(query: str):
    """카카오 API를 활용한 장소 좌표 변환"""
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    r = requests.get(url, headers=headers, params={"query": query})
    data = r.json()
    if data.get("documents"):
        doc = data["documents"][0]
        return float(doc["y"]), float(doc["x"]), doc["place_name"]
    return None


# -------------------- 외부 지식 검색 --------------------
def search_external_knowledge(query: str):
    """위키백과 + SerpAPI 기반 외부 지식 검색"""
    wikipedia.set_lang("ko")
    wiki_summary = ""
    serp_snippets = ""

    try:
        wiki_summary = wikipedia.summary(query, sentences=2)
    except Exception:
        pass

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

    external_info = ""
    if wiki_summary:
        external_info += f"📚 위키백과 요약:\n{wiki_summary}\n"
    if serp_snippets:
        external_info += f"🌐 웹 검색 결과:\n{serp_snippets}\n"

    return external_info if external_info else None


# -------------------- 챗봇 --------------------
def chatbot_view(request):
    """챗봇 메인 뷰 (대화 처리 및 세션 관리)"""

    # -------------------- 세션 불러오기 --------------------
    session_id = request.GET.get("session_id")   # GET 파라미터에서 session_id 가져오기
    session = None

    if session_id and request.user.is_authenticated:
        # 사용자가 로그인했고 session_id가 들어온 경우 → 해당 세션 불러오기
        session = ChatSession.objects.filter(id=session_id, user=request.user).first()
        if session:
            request.session["chat_session_id"] = session.id
    elif "chat_session_id" in request.session and request.user.is_authenticated:
        # 브라우저 세션에 chat_session_id가 이미 저장되어 있다면 불러오기
        session = ChatSession.objects.filter(
            id=request.session["chat_session_id"], user=request.user
        ).first()

    if not session and request.user.is_authenticated:
        # 세션이 전혀 없다면 새로 생성
        session = ChatSession.objects.create(user=request.user)
        request.session["chat_session_id"] = session.id

    # -------------------- POST 요청 (사용자 입력 처리) --------------------
    if request.method == "POST":
        if not request.user.is_authenticated:
            # 로그인하지 않은 상태에서 입력 시 로그인 필요 메시지 반환
            return JsonResponse({"login_required": True}, status=200)

        # 사용자가 보낸 입력
        user_input = request.POST.get("message", "").strip()

        # ✅ 일정 저장 버튼 활성화 여부 (프론트에 전달하기 위해 플래그 생성)
        save_button_enabled = False

        # ✅ 세션 제목 자동 생성 (단, 제목 없는 세션은 DB 저장하지 않도록 조건 추가)
        if not session.title:
            if "일정" in user_input:
                session.title = "🗓 여행 일정 추천"
                save_button_enabled = True   # 일정일 경우에만 저장 버튼 활성화
            elif "맛집" in user_input:
                session.title = "🍴 맛집 추천"
            elif "브이로그" in user_input or "유튜브" in user_input:
                session.title = "🎥 여행 브이로그 추천"
            else:
                # ⚠️ 일반 질문인데 제목이 없으면 저장하지 않고 넘어감
                # session.title = user_input[:20] ← 제거
                session.title = None

            # 제목이 실제로 채워졌을 때만 저장
            if session.title:
                session.save()

        # ✅ 사용자 메시지 DB 저장 (단, 세션이 유효할 때만)
        if session.title:  # 제목이 있는 세션만 메시지 저장
            ChatMessage.objects.create(session=session, role="user", content=user_input)

        # -------------------- LLM 초기화 --------------------
        llm = ChatOpenAI(
            model_name=OPENAI_CHAT_MODEL,
            temperature=0.4,
            openai_api_key=OPENAI_API_KEY,
            request_timeout=60
        )

        # -------------------- 분기 처리 --------------------
        if "일정" in user_input:
            # 일정 추천 요청일 경우 → 시스템 프롬프트로 답변 생성
            system_prompt = (
                "너는 대한민국 국내 여행 전문 AI 어시스턴트야. "
                "사용자가 일정 추천을 요청하면 반드시 Day1, Day2 형식으로 나눠서 출력해. "
                "각 Day는 아침/점심/저녁/오전활동/오후활동/저녁후 로 나눠서 "
                "구체적인 장소, 교통수단, 예상 시간, 맛집, 예산을 포함해야 해. "
                "추가로 주의사항과 숨겨진 여행지도 알려줘."
            )
            try:
                result = llm.predict(f"{system_prompt}\n사용자 질문: {user_input}")
            except Exception as e:
                result = f"처리 중 오류 발생: {e}"

        elif _wants_vlog(user_input):
            # 브이로그 관련 요청일 경우 → 유튜브 검색 실행
            youtube_results = yt_search(user_input)
            yt_html = _render_yt_cards(youtube_results)
            reply_html = f"""
            <div style=\"margin-bottom:8px;\">
                {user_input} 관련 브이로그를 추천해드릴게요!<br>
                제가 추천하는 영상들입니다 😊
            </div>
            {yt_html}
            """
            # 어시스턴트 메시지 저장 (단, 세션이 제목 있는 경우만)
            if session.title:
                ChatMessage.objects.create(session=session, role="assistant", content=reply_html)

            return JsonResponse(
                {
                    "reply": "", 
                    "yt_html": reply_html, 
                    "youtube": youtube_results, 
                    "map": [],
                    "save_button_enabled": save_button_enabled,  # ✅ 버튼 상태 전달
                }
            )

        else:
            # 일반 질문일 경우 → LangChain 에이전트 실행
            tools = [
                Tool(name="유튜브검색", func=yt_search, description="유튜브 브이로그 검색"),
                Tool(name="카카오지도검색", func=kakao_geocode, description="카카오 지도 검색"),
                Tool(name="외부지식검색", func=search_external_knowledge, description="외부 지식 검색"),
            ]
            agent = initialize_agent(
                tools,
                llm,
                agent="zero-shot-react-description",
                verbose=False,
                handle_parsing_errors=True,
                max_iterations=6
            )
            try:
                result = agent.run(f"사용자 질문: {user_input}")
            except Exception as e:
                result = "요청하신 정보를 찾는 중 문제가 발생했어요. 😅 다시 시도해주세요."

        # -------------------- 응답 저장 --------------------
        # LLM 답변 중 불필요한 [링크] 제거
        reply_clean = re.sub(r"\[.*?\]", "", result, flags=re.S).strip()
        # 마크다운 → HTML 변환
        reply_html = markdown(reply_clean, extensions=["fenced_code", "nl2br", "tables"])

        # ✅ 세션에 제목이 있을 때만 메시지 저장
        if session.title:
            ChatMessage.objects.create(session=session, role="assistant", content=reply_html)

        # 프론트에 반환 (저장 버튼 상태 포함)
        return JsonResponse(
            {
                "reply": reply_clean, 
                "yt_html": "", 
                "youtube": [], 
                "map": [],
                "save_button_enabled": save_button_enabled,  # ✅ 버튼 상태
            }
        )

    # -------------------- GET 요청 (메인 진입 시) --------------------
    histories = []
    if request.user.is_authenticated:
        # 유저 세션 불러오기 (단, 제목이 없는 세션은 제외)
        sessions = ChatSession.objects.filter(user=request.user).exclude(title__isnull=True).order_by("-created_at")
        for s in sessions:
            histories.append({
                "id": s.id,
                "title": s.title,   # 제목 없음은 아예 DB에 안 들어가기 때문에 바로 출력
            })

    # 템플릿 렌더링
    return render(
        request,
        "pybo/chatbot.html",
        {
            "messages": session.messages.all() if session and session.title else [],  # 제목 있는 세션만 메시지 표시
            "histories": histories,
            "current_session": session if session and session.title else None,
            "kakao_key": KAKAO_API_KEY,
        },
    )


# -------------------- 세션 메시지 로드 --------------------
# ⏰ 2025-09-07 01:28 추가
def load_session_messages(request, session_id):
    """특정 세션의 전체 메시지를 반환"""
    if not request.user.is_authenticated:
        return JsonResponse({"login_required": True}, status=401)
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        messages = ChatMessage.objects.filter(session=session).order_by("created_at")
        data = [{"role": m.role, "content": m.content, "id": m.id} for m in messages]
        return JsonResponse({"messages": data})
    except ChatSession.DoesNotExist:
        return JsonResponse({"error": "세션을 찾을 수 없습니다."}, status=404)


# -------------------- 세션 삭제 --------------------
@csrf_exempt
def delete_session(request, session_id):
    """특정 세션 삭제"""
    if not request.user.is_authenticated:
        return JsonResponse({"login_required": True}, status=401)
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        session.delete()
        return JsonResponse({"success": True})
    except ChatSession.DoesNotExist:
        return JsonResponse({"success": False, "error": "대화를 찾을 수 없습니다."}, status=404)


# -------------------- 로그인/로그아웃/회원가입 --------------------
def login_view(request):
    """로그인 처리"""
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("chatbot")
        else:
            return render(request, "pybo/login.html", {"error": "아이디 또는 비밀번호가 틀렸습니다."})
    return render(request, "pybo/login.html")

def logout_view(request):
    """로그아웃"""
    logout(request)
    return redirect("chatbot")

def register_view(request):
    """회원가입"""
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        if User.objects.filter(username=username).exists():
            return render(request, "pybo/register.html", {"error": "이미 존재하는 아이디입니다."})
        User.objects.create_user(username=username, password=password)
        return redirect("login")
    return render(request, "pybo/register.html")


# -------------------- 여행지 맵 --------------------
def map_view(request):
    """여행지 지도 뷰"""
    places = Place.objects.all()
    return render(request, "pybo/map.html", {
        "places": places,
        "kakao_key": KAKAO_API_KEY
    })


# -------------------- 장소 추가 --------------------
def 장소추가(request):
    """장소 추가 페이지"""
    return render(request, "pybo/장소추가.html")


# -------------------- 일정 저장/조회 --------------------
@csrf_exempt
@login_required
def save_schedule(request):
    """일정을 저장하고 대화 목록에도 추가 (질문 내용이 세션 제목에 반영됨)"""
    if request.method != "POST":
        return JsonResponse({"error": "POST 요청만 허용됩니다."}, status=400)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "로그인이 필요합니다."}, status=401)

    try:
        body = json.loads(request.body.decode('utf-8'))

        # 질문 내용 추출 (body["question"] 또는 body["title"] 사용)
        question = body.get("question") or body.get("title")
        if not question:
            return JsonResponse({"error": "일정 제목 또는 질문이 필요합니다."}, status=400)
        if not body.get("data"):
            return JsonResponse({"error": "일정 데이터가 필요합니다."}, status=400)

        current_session_id = request.session.get("chat_session_id")
        if not current_session_id:
            chat_session = ChatSession.objects.create(
                user=request.user,
                title=question  # 질문 내용으로 세션 제목 지정
            )
            request.session["chat_session_id"] = chat_session.id
        else:
            try:
                chat_session = ChatSession.objects.get(
                    id=current_session_id, user=request.user
                )
                # 세션 제목이 없거나 다르면 질문 내용으로 업데이트
                if not chat_session.title or chat_session.title != question:
                    chat_session.title = question
                    chat_session.save()
            except ChatSession.DoesNotExist:
                chat_session = ChatSession.objects.create(
                    user=request.user,
                    title=question
                )
                request.session["chat_session_id"] = chat_session.id

        # 일정 저장
        schedule = Schedule.objects.create(
            user=request.user,
            title=body["title"],
            data=body["data"]
        )

        return JsonResponse({
            "success": True,
            "id": schedule.id,
            "session_id": chat_session.id,
            "message": "일정이 성공적으로 저장되었습니다."
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "잘못된 JSON 형식입니다."}, status=400)
    except KeyError as e:
        return JsonResponse({"error": f"필수 필드가 누락되었습니다: {str(e)}"}, status=400)
    except Exception as e:
        print(f"일정 저장 중 오류 발생: {str(e)}")
        return JsonResponse({"error": "일정을 저장하는 중에 오류가 발생했습니다."}, status=500)



@login_required
def get_schedule(request, sid):
    """저장된 일정 조회 (질문/세션 제목 + 답변 + 일정 데이터 반환, 해당 일정의 세션 기준)"""
    try:
        schedule = Schedule.objects.get(id=sid, user=request.user)
        # 해당 일정의 세션 찾기: 일정 저장 시 연결된 세션을 찾아야 함
        chat_session = ChatSession.objects.filter(
            user=request.user,
            title=schedule.title
        ).order_by('-created_at').first()
        question = chat_session.title if chat_session else ""
        # assistant 답변 메시지 (가장 최근)
        answer_msg = ChatMessage.objects.filter(session=chat_session, role="assistant").order_by('-created_at').first()
        answer = answer_msg.content if answer_msg else ""
        return JsonResponse({
            "question": question,
            "answer": answer,
            "data": schedule.data
        })
    except Schedule.DoesNotExist:
        return JsonResponse({"error": "일정을 찾을 수 없습니다."}, status=404)

def load_session_messages(request, session_id):
    """특정 세션의 전체 메시지 반환"""
    if not request.user.is_authenticated:
        return JsonResponse({"login_required": True}, status=401)

    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        messages = ChatMessage.objects.filter(session=session).order_by("created_at")
        data = [
            {"role": m.role, "content": m.content, "id": m.id}
            for m in messages
        ]
        return JsonResponse({"messages": data})
    except ChatSession.DoesNotExist:
        return JsonResponse({"error": "세션을 찾을 수 없습니다."}, status=404)
