from django.db import models
from django.contrib.auth.models import User


# 💬 대화 세션 모델
class ChatSession(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sessions",
        null=True,   # ⚠️ 지금은 null 허용 상태 유지 (문제 해결 후 null=False 가능)
        blank=True
    )
    title = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or f"Session {self.id} ({self.created_at:%Y-%m-%d %H:%M})"


# 📝 대화 메시지 모델
class ChatMessage(models.Model):
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages"
    )
    role = models.CharField(max_length=20)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:30]}"


# 📍 장소 모델
class Place(models.Model):
    name = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return self.name


# 📅 일정 모델 (새로 추가)
class Schedule(models.Model):
    # 로그인한 사용자와 반드시 연결
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="schedules"
    )
    title = models.CharField(max_length=200, blank=True)
    data = models.JSONField()  # ✅ 일정 JSON 데이터 저장
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or f"Schedule {self.id} ({self.created_at:%Y-%m-%d})"
