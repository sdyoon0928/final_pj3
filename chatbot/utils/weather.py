# chatbot/utils/weather.py
import requests
import os

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

def get_weather_info(location: str) -> str:
    """OpenWeather API로 현재 날씨와 기온 가져오기 (최소 버전)"""
    if not OPENWEATHER_API_KEY:
        return "❌ OpenWeather API 키가 설정되지 않았습니다."

    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHER_API_KEY}&lang=kr&units=metric"
        response = requests.get(url)
        data = response.json()

        if data.get("cod") != 200:
            return f"❌ 날씨 정보를 가져올 수 없습니다: {data.get('message', '알 수 없는 오류')}"

        weather_desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]

        return f"{location} 현재 날씨는 '{weather_desc}', 기온은 {temp}°C (체감 {feels_like}°C) 입니다."
    except Exception as e:
        return f"❌ 날씨 정보 호출 오류: {e}"

def get_weather_info_by_coords(lat: float, lng: float) -> str:
    """좌표로 현재 날씨와 기온 가져오기"""
    if not OPENWEATHER_API_KEY:
        return "❌ OpenWeather API 키가 설정되지 않았습니다."

    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&appid={OPENWEATHER_API_KEY}&lang=kr&units=metric"
        response = requests.get(url)
        data = response.json()

        if data.get("cod") != 200:
            return f"❌ 날씨 정보를 가져올 수 없습니다: {data.get('message', '알 수 없는 오류')}"

        weather_desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        city_name = data.get("name", "해당 지역")

        return f"{city_name} 현재 날씨는 '{weather_desc}', 기온은 {temp}°C (체감 {feels_like}°C) 입니다."
    except Exception as e:
        return f"❌ 날씨 정보 호출 오류: {e}"