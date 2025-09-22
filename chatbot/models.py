from django.db import models
from django.contrib.auth.models import User


# 💬 대화 세션 모델
class ChatSession(models.Model):
    # 해당 세션을 생성한 사용자 (회원)
    # - ForeignKey: User 모델과 1:N 관계 (한 사용자가 여러 세션 가질 수 있음)
    # - on_delete=models.CASCADE: 사용자가 삭제되면 연결된 세션도 자동 삭제됨
    # - related_name="sessions": User 객체에서 user.sessions 로 접근 가능
    # - null=True, blank=True: 현재는 로그인 없이도 세션 허용 (추후 문제 해결 후 null=False로 변경 권장)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sessions",
        null=True,   # ⚠️ 임시로 null 허용
        blank=True
    )
    # 세션 제목 (예: "제주 여행 일정") → 비워둘 수 있음
    title = models.CharField(max_length=200, blank=True, null=True)
    # 세션 생성 시각 (자동 기록)
    created_at = models.DateTimeField(auto_now_add=True)
    # 새로 추가
    last_detected_destination = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        # 객체를 문자열로 표현할 때 보여줄 내용
        # → 제목이 있으면 제목 출력, 없으면 "Session {id} (날짜)" 형태로 출력
        return self.title or f"Session {self.id} ({self.created_at:%Y-%m-%d %H:%M})"


# 📝 대화 메시지 모델
class ChatMessage(models.Model):
    # 어떤 세션에 속한 메시지인지 연결
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,   # 세션이 삭제되면 메시지도 함께 삭제됨
        related_name="messages"     # session.messages 로 메시지 목록 접근 가능
    )
    # 메시지 역할 (user / assistant / system 등)
    role = models.CharField(max_length=20)
    # 메시지 본문 (길이 제한 없음)
    content = models.TextField()
    # 메시지 생성 시각 (자동 기록)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # 메시지를 생성된 순서대로 정렬
        ordering = ["created_at"]

    def __str__(self):
        # 문자열 출력 시 "역할: 내용 앞 30자" 표시
        return f"{self.role}: {self.content[:30]}"


# 📍 장소 모델
class Place(models.Model):
    # 장소 이름 (예: "한라산", "광안리 해수욕장")
    name = models.CharField(max_length=100)
    # 위도
    latitude = models.FloatField()
    # 경도
    longitude = models.FloatField()

    def __str__(self):
        # 문자열로 표현할 때는 장소 이름 출력
        return self.name


# 📅 일정 모델
class Schedule(models.Model):
    # 일정은 반드시 로그인된 사용자와 연결됨 (한 사용자가 여러 일정 가질 수 있음)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,   # 사용자가 삭제되면 일정도 함께 삭제됨
        related_name="schedules"    # user.schedules 로 접근 가능
    )
    # 일정 제목 (예: "부산 2박 3일 여행") → 비워둘 수도 있음
    title = models.CharField(max_length=200, blank=True)
    # 일정 데이터를 JSON 형식으로 저장 (Day1, Day2, 시간대별 장소 정보 등)
    data = models.JSONField()  # ✅ Python dict/list → DB에 JSON으로 저장
    # 일정 생성 시각 (자동 기록)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # 제목이 있으면 제목 출력, 없으면 "Schedule {id} (날짜)" 형태로 출력
        return self.title or f"Schedule {self.id} ({self.created_at:%Y-%m-%d})"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)

    def __str__(self):
        return self.user.username