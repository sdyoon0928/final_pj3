"""
좌표 추출 유틸리티

이 모듈은 일정 데이터에서 좌표 정보를 추출하는 공통 함수들을 제공합니다.
"""

from ..utils.coordinates import extract_places_from_response, search_place_coordinates
from rich.console import Console

console = Console()


def extract_coordinates_from_schedule_data(schedule_data):
    """
    일정 데이터에서 좌표 정보를 추출하는 함수
    
    Args:
        schedule_data (dict): 일정 데이터
        
    Returns:
        list: 좌표 정보가 포함된 장소 목록
    """
    places_with_coords = []
    
    if not schedule_data or 'schedule' not in schedule_data:
        return places_with_coords
    
    # JSON 데이터에서 직접 좌표 정보 추출 (우선순위)
    for day_key, day_data in schedule_data['schedule'].items():
        if isinstance(day_data, dict):
            for activity, details in day_data.items():
                if isinstance(details, dict) and '장소' in details and '좌표' in details:
                    place_name = details['장소']
                    coords = details['좌표']
                    if isinstance(coords, dict) and 'lat' in coords and 'lng' in coords:
                        places_with_coords.append({
                            "name": place_name,
                            "lat": coords['lat'],
                            "lng": coords['lng'],
                            "address": details.get('주소', ''),
                            "activity": activity
                        })
                        console.log(f"JSON에서 좌표 추출: {place_name} ({coords['lat']}, {coords['lng']})")
    
    return places_with_coords


def extract_coordinates_from_response(response_text, existing_places=None):
    """
    AI 응답에서 장소명을 추출하여 좌표를 검색하는 함수
    
    Args:
        response_text (str): AI 응답 텍스트
        existing_places (list): 기존에 추출된 장소 목록
        
    Returns:
        list: 좌표 정보가 포함된 장소 목록
    """
    places_with_coords = existing_places or []
    
    # JSON에 좌표가 없으면 AI 응답에서 장소명들을 추출하여 좌표 검색
    if not places_with_coords:
        places = extract_places_from_response(response_text)
        console.log(f"추출된 장소명들: {places}")
        
        for place_name in places:
            coords = search_place_coordinates(place_name)
            if coords:
                places_with_coords.append({
                    "name": coords.get("place_name", place_name),
                    "lat": coords["lat"],
                    "lng": coords["lng"],
                    "address": coords.get("address", "")
                })
    
    return places_with_coords


def format_places_info(places_with_coords):
    """
    장소 정보를 포맷팅하는 함수
    
    Args:
        places_with_coords (list): 좌표 정보가 포함된 장소 목록
        
    Returns:
        str: 포맷팅된 장소 정보 텍스트
    """
    if not places_with_coords:
        return ""
    
    result = "\n\n📍 **추천 장소 위치 정보:**\n"
    for place in places_with_coords:
        result += f"- {place['name']}: {place['address']}\n"
    
    return result
