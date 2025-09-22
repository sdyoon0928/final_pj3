"""
세션 관련 유틸리티 함수들

이 모듈은 채팅 세션 관리와 관련된 유틸리티 함수들을 포함합니다.
"""

# 로컬 모듈
from ..models import ChatSession


def get_or_create_session(request, session_id=None):
    """
    세션을 가져오거나 새로 생성하는 함수
    
    Args:
        request (HttpRequest): Django 요청 객체
        session_id (str, optional): 특정 세션 ID
        
    Returns:
        ChatSession: 현재 또는 새로 생성된 채팅 세션
    """
    session = None
    
    if session_id and request.user.is_authenticated:
        # URL에 session_id가 있고, 사용자가 로그인한 경우
        # 해당 사용자의 세션이 DB에 존재하는지 확인
        session = ChatSession.objects.filter(id=session_id, user=request.user).first()
        if session:
            # 세션이 존재하면, Django 세션 저장소에도 현재 session_id를 기록
            request.session["chat_session_id"] = session.id
    elif "chat_session_id" in request.session and request.user.is_authenticated:
        # URL 파라미터에 없고, Django 세션 저장소에는 값이 있는 경우
        # (즉, 사용자가 이미 대화를 시작한 적이 있는 경우)
        session = ChatSession.objects.filter(
            id=request.session["chat_session_id"], user=request.user
        ).first()

    if not session and request.user.is_authenticated:
        # 세션이 전혀 없는 경우 (처음 접속)
        # 새 ChatSession을 DB에 생성하고 Django 세션 저장소에도 기록
        session = ChatSession.objects.create(user=request.user)
        request.session["chat_session_id"] = session.id
    
    return session
