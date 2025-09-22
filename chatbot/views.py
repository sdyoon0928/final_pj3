# -------------------- 표준 라이브러리 --------------------
import os
import json
import random
import requests

# -------------------- Django 및 외부 모듈 --------------------
from django.shortcuts import render, redirect
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from markdown import markdown
from rich.console import Console
from django.contrib import messages  # ⭐ messages 모듈 추가

# -------------------- 로컬 모듈 --------------------
from .models import ChatSession, ChatMessage, Place, Schedule, UserProfile
from .services.chat_handlers import (
    handle_schedule_request,
    handle_vlog_request,
    handle_simple_qna,
    handle_general_request,
)
from .utils.sessions import get_or_create_session
from .utils.youtube import _wants_vlog
from .utils.maps import google_place_details, clean_place_query
from .utils.coordinates import extract_places_from_response, search_place_coordinates
from .utils.coordinate_extractor import extract_coordinates_from_schedule_data, extract_coordinates_from_response, format_places_info
from .forms import FindAccountForm

# -------------------- 전역 변수 --------------------
console = Console()

KAKAO_JS_API_KEY = settings.KAKAO_JS_API_KEY               # 카카오 JavaScript 키 (프론트엔드용)


# ==================== 챗봇 메인 뷰 ====================
def chatbot_view(request):
    """
    챗봇 메인 뷰 (대화 처리 및 세션 관리)
    
    이 함수는 사용자의 메시지를 받아서 적절한 AI 응답을 생성하고 반환합니다.
    요청 유형에 따라 다른 처리 함수를 호출합니다:
    - 일정 관련: handle_schedule_request()
    - 브이로그 관련: handle_vlog_request()
    - 간단한 질문: handle_simple_qna()
    - 일반적인 질문: handle_general_request()
    
    Args:
        request (HttpRequest): Django 요청 객체
        
    Returns:
        JsonResponse: AI 응답 및 관련 데이터
    """

    # -------------------- 세션 불러오기 --------------------
    session_id = request.GET.get("session_id")   # URL 파라미터에서 session_id 가져오기
    session = get_or_create_session(request, session_id)

    # -------------------- POST 요청 처리 --------------------
    if request.method == "POST":
        # 👉 사용자가 메시지를 입력했을 때 실행

        if not request.user.is_authenticated:
            # 로그인이 안 되어 있으면 "로그인 필요" 반환
            return JsonResponse({"login_required": True}, status=200)

        # 사용자가 보낸 메시지 추출
        user_input = request.POST.get("message", "").strip()
        save_button_enabled = False   # 일정 저장 버튼 상태 (기본 False)
        
        # ✅ 좌표 정보가 포함된 장소들 (전역 변수로 설정)
        places_with_coords = []

        # 세션 제목 자동 생성 (첫 메시지에서만 제목 생성)
        if not session.title:
            if "일정" in user_input:
                session.title = "🗓 여행 일정 추천"
                save_button_enabled = True   # 일정 요청일 경우 저장 버튼 활성화
            elif "맛집" in user_input:
                session.title = "🍴 맛집 추천"
            elif "브이로그" in user_input or "유튜브" in user_input:
                session.title = "🎥 여행 브이로그 추천"

            if session.title:
                session.save()   # 세션 제목을 DB에 저장

        # 사용자 메시지를 DB에 저장 (대화 내역 관리)
        if session.title:
            ChatMessage.objects.create(session=session, role="user", content=user_input)

        # -------------------- 병행 구조 --------------------
        try:
            # 대화 히스토리 가져오기 (모든 요청에 대해)
            conversation_history = []
            if session:
                recent_messages = ChatMessage.objects.filter(session=session).order_by('-created_at')[:15]
                for msg in reversed(recent_messages):  # 시간순으로 정렬
                    conversation_history.append(f"{msg.role}: {msg.content}")
                
                # 세션 제목과 관련된 컨텍스트 정보 추가
                if session.title:
                    conversation_history.insert(0, f"세션 제목: {session.title}")
                    conversation_history.insert(1, f"대화 시작 시간: {session.created_at.strftime('%Y-%m-%d %H:%M')}")
            
            # 기존 일정 변경 요청 감지
            is_schedule_modification = any(keyword in user_input for keyword in [
                "일정 변경", "일정 수정", "일정 바꿔", "일정 다시", "일정 재", "일정 수정해", 
                "일정 바꿔줘", "일정 다시 짜", "일정 다시 만들어", "일정 다시 추천",
                "일정 중에", "일정에서", "일정의", "일정을", "일정을 다른거로", "일정을 바꿔"
            ])
            
            if "일정" in user_input:
                # ✅ 일정 관련 요청 처리 → handle_schedule_request 함수 사용 (개선된 버전)
                result, schedule_data = handle_schedule_request(user_input, session, request, is_schedule_modification)
                
                # ✅ 좌표 정보 추출 (개선된 버전)
                if schedule_data:
                    # JSON 데이터에서 직접 좌표 정보 추출
                    places_with_coords = extract_coordinates_from_schedule_data(schedule_data)
                    
                    # JSON에 좌표가 없으면 AI 응답에서 장소명들을 추출하여 좌표 검색
                    if not places_with_coords:
                        places_with_coords = extract_coordinates_from_response(result)
                    
                    # 좌표 정보가 있는 장소들을 응답에 포함
                    if places_with_coords:
                        result += format_places_info(places_with_coords)
                        
                        # 프론트엔드에서 사용할 수 있도록 places 데이터 설정
                        save_button_enabled = True
                        console.log(f"좌표 검색 완료: {len(places_with_coords)}개 장소")  # 디버깅용

            elif ("간단" in user_input or "단답" in user_input or 
                  any(keyword in user_input for keyword in [
                      "주차장", "가성비", "팁", "추천", "어디", "뭐가", "어떤", "어느", 
                      "좋은", "나쁜", "비용", "요금", "가격", "얼마", "시간", "언제",
                      "방법", "어떻게", "왜", "이유", "장점", "단점", "차이", "비교",
                      "주의", "조심", "준비", "필요", "챙겨", "가져", "입장료"
                  ])):
                # ✅ 간단 질문 답변 → handle_simple_qna 함수 사용
                result = handle_simple_qna(user_input)

            # 추가----
            elif _wants_vlog(user_input):
                wants_schedule = "일정" in user_input
                vlog_response = handle_vlog_request(user_input, session)

                if wants_schedule:
                    # 일정도 같이 처리
                    schedule_result, schedule_data = handle_schedule_request(
                        user_input, session, request, is_schedule_modification
                    )
                    places = extract_coordinates_from_schedule_data(schedule_data) or []
                    return JsonResponse({
                        "reply": schedule_result + "\n\n관련 브이로그:\n" + vlog_response.get("reply",""),
                        "yt_html": vlog_response.get("yt_html",""),
                        "youtube": vlog_response.get("youtube", []),
                        "places": places,
                    })
                else:
                    return JsonResponse(vlog_response)
            #== 추가 끝----


            elif "상세" in user_input or "정보" in user_input:
                # ✅ 장소 상세정보 요청 → Google Places API
                query = clean_place_query(user_input)  # 입력 정제
                details = google_place_details(query)

                if details:
                    result = (
                        f"📍 {details.get('name', '이름 없음')}\n"
                        f"주소: {details.get('address', '주소 없음')}\n"
                        f"전화: {details.get('phone', '전화번호 없음')}\n"
                        f"운영시간:\n{details.get('opening_hours', '운영시간 정보 없음')}"
                    )
                else:
                    result = f"'{query}'에 대한 장소 정보를 찾을 수 없습니다."


            else:
                # ✅ 일반적인 여행 관련 질문 → handle_general_request 함수 사용 (세션 전달)
                try:
                    result = handle_general_request(user_input, conversation_history, session)  # 세션 전달
                    
                    # 결과가 너무 짧거나 오류 메시지인 경우 simple_qna로 폴백
                    if (not result or len(result.strip()) < 20 or 
                        "오류" in result or "실패" in result or "문제가 발생" in result):
                        console.log("🔄 handle_general_request 결과가 부적절하여 handle_simple_qna로 폴백")
                        result = handle_simple_qna(user_input)
                    
                    # ✅ 일반 요청에서도 좌표 정보 추출 (새로 추가된 기능 활용)
                    try:
                        # AI 응답에서 장소명들을 추출하여 좌표 검색
                        general_places = extract_coordinates_from_response(result)
                        if general_places:
                            console.log(f"📍 일반 요청에서 좌표 정보 추출: {len(general_places)}개 장소")
                            # places_with_coords에 추가 (지도 표시용)
                            places_with_coords.extend(general_places)
                    except Exception as coord_error:
                        console.log(f"⚠️ 일반 요청 좌표 추출 중 오류: {coord_error}")
                        # 좌표 추출 실패해도 메인 응답은 유지
                        
                except Exception as general_error:
                    console.log(f"❌ handle_general_request 실패: {general_error}")
                    console.log("🔄 handle_simple_qna로 폴백 실행")
                    result = handle_simple_qna(user_input)
        except Exception as e:
            # 예외 발생 시 에러 메시지 반환
            result = f"처리 중 오류 발생: {e}"
            console.log(f"전체 처리 중 예외 발생: {e}")

        # -------------------- 응답 저장 --------------------
        # 1) LLM 결과에서 불필요한 대괄호 [링크] 제거
        reply_clean = result if result else ""
        # 2) 마크다운을 HTML로 변환 (코드블록, 줄바꿈, 테이블 지원)
        reply_html = markdown(reply_clean, extensions=["fenced_code", "nl2br", "tables"])
        # 3) 어시스턴트 답변 DB 저장
        if session.title:
            ChatMessage.objects.create(session=session, role="assistant", content=reply_html)

        # 프론트엔드로 JSON 응답 반환
        response_data = {
            "reply": reply_clean,
            "yt_html": "",
            "youtube": [],
            "map": [],
            "save_button_enabled": save_button_enabled
        }
        
        # ✅ 좌표 정보가 있는 경우 places 데이터 추가 (일정 및 일반 요청 모두)
        if places_with_coords:
            response_data["places"] = places_with_coords
            response_data["map"] = places_with_coords  # 지도 표시용
            console.log(f"JSON 응답에 좌표 정보 포함: {len(places_with_coords)}개 장소")  # 디버깅용

        # 추가----
        # ✅ 🔹여기에 브이로그 추가🔹
        if _wants_vlog(user_input):
            vlog_result = handle_vlog_request(user_input, session, request)  # request 추가
            console.log(f"브이로그 검색어: {vlog_result.get('search_term', '없음')} (세션 ID: {session.id})")
            if isinstance(vlog_result, dict):
                response_data["reply"] += "\n\n" + vlog_result.get("reply", "")
                response_data["yt_html"] = vlog_result.get("yt_html", "")
                response_data["youtube"] = vlog_result.get("youtube", [])
            else:
                response_data["reply"] += "\n\n" + str(vlog_result)
        #== 추가 끝----
        
        return JsonResponse(response_data)

    # -------------------- GET 요청 (메인 페이지) --------------------
    # 👉 POST 요청이 아닌 경우 (예: 사용자가 페이지 처음 접속했을 때)
    histories = []
    if request.user.is_authenticated:
        # 로그인한 사용자의 과거 세션 목록 불러오기
        sessions = ChatSession.objects.filter(user=request.user).exclude(title__isnull=True).order_by("-created_at")
        for s in sessions:
            histories.append({"id": s.id, "title": s.title})   # 세션 ID와 제목만 추출

    # chatbot.html 템플릿 렌더링 + 컨텍스트 데이터 전달
    return render(request, "pybo/chatbot.html", {
        "messages": session.messages.all() if session and session.title else [],   # 현재 세션 메시지
        "histories": histories,                                                   # 과거 세션 목록
        "current_session": session if session and session.title else None,        # 현재 세션
        "kakao_js_key": KAKAO_JS_API_KEY                                          # 카카오 JavaScript API 키 (프론트엔드용)
    })


# -------------------- 세션 메시지 로드 --------------------
def load_session_messages(request, session_id):
    """특정 세션의 전체 메시지를 반환 (Ajax 요청용)"""
    
    # 1) 로그인 여부 확인
    if not request.user.is_authenticated:
        return JsonResponse({"login_required": True}, status=401)
    try:
        # 2) 세션 ID와 현재 로그인한 유저가 일치하는지 확인
        session = ChatSession.objects.get(id=session_id, user=request.user)

        # 3) 해당 세션의 모든 메시지를 시간순 정렬
        messages = ChatMessage.objects.filter(session=session).order_by("created_at")

        # 4) JSON 형태로 변환 (role, content, created_at 포함)
        data = [
            {
                "role": m.role,
                "content": m.content,
                "id": m.id,
                "timestamp": m.created_at.isoformat() if m.created_at else None
            }
            for m in messages
        ]
        # 5) 최종 반환
        return JsonResponse({"messages": data})

    except ChatSession.DoesNotExist:
        # 세션을 찾을 수 없는 경우 (권한 없음 or 잘못된 ID)
        return JsonResponse({"error": "세션을 찾을 수 없습니다."}, status=404)


# -------------------- 세션 삭제 --------------------
@csrf_exempt   # ⚠️ CSRF 토큰 없이도 요청 가능 (보안상 주의, Ajax 편의성)
def delete_session(request, session_id):
    """특정 세션 삭제"""
    
    # 1) 로그인 여부 확인
    if not request.user.is_authenticated:
        return JsonResponse({"login_required": True}, status=401)
    try:
        # 2) 세션 ID와 현재 로그인한 유저가 일치하는지 확인
        session = ChatSession.objects.get(id=session_id, user=request.user)

        # 3) 세션 삭제
        session.delete()

        # 4) 성공 응답 반환
        return JsonResponse({"success": True})

    except ChatSession.DoesNotExist:
        # 세션이 존재하지 않는 경우 (잘못된 ID)
        return JsonResponse(
            {"success": False, "error": "대화를 찾을 수 없습니다."},
            status=404
        )


# -------------------- 로그인 --------------------
def login_view(request):
    """로그인 처리"""

    if request.method == "POST":
        # 1) 사용자가 로그인 폼에서 입력한 값 가져오기
        username = request.POST.get("username")
        password = request.POST.get("password")

        # 2) Django 내장 인증 함수로 사용자 확인
        user = authenticate(request, username=username, password=password)

        if user:
            # 3) 인증 성공 → 로그인 처리 후 챗봇 화면으로 이동
            login(request, user)
            return redirect("chatbot")
        else:
            # 4) 인증 실패 → 다시 로그인 페이지에 오류 메시지 표시
            # return render(
            #     request,
            #     "pybo/login.html",
            #     {"error": "아이디 또는 비밀번호가 틀렸습니다."}
            # )
            # 4) 인증 실패 → messages 프레임워크로 오류 메시지 추가

            # 에러 메시지 2줄 추가----
            messages.error(request, "아이디 또는 비밀번호가 틀렸습니다.")  # ⭐ messages.error 사용
            return render(request, "pybo/login.html")  # ⭐ 오류 메시지 전달 제거
    # GET 요청 → 로그인 페이지 보여주기
    return render(request, "pybo/login.html")


# -------------------- 로그아웃 --------------------
def logout_view(request):
    """로그아웃"""

    # 현재 세션에서 로그인 사용자 정보 제거
    logout(request)

    # 로그아웃 후 챗봇 메인으로 리다이렉트
    return redirect("chatbot")


# -------------------- 회원가입 --------------------
def register_view(request):
    """회원가입"""

    if request.method == "POST":
        # 1) 사용자가 입력한 값 가져오기
        username = request.POST.get("username")
        password = request.POST.get("password")
        name = request.POST.get("name")      # 추가
        phone = request.POST.get("phone")    # 추가

        # 2) 아이디 중복 확인
        if User.objects.filter(username=username).exists():
            # 이미 같은 아이디가 있다면 에러 메시지 반환
            return render(
                request,
                "pybo/register.html",
                {"error": "이미 존재하는 아이디입니다."}
            )
        
        # 3) 새 사용자 생성 (비밀번호는 자동 해싱됨)
        user = User.objects.create_user(username=username, password=password)
        
        # 4) UserProfile 생성
        UserProfile.objects.create(user=user, name=name, phone=phone)

        # 5) 회원가입 완료 → 로그인 페이지로 이동
        return redirect("login")
    
    # GET 요청 → 회원가입 페이지 보여주기
    return render(request, "pybo/register.html")


# -------------------- 여행지 맵 --------------------
def map_view(request):
    """여행지 지도 뷰"""
    
    # DB에 저장된 모든 장소 가져오기
    places = Place.objects.all()
    
    # pybo/map.html 템플릿에 전달
    return render(
        request,
        "pybo/map.html",
        {
            "places": places,        # 지도에 표시할 장소 목록
            "kakao_js_key": KAKAO_JS_API_KEY  # 카카오 JavaScript API 키 (프론트엔드용)
        }
    )


# -------------------- 장소 추가 --------------------
def 장소추가(request):
    """장소 추가 페이지"""
    
    # 단순히 장소 추가 화면 렌더링
    return render(request, "pybo/장소추가.html")


# -------------------- 일정 저장 --------------------
@csrf_exempt           # CSRF 토큰 검사 제외 (AJAX 호출 편의성)
@login_required        # 로그인 필수 (로그인 안 하면 접근 불가)
def save_schedule(request):
    """일정을 저장하고 대화 목록에도 추가 (질문 내용이 세션 제목에 반영됨)"""
    
    # 1) POST 요청만 허용
    if request.method != "POST":
        return JsonResponse({"error": "POST 요청만 허용됩니다."}, status=400)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
    try:
        # 2) JSON Body 파싱
        body = json.loads(request.body.decode('utf-8'))

        # 3) 질문/제목 확인 (질문 없으면 일정 제목 사용)
        question = body.get("question") or body.get("title")
        if not question:
            return JsonResponse({"error": "일정 제목 또는 질문이 필요합니다."}, status=400)

        # 4) 일정 데이터 유효성 확인
        if not body.get("data"):
            return JsonResponse({"error": "일정 데이터가 필요합니다."}, status=400)

        # 5) 현재 세션 확인 (없으면 새로 생성)
        current_session_id = request.session.get("chat_session_id")
        if not current_session_id:
            # 세션이 없으면 새로 생성
            chat_session = ChatSession.objects.create(
                user=request.user,
                title=question   # 질문 내용으로 세션 제목 설정
            )
            request.session["chat_session_id"] = chat_session.id
        else:
            try:
                # 기존 세션 불러오기
                chat_session = ChatSession.objects.get(
                    id=current_session_id, user=request.user
                )
                # 세션 제목이 없거나 기존 제목과 다르면 업데이트
                if not chat_session.title or chat_session.title != question:
                    chat_session.title = question
                    chat_session.save()
            except ChatSession.DoesNotExist:
                # 세션이 존재하지 않으면 새로 생성
                chat_session = ChatSession.objects.create(
                    user=request.user,
                    title=question
                )
                request.session["chat_session_id"] = chat_session.id

        # 6) 일정 저장 (Schedule 모델에 저장)
        # 세션에서 JSON 데이터 가져오기
        schedule_json = request.session.get('schedule_json', {})
        
        # JSON 데이터 우선 사용, 없으면 요청 데이터 사용
        schedule_data = schedule_json if schedule_json else body["data"]
        
        # 일정 데이터가 비어있으면 기본 구조 생성
        if not schedule_data or schedule_data == {}:
            schedule_data = {
                "schedule": {
                    "Day1": {
                        "오전활동": {
                            "장소": "추천 장소",
                            "시간": "09:00-11:00",
                            "비용": "예상 비용",
                            "주의사항": "주의사항"
                        },
                        "점심": {
                            "장소": "추천 맛집",
                            "시간": "11:30-12:30",
                            "비용": "예상 비용",
                            "주의사항": "주의사항"
                        },
                        "오후활동": {
                            "장소": "추천 장소",
                            "시간": "13:00-17:00",
                            "비용": "예상 비용",
                            "주의사항": "주의사항"
                        },
                        "저녁": {
                            "장소": "추천 맛집",
                            "시간": "18:00-19:30",
                            "비용": "예상 비용",
                            "주의사항": "주의사항"
                        }
                    }
                },
                "summary": "추천 코스"
            }
        
        schedule = Schedule.objects.create(
            user=request.user,
            title=body["title"],    # 일정 제목
            data=schedule_data      # 일정 데이터
        )
        # 세션 ID별로 schedule_json 저장 추가----
        request.session[f'schedule_json_{chat_session.id}'] = schedule_data

        # 7) 성공 응답 반환
        return JsonResponse({
            "success": True,
            "id": schedule.id,
            "session_id": chat_session.id,
            "message": "일정이 성공적으로 저장되었습니다."
        })

    except ValueError:
        # JSON 형식이 잘못된 경우
        return JsonResponse({"error": "잘못된 JSON 형식입니다."}, status=400)
    except KeyError as e:
        # 필수 필드가 누락된 경우
        return JsonResponse({"error": f"필수 필드가 누락되었습니다: {str(e)}"}, status=400)
    except Exception as e:
        # 알 수 없는 오류
        print(f"일정 저장 중 오류 발생: {str(e)}")
        return JsonResponse({"error": "일정을 저장하는 중에 오류가 발생했습니다."}, status=500)


# -------------------- 일정 조회 --------------------
@login_required
def get_schedule(request, sid):
    """저장된 일정 JSON을 그대로 반환 (지도에서 바로 사용)"""
    try:
        schedule = Schedule.objects.get(id=sid, user=request.user)
        return JsonResponse(schedule.data, safe=False)
    except Schedule.DoesNotExist:
        return JsonResponse({"error": "일정을 찾을 수 없습니다."}, status=404)


# -------------------- 세션 → 일정 매핑 조회 --------------------
@login_required
def find_schedule_by_session(request, session_id):
    """세션 ID로 최근 저장된 일정 ID를 찾는다 (세션 제목과 일정 제목 매칭)"""
    try:
        chat_session = ChatSession.objects.get(id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return JsonResponse({"error": "세션을 찾을 수 없습니다."}, status=404)

    if not chat_session.title:
        return JsonResponse({"error": "세션에 제목이 없어 일정과 매칭할 수 없습니다."}, status=404)

    schedule = (
        Schedule.objects
        .filter(user=request.user, title=chat_session.title)
        .order_by('-created_at')
        .first()
    )
    if not schedule:
        # 일정이 없는 경우 빈 응답 반환 (404 대신 200)
        return JsonResponse({"message": "해당 세션과 매칭되는 일정이 없습니다."}, status=200)

    return JsonResponse({"schedule_id": schedule.id})


# ==================== 경로 API 엔드포인트 ====================
@csrf_exempt
def get_route(request):
    """자동차(카카오) + 대중교통(Google) 통합 길찾기 API 엔드포인트"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST 요청만 허용됩니다.'}, status=405)

    try:
        data = json.loads(request.body)
        origin = data.get('origin', {})
        destination = data.get('destination', {})
        waypoints = data.get('waypoints', [])
        priority = (data.get('priority') or 'RECOMMEND').upper()
        if priority not in ['RECOMMEND', 'TIME', 'DISTANCE']:
            priority = 'RECOMMEND'
        mode = (data.get('mode') or 'RECOMMEND').upper()

        print(f"요청 데이터: origin={origin}, destination={destination}, waypoints={waypoints}, mode={mode}")

        # 필수 파라미터 검증
        if not origin or not destination:
            return JsonResponse({'error': '출발지와 도착지는 필수입니다.'}, status=400)

        # 좌표 유효성 검사
        try:
            origin_x, origin_y = float(origin.get('x', 0)), float(origin.get('y', 0))
            dest_x, dest_y = float(destination.get('x', 0)), float(destination.get('y', 0))
            for x, y, name in [(origin_x, origin_y, '출발지'), (dest_x, dest_y, '도착지')]:
                if not (-180 <= x <= 180) or not (-90 <= y <= 90):
                    return JsonResponse({'error': f'{name} 좌표가 유효하지 않습니다.'}, status=400)
        except (ValueError, TypeError) as e:
            return JsonResponse({'error': f'좌표 형식 오류: {str(e)}'}, status=400)

        # 대중교통 모드 (Google Directions)
        if mode == 'TRANSIT':
            GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
            if not GOOGLE_API_KEY:
                return JsonResponse({"error": "GOOGLE_API_KEY 미설정"}, status=500)

            g_url = "https://maps.googleapis.com/maps/api/directions/json"
            params = {
                'origin': f"{origin_y},{origin_x}",
                'destination': f"{dest_y},{dest_x}",
                'mode': 'transit',
                'language': 'ko',
                'alternatives': 'false',
                'departure_time': 'now',
                'key': GOOGLE_API_KEY,
            }
            g_resp = requests.get(g_url, params=params)
            g_data = g_resp.json()
            if g_data.get('status') != 'OK' or not g_data.get('routes'):
                return JsonResponse({
                    "error": "Google Directions 실패",
                    "provider": "google_transit",
                    "status": g_data.get('status'),
                    "error_message": g_data.get('error_message'),
                    "raw": g_data
                }, status=502)

            route0 = g_data['routes'][0]

            # Polyline 디코딩
            def decode_polyline(polyline_str: str):
                points, index, lat, lng = [], 0, 0, 0
                while index < len(polyline_str):
                    result, shift = 0, 0
                    while True:
                        b = ord(polyline_str[index]) - 63
                        index += 1
                        result |= (b & 0x1f) << shift
                        shift += 5
                        if b < 0x20:
                            break
                    dlat = ~(result >> 1) if (result & 1) else (result >> 1)
                    lat += dlat
                    result, shift = 0, 0
                    while True:
                        b = ord(polyline_str[index]) - 63
                        index += 1
                        result |= (b & 0x1f) << shift
                        shift += 5
                        if b < 0x20:
                            break
                    dlng = ~(result >> 1) if (result & 1) else (result >> 1)
                    lng += dlng
                    points.append({'y': lat / 1e5, 'x': lng / 1e5})
                return points

            total_distance, total_duration, sections = 0, 0, []
            for leg in route0.get('legs', []):
                total_distance += leg.get('distance', {}).get('value', 0)
                total_duration += leg.get('duration', {}).get('value', 0)
                for step in leg.get('steps', []):
                    poly = step.get('polyline', {}).get('points')
                    path = decode_polyline(poly) if poly else []
                    sections.append({
                        'name': step.get('html_instructions', ''),
                        'distance': step.get('distance', {}).get('value', 0),
                        'duration': step.get('duration', {}).get('value', 0),
                        'path': path,
                        'transport': '대중교통' if step.get('travel_mode') == 'TRANSIT' else '도보',
                    })

            overview_path = decode_polyline(route0.get('overview_polyline', {}).get('points', '')) \
                if route0.get('overview_polyline') else []

            unified = {
                'provider': 'google_transit',
                'routes': [{
                    'summary': {'distance': total_distance, 'duration': total_duration},
                    'sections': sections,
                    'overview_path': overview_path,
                }]
            }
            return JsonResponse(unified, safe=False)

        # 자동차 모드 (카카오)
        KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
        if not KAKAO_REST_API_KEY:
            return JsonResponse({'error': 'KAKAO_REST_API_KEY 미설정'}, status=500)

        kakao_url = "https://apis-navi.kakaomobility.com/v1/waypoints/directions"
        headers = {
            'Authorization': f'KakaoAK {KAKAO_REST_API_KEY}',
            'Content-Type': 'application/json'
        }
        kakao_body = {
            'origin': {'x': origin_x, 'y': origin_y},
            'destination': {'x': dest_x, 'y': dest_y},
            'priority': priority,
            'car_fuel': 'GASOLINE',
            'car_hipass': False,
            'alternatives': False,
            'road_details': False
        }
        if waypoints:
            kakao_body['waypoints'] = [{'x': float(wp['x']), 'y': float(wp['y'])} for wp in waypoints]

        try:
            response = requests.post(kakao_url, headers=headers, json=kakao_body, timeout=10)
            if response.status_code == 405:  # POST 실패 시 GET 재시도
                params = {
                    'origin': f"{origin_x},{origin_y}",
                    'destination': f"{dest_x},{dest_y}",
                    'priority': priority
                }
                if waypoints:
                    params['waypoints'] = '|'.join([f"{float(wp['x'])},{float(wp['y'])}" for wp in waypoints])
                response = requests.get(kakao_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            result = response.json()
            result['provider'] = 'kakao'
            return JsonResponse(result)

        except requests.exceptions.RequestException as e:
            print(f"카카오 API 요청 오류: {e}")
            return JsonResponse({'error': f'카카오 API 요청 실패: {str(e)}'}, status=500)

    except json.JSONDecodeError as e:
        return JsonResponse({'error': '잘못된 JSON 형식입니다.', 'error_message': str(e)}, status=400)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'error': f'서버 오류: {str(e)}'}, status=500)


# ==================== 다중 삭제 API 엔드포인트 ====================
@csrf_exempt
def bulk_delete_sessions(request):
    """여러 세션을 한 번에 삭제하는 API"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST 요청만 허용됩니다.'}, status=405)
    
    try:
        # 요청 데이터 파싱
        data = json.loads(request.body)
        session_ids = data.get('session_ids', [])
        
        if not session_ids or not isinstance(session_ids, list):
            return JsonResponse({'error': 'session_ids 배열이 필요합니다.'}, status=400)
        
        # 로그인 확인
        if not request.user.is_authenticated:
            return JsonResponse({'error': '로그인이 필요합니다.'}, status=401)
        
        # 삭제할 세션들을 현재 사용자의 세션으로 필터링
        sessions_to_delete = ChatSession.objects.filter(
            id__in=session_ids,
            user=request.user
        )
        
        # 실제 존재하는 세션 ID만 추출
        existing_session_ids = list(sessions_to_delete.values_list('id', flat=True))
        
        if not existing_session_ids:
            return JsonResponse({'error': '삭제할 수 있는 세션이 없습니다.'}, status=404)
        
        # 세션 삭제 (CASCADE로 관련 메시지도 자동 삭제됨)
        deleted_count = sessions_to_delete.delete()[0]
        
        return JsonResponse({
            'success': True,
            'message': f'{deleted_count}개의 세션이 성공적으로 삭제되었습니다.',
            'deleted_count': deleted_count,
            'deleted_session_ids': existing_session_ids
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': '잘못된 JSON 형식입니다.'}, status=400)
    except Exception as e:
        print(f"다중 삭제 오류: {e}")
        return JsonResponse({
            'error': '서버 내부 오류가 발생했습니다.',
            'error_message': str(e)
        }, status=500)


# -------------------- 사용자명 중복 확인 --------------------
def check_username(request):
    username = request.GET.get('username')
    exists = User.objects.filter(username=username).exists()
    return JsonResponse({'exists': exists})


# -------------------- 계정 찾기 --------------------
def find_account_view(request):
    result = None
    if request.method == "POST":
        form = FindAccountForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            phone = form.cleaned_data['phone']
            try:
                profile = UserProfile.objects.get(name=name, phone=phone)
                user = profile.user

                # ✅ 비밀번호를 초기화해서 사용자에게 보여줌
                new_password = str(random.randint(100000, 999999))
                user.set_password(new_password)
                user.save()

                result = {
                    'username': user.username,
                    'new_password': new_password
                }

            except UserProfile.DoesNotExist:
                form.add_error(None, "일치하는 사용자가 없습니다.")
    else:
        form = FindAccountForm()

    return render(request, "pybo/find_account.html", {
        'form': form,
        'result': result
    })

# 추가----
@csrf_exempt
@login_required
def start_new_session(request):
    """새로운 대화 세션을 시작하는 API"""
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'POST 요청만 허용됩니다.'}, status=405)
        
        # 새 채팅 세션 생성
        chat_session = ChatSession.objects.create(
            user=request.user,
            title="새 여행 계획"
        )
        
        # 기존 schedule_json 초기화 (세션 ID별로 저장)
        request.session[f'schedule_json_{chat_session.id}'] = None
        request.session['chat_session_id'] = chat_session.id
        
        console.log(f"새 세션 생성됨: {chat_session.id} (사용자: {request.user.username})")
        
        return JsonResponse({
            'success': True,
            'session_id': str(chat_session.id),
            'message': '새 대화 세션이 시작되었습니다.'
        })
        
    except Exception as e:
        console.log(f"새 세션 생성 오류: {e}")
        return JsonResponse({'error': '새 세션 생성에 실패했습니다.'}, status=500)
#== 추가 끝----
