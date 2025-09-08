# -------------------- 일정 저장/조회 --------------------
@csrf_exempt
@login_required
def save_schedule(request):
    """일정을 저장하고 채팅 메시지로도 기록"""
    print("[일정 저장] 요청 시작")  # 디버깅용 로그
    
    if request.method != "POST":
        return JsonResponse({"error": "POST 요청만 허용됩니다."}, status=400)
    
    if not request.user.is_authenticated:
        return JsonResponse({"error": "로그인이 필요합니다."}, status=401)
    
    try:
        # 1. 요청 데이터 파싱
        try:
            raw_body = request.body.decode('utf-8')
            print("[일정 저장] 요청 본문:", raw_body)  # 디버깅용 로그
            body = json.loads(raw_body)
        except json.JSONDecodeError as e:
            print("[일정 저장] JSON 파싱 오류:", str(e))
            return JsonResponse({"error": "잘못된 JSON 형식입니다."}, status=400)

        # 2. 데이터 검증
        if not isinstance(body, dict):
            return JsonResponse({"error": "잘못된 데이터 형식입니다."}, status=400)
            
        if not body.get("title"):
            return JsonResponse({"error": "일정 제목이 필요합니다."}, status=400)
        if not body.get("data"):
            return JsonResponse({"error": "일정 데이터가 필요합니다."}, status=400)

        # 3. 일정 저장
        try:
            schedule = Schedule.objects.create(
                user=request.user,
                title=body["title"],
                data=body["data"]
            )
            print(f"[일정 저장] 일정 생성됨 (ID: {schedule.id})")
        except Exception as e:
            print("[일정 저장] 일정 저장 실패:", str(e))
            return JsonResponse({"error": "일정 저장에 실패했습니다."}, status=500)

        # 4. 채팅 세션 처리
        current_session_id = request.session.get("chat_session_id")
        chat_session = None

        if current_session_id:
            try:
                chat_session = ChatSession.objects.get(
                    id=current_session_id,
                    user=request.user
                )
                print(f"[일정 저장] 기존 세션 사용 (ID: {chat_session.id})")
            except ChatSession.DoesNotExist:
                print("[일정 저장] 기존 세션 없음")
                pass

        if not chat_session:
            chat_session = ChatSession.objects.create(
                user=request.user,
                title=f"{body['title']}"
            )
            request.session["chat_session_id"] = chat_session.id
            print(f"[일정 저장] 새 세션 생성됨 (ID: {chat_session.id})")

        # 5. 일정을 채팅 메시지로 저장
        schedule_content = f"""
        📅 새로운 일정이 저장되었습니다!
        제목: {body['title']}
        ──────────────
        {body['data'].get('schedule', '일정 내용 없음')}
        ──────────────
        """
        
        try:
            ChatMessage.objects.create(
                session=chat_session,
                role="assistant",
                content=schedule_content
            )
            print("[일정 저장] 채팅 메시지 저장됨")
        except Exception as e:
            print("[일정 저장] 채팅 메시지 저장 실패:", str(e))
            # 채팅 메시지 저장 실패는 전체 프로세스를 실패로 처리하지 않음

        # 6. 성공 응답
        return JsonResponse({
            "success": True,
            "id": schedule.id,
            "session_id": chat_session.id,
            "message": "일정이 성공적으로 저장되었습니다."
        })
        
    except Exception as e:
        print("[일정 저장] 예상치 못한 오류:", str(e))
        return JsonResponse({
            "error": "일정을 저장하는 중에 오류가 발생했습니다.",
            "detail": str(e)
        }, status=500)

@login_required
def get_schedule(request, sid):
    """저장된 일정 조회"""
    try:
        schedule = Schedule.objects.get(id=sid, user=request.user)
        return JsonResponse(schedule.data, safe=False)
    except Schedule.DoesNotExist:
        return JsonResponse({"error": "일정을 찾을 수 없습니다."}, status=404)
