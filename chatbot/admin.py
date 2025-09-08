from django.contrib import admin
from .models import ChatMessage, Place

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "role", "content", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("content",)

@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'latitude', 'longitude')
