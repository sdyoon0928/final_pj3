"""
챗봇 요청 처리 핸들러 함수들

이 모듈은 다양한 유형의 사용자 요청을 처리하는 핸들러 함수들을 포함합니다.
"""

# 표준 라이브러리
import json

# Django 및 외부 모듈
from django.contrib.auth.models import User
from rich.console import Console

# LangChain 관련
from langchain.agents import initialize_agent, Tool
from langchain_openai import ChatOpenAI

# 로컬 모듈
from ..models import ChatMessage, Schedule
from ..utils.youtube import yt_search, _render_yt_cards
from ..utils.maps import google_place_details, kakao_geocode
from ..utils.knowledge import search_external_knowledge
from ..utils.coordinates import extract_places_from_response, search_place_coordinates
from ..utils.coordinate_extractor import extract_coordinates_from_schedule_data, extract_coordinates_from_response, format_places_info
from ..utils.prompt_templates import get_schedule_prompt, get_general_prompt
from ..utils.conversation_manager import get_conversation_history, extract_conversation_context

import re
from django.http import HttpRequest

console = Console()

# LLM 초기화
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)


def generate_complete_summary(schedule_data):
    """
    일정 데이터에서 완전한 요약 코스를 생성하는 함수
    
    Args:
        schedule_data (dict): 일정 데이터의 schedule 부분
        
    Returns:
        str: 완전한 요약 코스 문자열
    """
    summary_parts = []
    
    for day_key, day_activities in schedule_data.items():
        day_places = []
        
        # 각 활동의 장소를 순서대로 수집
        activity_order = ['오전활동', '점심', '오후활동', '저녁']
        
        for activity in activity_order:
            if activity in day_activities:
                place = day_activities[activity].get('장소', f'{activity}장소')
                day_places.append(place)
        
        # Day별 요약 생성
        if day_places:
            day_summary = f"{day_key}: " + " → ".join(day_places)
            summary_parts.append(day_summary)
    
    return ", ".join(summary_parts)


def handle_schedule_request(user_input, session, request, is_schedule_modification=False):
    """
    일정 관련 요청을 처리하는 함수 (개선된 버전)
    
    Args:
        user_input (str): 사용자 입력 메시지
        session (ChatSession): 현재 채팅 세션
        request (HttpRequest): Django 요청 객체
        is_schedule_modification (bool): 일정 변경 요청 여부
        
    Returns:
        tuple: (결과 텍스트, 일정 데이터 딕셔너리 또는 None)
    """
    # 대화 히스토리 가져오기
    conversation_history = get_conversation_history(session, limit=15)
    conversation_str = "\n".join(conversation_history) if conversation_history else "대화 히스토리가 없습니다."
    
    # 세션 ID 가져오기 (세션 기반 목적지 감지를 위해)
    session_id = str(session.id) if session else None
    
    # 대화 컨텍스트 추출
    context_info = extract_conversation_context(conversation_history)
    
    # 기존 일정 데이터 가져오기 (일정 변경 요청인 경우)
    existing_schedule_data = None
    existing_data_str = ""
    if is_schedule_modification:
        # 세션에서 기존 일정 JSON 데이터 가져오기
        existing_schedule_data = request.session.get('schedule_json')
        if not existing_schedule_data:
            # DB에서 최근 일정 데이터 가져오기
            recent_schedule = Schedule.objects.filter(session=session).order_by('-created_at').first()
            if recent_schedule:
                try:
                    existing_schedule_data = json.loads(recent_schedule.schedule_data)
                except:
                    pass
        
        if existing_schedule_data:
            existing_data_str = json.dumps(existing_schedule_data, ensure_ascii=False, indent=2)
    
    # 프롬프트 생성 (세션 기반 목적지 감지)
    system_prompt = get_schedule_prompt(
        conversation_str=conversation_str,
        user_input=user_input,
        session_id=session_id,  # 세션 ID 전달
        is_modification=is_schedule_modification,
        existing_data_str=existing_data_str,
        context_info=context_info
    )
    
    result = llm.invoke(f"{system_prompt}\n사용자 질문: {user_input}")
    # LangChain 결과에서 실제 텍스트 추출
    if hasattr(result, 'content'):
        result = result.content
    
    # JSON 응답을 파싱하여 구조화된 데이터로 변환
    try:
        # JSON 부분만 추출 (```json ... ``` 형태일 수 있음)
        json_text = result
        if '```json' in result:
            json_text = result.split('```json')[1].split('```')[0].strip()
        elif '```' in result:
            json_text = result.split('```')[1].split('```')[0].strip()
        
        schedule_data = json.loads(json_text)
        
        # ✅ Summary 후처리: 불완전한 요약 코스 자동 보완
        if 'schedule' in schedule_data and 'summary' in schedule_data:
            original_summary = schedule_data['summary']
            
            # 모든 활동이 포함되었는지 확인하고 필요시 보완
            complete_summary = generate_complete_summary(schedule_data['schedule'])
            
            # 원본 요약이 너무 짧거나 일부 활동만 포함된 경우 보완된 요약 사용
            if (len(original_summary) < 30 or 
                not all(activity in original_summary for activity in ['오전', '점심', '오후', '저녁']) or
                original_summary.count('→') < 3):  # 최소 3개의 화살표가 있어야 함
                console.log(f"🔄 불완전한 요약 감지, 자동 보완: '{original_summary}' → '{complete_summary}'")
                schedule_data['summary'] = complete_summary
        
        # JSON을 Markdown으로 변환하여 사용자에게 표시
        markdown_result = ""
        if 'schedule' in schedule_data:
            for day, activities in schedule_data['schedule'].items():
                markdown_result += f"## {day}\n\n"
                for activity, details in activities.items():
                    markdown_result += f"### {activity}\n"
                    markdown_result += f"- 장소: {details.get('장소', 'N/A')}\n"
                    markdown_result += f"- 시간: {details.get('시간', 'N/A')}\n"
                    markdown_result += f"- 비용: {details.get('비용', 'N/A')}\n"
                    markdown_result += f"- 주의사항: {details.get('주의사항', 'N/A')}\n"
                    markdown_result += "\n"
        
        if 'summary' in schedule_data:
            markdown_result += f"## 요약 코스\n{schedule_data['summary']}\n"
        
        result = markdown_result
        
        # JSON 데이터를 세션에 저장 (지도에서 사용)
        request.session['schedule_json'] = schedule_data
        
        return result, schedule_data
        
    except (ValueError, KeyError) as e:
        # JSON 파싱 실패 시 원본 텍스트 사용
        console.log(f"JSON 파싱 실패: {e}")
        return result, None

# 추가----
def extract_location(user_input, session=None, request=None):
    """
    사용자 입력, 세션, 또는 schedule_json에서 위치를 추출하는 함수
    """
    # 위치 패턴: 한국 지명 (한글 2~4자 + 옵션 "도/시/군/구")
    location_pattern = r'([가-힣]{2,4}(?:도|시|군|구)?)'

    # 1. schedule_json에서 추출 (최우선)
    if request and session and f'schedule_json_{session.id}' in request.session:
        schedule_data = request.session.get(f'schedule_json_{session.id}')
        if schedule_data:
            for day in schedule_data.get('schedule', {}):
                for activity in schedule_data['schedule'][day]:
                    place = schedule_data['schedule'][day][activity].get('장소', '')
                    place_matches = re.findall(location_pattern, place)
                    if place_matches:
                        return place_matches[0]  # 첫 번째 장소 반환 (예: "영월")

    # 2. user_input에서 직접 추출
    matches = re.findall(location_pattern, user_input)
    if matches:
        filtered = [m for m in matches if m not in ["박", "일", "일정", "관련", "위", "보여줘"]]
        if filtered:
            return filtered[0]

    # 3. "위 일정" 같은 참조 표현이 있으면 세션 맥락에서 추출
    if any(keyword in user_input for keyword in ["위 일정", "이 일정", "관련 브이로그"]):
        if session:
            # 세션 제목에서 추출
            if session.title:
                title_matches = re.findall(location_pattern, session.title)
                if title_matches:
                    return title_matches[0]
            # 최근 메시지에서 추출
            recent_messages = ChatMessage.objects.filter(session=session).order_by('-created_at')[:5]
            for msg in recent_messages:
                msg_matches = re.findall(location_pattern, msg.content)
                filtered = [m for m in msg_matches if m not in ["박", "일", "일정", "관련", "위", "보여줘"]]
                if filtered:
                    return filtered[0]

    return None

def handle_vlog_request(user_input, session, request=None):
    """
    브이로그 관련 요청을 처리하는 함수 (세션 ID별 schedule_json 활용 + 직전 맥락 반영)
    """
    # 최근 대화 히스토리 가져오기
    conversation_history = get_conversation_history(session, limit=15)
    conversation_str = "\n".join(conversation_history) if conversation_history else ""

    # 핵심 검색어 추출 (현재 입력에서 먼저 시도)
    search_term = extract_location(user_input, session, request)

    # 만약 검색어가 없거나 "위와 관련된" 같은 모호한 경우 → 직전 대화에서 보정
    if not search_term or "관련" in user_input or "보여줘" in user_input:
        if conversation_history:
            last_message = conversation_history[-1]  # 직전 메시지
            search_term = extract_location(last_message, session, request)
        if not search_term and session.title:
            search_term = extract_location(session.title, session, request)

    if not search_term:
        search_term = "여행 브이로그"  # 최종 fallback

    console.log(f"브이로그 검색어: {search_term} (세션 ID: {session.id})")

    # 유튜브 브이로그 검색
    youtube_results = yt_search(search_term)
    yt_html = _render_yt_cards(youtube_results)

    reply_html = f"""
    <div style="margin-bottom:8px;">
        {search_term} 관련 브이로그를 추천해드릴게요! ✨
    </div>
    {yt_html}
    """

    if session.title:
        ChatMessage.objects.create(session=session, role="assistant", content=reply_html)

    return {
        "reply": "",
        "yt_html": reply_html,
        "youtube": youtube_results,
        "map": [],
        "save_button_enabled": False,
        "search_term": search_term
    }

# 끝----


def handle_simple_qna(user_input):
    """
    간단한 질문 답변을 처리하는 함수
    
    Args:
        user_input (str): 사용자 입력 메시지
        
    Returns:
        str: AI 응답 텍스트
    """
    from openai import OpenAI
    
    # OpenAI SDK 초기화
    client = OpenAI()
    
    # 간단 질문 → OpenAI SDK 사용
    # OpenAI SDK는 LangChain보다 응답 속도가 빠르고 단순한 작업에 적합
    completion = client.chat.completions.create(
        model="gpt-4o-mini",   # 모델 지정
        messages=[
            {"role": "system", "content": """# 🎯 여행 질문 답변 전문가

**역할**: 국내 여행 전문가
**목표**: 명확하고 실용적인 답변 제공
- 사용자가 원하는 여행 기간(N박 M일)은 절대로 변경하지 않습니다.  
- 추가 조건(특정 관광지, 혼자 여행, 아이 동반 등)이 들어와도 반드시 N박 M일 형식으로 일정을 구성합니다.  
- 출력은 항상 Day1, Day2, … 형식으로 나누어 작성합니다.  
- 각 일정에는 장소, 시간, 비용, 주의사항을 반드시 포함합니다.  
- 사용자의 요청이 모호하거나 불완전해도 절대로 당일치기로 축소하지 않습니다.  
- 브이로그, 유튜브 관련에 대해 물어보면 해당 지역과 관련된 유튜브 여행 브이로그 영상도 추천할 수 있습니다.  
- 영어로 절대 답하지 마세요.
- 사용자가 필요한 여행지와 여행일정을 추천하세요.

## 🎯 답변 원칙
1. **핵심 먼저**: 질문에 대한 직접적 답변
2. **간결함**: 불필요한 정보 제거
3. **실용성**: 실제 여행에 도움이 되는 정보
4. **친근함**: 도움이 되는 톤 유지

**형식**: 핵심 답변 → 부가 정보 → 실용적 팁"""},
            {"role": "user", "content": user_input}
        ]
    )
    return completion.choices[0].message.content   # 첫 번째 응답만 사용


def handle_general_request(user_input, conversation_history, session=None):
    """
    일반적인 여행 관련 질문을 처리하는 함수 (개선된 버전)
    
    Args:
        user_input (str): 사용자 입력 메시지
        conversation_history (list): 대화 히스토리
        session (ChatSession): 현재 채팅 세션 (세션 기반 목적지 감지를 위해)
        
    Returns:
        str: AI 응답 텍스트
    """
    # 일반 질문 → LangChain Agent 실행
    tools = [
        Tool(name="유튜브검색", func=yt_search, description="지역명/장소명으로 여행 브이로그, 맛집 리뷰, 관광지 영상을 찾아줍니다. 맛집 추천 시에는 맛집 리뷰 영상도 함께 검색합니다. 예: '서울 여행 브이로그', '강릉 맛집', '제주도 vlog', '경복궁 브이로그', '이태원 맛집'"),
        Tool(name="카카오지도검색", func=kakao_geocode, description="장소명으로 검색하여 정확한 위도, 경도 좌표와 주소를 찾아줍니다. 모든 장소의 정확한 위치 정보가 필요할 때 사용합니다. 예: '경복궁', '제주도 한라산', '부산 해운대', '이태원 맛집'"),
        Tool(name="구글플레이스상세", func=google_place_details, description="장소명으로 검색하여 운영시간, 전화번호, 정확한 주소, 평점 등 상세 정보를 찾아줍니다. 맛집이나 관광지의 실용적인 정보가 필요할 때 사용합니다. 예: '경복궁', '제주도 카페', '부산 맛집', '이태원 식당'"),
        Tool(name="외부지식검색", func=search_external_knowledge, description="지역명이나 관광지명으로 검색하여 역사, 문화, 특징 등 배경 정보를 찾아줍니다. 관광지의 의미나 역사적 배경이 필요할 때 사용합니다. 예: '제주도', '경복궁', '부산 감천문화마을', '이태원'"),
    ]

    # Agent 초기화: ChatGPT 수준의 빠른 응답을 위한 최적화
    agent = initialize_agent(
        tools,
        llm,
        agent="zero-shot-react-description",  # Zero-shot 방식
        verbose=False,                       # 로그 출력 비활성화 (성능 향상)
        handle_parsing_errors="Check your output and make sure it conforms!",  # 파싱 에러 시 재시도
        max_iterations=3,                    # 최대 3번 도구 호출 (파싱 에러 대응)
        early_stopping_method="generate",    # 조기 종료 방법
        return_intermediate_steps=True,      # 중간 단계 반환 활성화 (에러 디버깅용)
        max_execution_time=20                # 최대 실행 시간 20초 (여유있게)
    )

    # 입력 프롬프트 생성
    conversation_str = "\n".join(conversation_history) if conversation_history else "대화 히스토리가 없습니다."
    
    # 사용자 요청 유형에 따른 맞춤형 prompt 생성 (더 정확한 판단)
    request_type = ""
    
    # 입력 텍스트 정리 (불필요한 접속사, 조사 제거)
    clean_input = user_input.lower().strip()
    
    # 맛집 관련 키워드 검사
    if any(keyword in clean_input for keyword in ["맛집", "음식", "식당", "레스토랑", "카페"]):
        request_type = "맛집 추천"

    # 브이로그/영상 관련 키워드 검사 (더 포괄적으로)
    elif any(keyword in clean_input for keyword in ["브이로그", "vlog", "유튜브", "영상", "동영상", "비디오", "보여줘", "여행브이로그"]):
        request_type = "브이로그 추천"

    # 일정/여행 관련 키워드 검사 (추천/생성 요청일 때만 '여행 일정'으로 분류)
    elif any(keyword in clean_input for keyword in ["일정", "여행", "코스", "플랜"]):
        if any(intent in clean_input for intent in ["추천", "짜줘", "만들어", "생성", "계획해줘"]):
            request_type = "여행 일정"
        else:
            request_type = "일반 여행 정보"

    else:
        request_type = "일반 여행 정보"

    
    # 디버깅을 위한 로그 출력
    console.log(f"원본 입력: '{user_input}'")
    console.log(f"정리된 입력: '{clean_input}'")
    console.log(f"판단된 요청 유형: '{request_type}'")
    
    # 세션 ID 가져오기 (세션 기반 목적지 감지를 위해)
    session_id = str(session.id) if session else None
    
    # 요청 유형에 따른 최적화된 prompt 생성
    if request_type == "맛집 추천":
        # 브이로그 요청에서 지역명 추출
        search_query = user_input.replace("맛집", "").replace("음식", "").replace("식당", "").replace("레스토랑", "").replace("카페", "").strip()
        prompt = get_general_prompt(request_type, user_input, session_id=session_id, search_query=search_query)  # 세션 ID 전달
    
    elif request_type == "브이로그 추천":
        # 브이로그 요청에서 지역명 추출 (더 정확하게)
        location_keywords = []
        
        # 특정 지역명 매핑
        location_mappings = {
            "청계천": ["청계천", "청계천 플라자", "청계천광장"],
            "창덕궁": ["창덕궁", "창덕궁과원", "비원"],
            "경복궁": ["경복궁", "경복궁역"],
            "창경궁": ["창경궁", "창경궁역"],
            "이태원": ["이태원", "이태원역"],
            "강남": ["강남", "강남역", "강남구"],
            "홍대": ["홍대", "홍익대", "홍대입구"],
            "부산": ["부산", "부산여행"],
            "경주": ["경주", "경주여행"],
            "제주": ["제주도", "제주", "제주여행"]
        }
        
        # 입력에서 지역명 찾기
        found_location = None
        for location, keywords in location_mappings.items():
            if location in user_input:
                found_location = location
                location_keywords = keywords
                break
        
        if not found_location:
            # 일반적인 지역명 추출 (더 정확하게)
            clean_location = user_input.replace("브이로그", "").replace("vlog", "").replace("추천", "").replace("보여줘", "").replace("그럼", "").replace("그러면", "").replace("관련된", "").strip()
            location_keywords = [clean_location]
        
        search_query = " ".join(location_keywords[:2])  # 최대 2개 키워드만 사용
        prompt = get_general_prompt(request_type, user_input, session_id=session_id, search_query=search_query, conversation_str=conversation_str)  # 세션 ID 전달
    
    else:
        prompt = get_general_prompt(request_type, user_input, session_id=session_id, conversation_str=conversation_str)  # 세션 ID 전달
    
    # 랭체인 에이전트 실행
    try:
        console.log(f"🤖 AI 에이전트 실행 시작: {user_input}")
        console.log(f"📝 프롬프트: {prompt[:200]}...")
        
        result = agent.invoke({ 'input': prompt })
        console.log("🤖 AI 에이전트 원본 결과:", result)
        
        # LangChain Agent 결과에서 실제 텍스트 추출 (개선된 버전)
        if isinstance(result, dict):
            if 'output' in result:
                result = result['output']
                console.log("✅ output에서 결과 추출 성공")
            elif 'intermediate_steps' in result:
                # 중간 단계가 있는 경우 마지막 응답 추출
                console.log("🔄 중간 단계 결과:", result.get('intermediate_steps', []))
                if 'output' in result:
                    result = result['output']
                else:
                    # 중간 단계에서 최종 응답 생성
                    steps = result.get('intermediate_steps', [])
                    if steps:
                        # 마지막 도구 실행 결과를 기반으로 응답 생성
                        last_step = steps[-1]
                        if isinstance(last_step, tuple) and len(last_step) >= 2:
                            tool_result = last_step[1]
                            console.log("🔧 마지막 도구 결과:", tool_result)
                            result = f"검색 결과를 바탕으로 {user_input}에 대한 정보를 제공해드립니다.\n\n{tool_result}"
                        else:
                            result = f"안녕하세요! {user_input}에 대한 정보를 찾아보겠습니다."
                    else:
                        result = "죄송합니다. 응답을 생성하는 중에 문제가 발생했습니다."
            else:
                console.log("❌ 예상치 못한 결과 구조:", result)
                result = str(result)
        elif hasattr(result, 'content'):
            result = result.content
            console.log("✅ content에서 결과 추출 성공")
        elif isinstance(result, str):
            result = result
            console.log("✅ 문자열 결과 사용")
        else:
            console.log("❌ 알 수 없는 결과 타입:", type(result), result)
            result = str(result)
        
        # 결과가 비어있거나 너무 짧은 경우 처리
        if not result or len(result.strip()) < 10:
            console.log("⚠️ 결과가 너무 짧거나 비어있음, 대체 응답 생성")
            result = f"안녕하세요! {user_input}에 대한 정보를 찾아보겠습니다. 잠시만 기다려주세요."
        
        # ✅ 좌표 정보 추출 및 포맷팅 (자연스러운 답변에서도 추출)
        try:
            # AI 응답에서 장소명들을 추출하여 좌표 검색
            places_with_coords = extract_coordinates_from_response(result)
            if places_with_coords:
                console.log(f"📍 좌표 정보 추출 성공: {len(places_with_coords)}개 장소")
                # 좌표 정보를 자연스럽게 응답에 통합
                for place_info in places_with_coords:
                    place_name = place_info.get('name', '')
                    coords = place_info.get('coordinates', {})
                    if coords and 'lat' in coords and 'lng' in coords:
                        # 자연스럽게 좌표 정보 추가
                        result = result.replace(
                            place_name, 
                            f"{place_name} (좌표: {coords['lat']}, {coords['lng']})"
                        )
            else:
                console.log("📍 좌표 정보 없음")
        except Exception as coord_error:
            console.log(f"⚠️ 좌표 추출 중 오류: {coord_error}")
            # 좌표 추출 실패해도 메인 응답은 유지
            
    except Exception as agent_error:
        console.log(f"❌ Agent 실행 오류: {agent_error}")
        import traceback
        console.log(f"상세 오류: {traceback.format_exc()}")
        
        # Agent 오류 시 간단한 응답 생성
        if "맛집" in user_input or "음식" in user_input:
            result = f"죄송합니다. 현재 {user_input}에 대한 정보를 가져오는 중에 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        elif "브이로그" in user_input or "유튜브" in user_input:
            result = f"죄송합니다. 현재 {user_input}에 대한 영상을 찾는 중에 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        else:
            result = f"죄송합니다. 현재 {user_input}에 대한 정보를 처리하는 중에 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
    
    console.log(f"✅ 최종 응답: {result[:100]}...")
    return result
