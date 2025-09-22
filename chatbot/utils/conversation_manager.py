"""
대화 관리 유틸리티

이 모듈은 대화 히스토리 관리와 관련된 공통 함수들을 제공합니다.
"""

import re
from ..models import ChatMessage
from rich.console import Console    
# prompt_templates.py의 detect_travel_destination 함수 사용 (DB+sessionstorage 구조)
from .prompt_templates import detect_travel_destination as detect_destination

console = Console()


def get_conversation_history(session, limit=15):
    """
    세션의 대화 히스토리를 가져오는 함수
    
    Args:
        session: ChatSession 객체
        limit (int): 가져올 메시지 수 제한
        
    Returns:
        list: 대화 히스토리 목록
    """
    conversation_history = []
    
    if not session:
        console.log("❌ 세션이 없습니다.")
        return conversation_history
    
    # 최근 메시지들을 시간순으로 가져오기
    recent_messages = ChatMessage.objects.filter(session=session).order_by('-created_at')[:limit]
    
    console.log(f"🔍 DB에서 가져온 메시지 개수: {len(recent_messages)}")
    
    for msg in reversed(recent_messages):  # 시간순으로 정렬
        conversation_history.append(f"{msg.role}: {msg.content}")
        console.log(f"🔍 메시지 추가: {msg.role}: {msg.content[:50]}...")
    
    console.log(f"🔍 최종 대화 히스토리 개수: {len(conversation_history)}")
    return conversation_history


def get_session_context(session, conversation_history):
    """
    세션 컨텍스트 정보를 생성하는 함수
    
    Args:
        session: ChatSession 객체
        conversation_history (list): 대화 히스토리
        
    Returns:
        str: 세션 컨텍스트 문자열
    """
    context_parts = []
    
    if session and session.title:
        context_parts.append(f"세션 제목: {session.title}")
        context_parts.append(f"대화 시작 시간: {session.created_at.strftime('%Y-%m-%d %H:%M')}")
    
    if conversation_history:
        context_parts.append("대화 히스토리:")
        context_parts.extend(conversation_history)
    else:
        context_parts.append("대화 히스토리가 없습니다.")
    
    return "\n".join(context_parts)


def extract_conversation_context(conversation_history):
    """
    대화 히스토리에서 중요한 컨텍스트 정보를 추출하는 함수
    
    Args:
        conversation_history (list): 대화 히스토리 목록
        
    Returns:
        dict: 추출된 컨텍스트 정보
    """
    context = {
        'mentioned_places': set(),
        'mentioned_dates': set(),
        'user_preferences': set(),
        'previous_questions': [],
        'travel_destination': None,
        'travel_duration': None
    }
    
    conversation_text = " ".join(conversation_history).lower()
    
    # AI 기반 여행 목적지 감지 (완전 하드코딩 제거)
    if conversation_history:
        latest_message = conversation_history[-1].lower()
        console.log(f"🔍 최신 메시지 (원본): '{latest_message}'")
        
        # AI가 자연스럽게 지역을 감지하도록 키워드 기반 감지 제거
        # 이제 AI가 프롬프트에서 직접 지역을 이해하도록 함
        context['travel_destination'] = ""  # AI가 프롬프트에서 감지하도록 함
    
    # AI가 프롬프트에서 직접 지역을 감지하도록 함 (하드코딩 완전 제거)
    
    # 여행 기간 감지
    duration_patterns = [
        r'(\d+)일\s*여행', r'(\d+)박\s*(\d+)일', r'(\d+)일간', r'(\d+)일\s*동안'
    ]
    for pattern in duration_patterns:
        match = re.search(pattern, conversation_text)
        if match:
            context['travel_duration'] = match.group(1) + "일"
            break
    
    # 언급된 장소들 추출
    place_keywords = [
        '궁', '사', '공원', '박물관', '미술관', '해변', '산', '시장', 
        '카페', '맛집', '식당', '호텔', '펜션', '리조트'
    ]
    
    for keyword in place_keywords:
        if keyword in conversation_text:
            # 키워드 주변 텍스트에서 장소명 추출 시도
            pattern = rf'[가-힣\s]*{keyword}[가-힣\s]*'
            matches = re.findall(pattern, conversation_text)
            for match in matches:
                clean_place = match.strip()
                if len(clean_place) > 2:
                    context['mentioned_places'].add(clean_place)
    
    # 사용자 선호도 추출
    preference_keywords = {
        '자연': ['자연', '산', '바다', '공원', '해변'],
        '문화': ['문화', '역사', '전통', '박물관', '미술관'],
        '음식': ['음식', '맛집', '카페', '식당', '먹거리'],
        '쇼핑': ['쇼핑', '시장', '상가', '백화점'],
        '액티비티': ['액티비티', '체험', '놀이', '레저']
    }
    
    for pref_type, keywords in preference_keywords.items():
        if any(keyword in conversation_text for keyword in keywords):
            context['user_preferences'].add(pref_type)
    
    # 이전 질문들 추출
    for msg in conversation_history:
        if msg.startswith('user:'):
            question = msg.replace('user:', '').strip()
            if len(question) > 10:  # 의미있는 질문만
                context['previous_questions'].append(question)
    
    # 일정 관련 정보 추출
    schedule_keywords = ['일정', '여행', '코스', '플랜', '스케줄']
    if any(keyword in conversation_text for keyword in schedule_keywords):
        context['has_schedule_discussion'] = True
    
    # 맛집 관련 정보 추출
    food_keywords = ['맛집', '음식', '식당', '카페', '레스토랑', '먹거리', '커피']
    if any(keyword in conversation_text for keyword in food_keywords):
        context['has_food_discussion'] = True
    
    # 관광지 관련 정보 추출
    tourist_keywords = ['관광지', '명소', '공원', '박물관', '미술관', '궁', '사']
    if any(keyword in conversation_text for keyword in tourist_keywords):
        context['has_tourist_discussion'] = True
    
    # 예산 관련 정보 추출
    budget_keywords = ['예산', '비용', '돈', '가격', '저렴', '비싼']
    if any(keyword in conversation_text for keyword in budget_keywords):
        context['has_budget_discussion'] = True
    
    return context


def detect_travel_destination(conversation_str, session_id=None, existing_schedule_data=None):
    """
    AI 기반 여행 목적지 감지 함수 (DB+sessionstorage 구조 지원)
    
    Args:
        conversation_str (str): 대화 내용
        session_id (str): 세션 ID (DB+sessionstorage 구조용)
        existing_schedule_data (dict): 기존 일정 데이터
        
    Returns:
        str: 감지된 여행 목적지 (세션 기반 또는 AI 감지)
    """

    
    # 세션 기반으로 목적지 감지 (DB 저장/조회 포함)
    travel_destination = detect_destination(conversation_str, session_id)
    
    console.log(f"🔍 세션 기반 지역 감지: {travel_destination} (세션: {session_id})")
    
    return travel_destination
