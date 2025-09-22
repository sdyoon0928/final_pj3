"""
지도 관련 유틸리티 함수들

이 모듈은 카카오 지도 API와 구글 플레이스 API를 사용한 지도 관련 함수들을 포함합니다.
"""

# 표준 라이브러리
import os
import re
import json
import requests
import difflib

# 외부 모듈
from rich.console import Console
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

console = Console()

# API 키
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# 로컬 모듈 import (순환 import 방지를 위해 함수 내부에서 import)

# 불용어 목록
STOPWORDS = ["추천","일정","시간","도착","출발","점심","저녁","식사","활동","옵션","여행","코스","계획", "그럼"]


def clean_query(text: str):
    """질문에서 불필요한 단어 제거 (카카오 API 검색 정확도 향상)"""
    text = re.sub(r"[^가-힣A-Za-z0-9 ]", " ", text)
    tokens = [t for t in text.split() if t not in STOPWORDS and len(t) > 1]
    return " ".join(tokens)


def validate_korean_coordinates(lat: float, lng: float, place_name: str = "") -> bool:
    """한국 내 좌표인지 검증"""
    # 한국 좌표 범위: 위도 33-39, 경도 124-132
    if not (33 <= lat <= 39 and 124 <= lng <= 132):
        console.log(f"좌표가 한국 범위를 벗어남: {place_name} ({lat}, {lng})")
        return False
    
    # 특정 지역별 세부 검증
    if "목포" in place_name or "전라남도" in place_name:
        # 목포 지역 좌표 범위
        if not (34.5 <= lat <= 35.0 and 126.0 <= lng <= 126.5):
            console.log(f"목포 지역 좌표가 범위를 벗어남: {place_name} ({lat}, {lng})")
            return False
    
    if "경주" in place_name or "경상북도" in place_name:
        # 경주 지역 좌표 범위
        if not (35.7 <= lat <= 36.0 and 129.0 <= lng <= 129.5):
            console.log(f"경주 지역 좌표가 범위를 벗어남: {place_name} ({lat}, {lng})")
            return False
    
    if "서울" in place_name:
        # 서울 지역 좌표 범위
        if not (37.4 <= lat <= 37.7 and 126.8 <= lng <= 127.2):
            console.log(f"서울 지역 좌표가 범위를 벗어남: {place_name} ({lat}, {lng})")
            return False
    
    return True


def adjust_coordinates_to_road(x: float, y: float) -> tuple:
    """
    좌표를 도로 근처로 조정하는 함수
    산이나 바다 등 도로가 없는 곳의 좌표를 가장 가까운 도로로 이동
    """
    # 제주도 주요 도로 근처 좌표들
    jeju_road_coordinates = [
        # 제주시 근처 도로
        (126.5312, 33.4996),  # 제주시 중심
        (126.5200, 33.5100),  # 제주시 북쪽
        (126.5400, 33.4900),  # 제주시 남쪽
        (126.5300, 33.5000),  # 제주시 동쪽
        (126.5100, 33.5000),  # 제주시 서쪽
        
        # 한라산 근처 도로
        (126.5200, 33.4000),  # 한라산 북쪽
        (126.5400, 33.3800),  # 한라산 동쪽
        (126.5000, 33.4200),  # 한라산 서쪽
        
        # 서귀포 근처 도로
        (126.5600, 33.2500),  # 서귀포 중심
        (126.5500, 33.2600),  # 서귀포 북쪽
        (126.5700, 33.2400),  # 서귀포 남쪽
        
        # 중문 근처 도로
        (126.4100, 33.2400),  # 중문
        (126.4200, 33.2500),  # 중문 북쪽
        (126.4000, 33.2300),  # 중문 남쪽
    ]
    
    # 현재 좌표와 가장 가까운 도로 좌표 찾기
    min_distance = float('inf')
    closest_road = (x, y)
    
    for road_x, road_y in jeju_road_coordinates:
        # 유클리드 거리 계산
        distance = ((x - road_x) ** 2 + (y - road_y) ** 2) ** 0.5
        if distance < min_distance:
            min_distance = distance
            closest_road = (road_x, road_y)
    
    # 거리가 너무 멀면 원본 좌표 반환 (0.01도 = 약 1km)
    if min_distance > 0.01:
        return x, y
    
    return closest_road


def kakao_geocode(query: str):
    """카카오 API를 활용한 장소 좌표 검색 (정확한 좌표를 무조건 찾는 시스템)"""
    if not KAKAO_REST_API_KEY:
        return None
        
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    
    # 검색어 정리 (불필요한 단어 제거)
    cleaned_query = clean_query(query)
    
    # ✅ 장소 유형 분석
    cafe_keywords = ['카페', '커피', 'coffee', 'cafe']
    is_cafe_search = any(keyword in query.lower() for keyword in cafe_keywords)
    
    restaurant_keywords = ['식당', '맛집', '레스토랑', '음식점', '국밥', '냉면', '김치찌개']
    is_restaurant_search = any(keyword in query.lower() for keyword in restaurant_keywords)
    
    tourist_keywords = ['관광지', '명소', '공원', '박물관', '미술관', '산', '해변', '바다']
    is_tourist_search = any(keyword in query.lower() for keyword in tourist_keywords)
    
    # ✅ 지역명 추출 (부산, 서울, 제주도 등)
    regions = ['부산', '서울', '제주도', '제주', '경주', '강릉', '대구', '인천', '광주', '대전', '울산', '해운대', '광안리']
    detected_region = None
    for region in regions:
        if region in query:
            detected_region = region
            break
    
    console.log(f"🔍 정확한 좌표 검색 시작: '{query}' (카페: {is_cafe_search}, 식당: {is_restaurant_search}, 관광지: {is_tourist_search}, 지역: {detected_region})")
    
    # ✅ 다단계 검색 전략
    search_strategies = []
    
    # 1단계: 정확한 매칭 전략
    if detected_region:
        search_strategies.extend([
            f"{detected_region} {cleaned_query}",
            f"{cleaned_query} {detected_region}",
        ])
    
    # 2단계: 장소 유형별 전략
    if is_cafe_search:
        search_strategies.extend([
            f"{detected_region} 카페" if detected_region else "카페",
            f"{detected_region} 커피" if detected_region else "커피",
            f"{cleaned_query} 카페",
            f"{cleaned_query} 커피",
        ])
    elif is_restaurant_search:
        search_strategies.extend([
            f"{detected_region} 맛집" if detected_region else "맛집",
            f"{detected_region} 식당" if detected_region else "식당",
            f"{cleaned_query} 맛집",
            f"{cleaned_query} 식당",
        ])
    elif is_tourist_search:
        search_strategies.extend([
            f"{detected_region} 관광지" if detected_region else "관광지",
            f"{detected_region} 명소" if detected_region else "명소",
            f"{cleaned_query} 관광지",
            f"{cleaned_query} 명소",
        ])
    
    # 3단계: 기본 검색어들
    search_strategies.extend([
        cleaned_query,
        query,  # 원본도 시도
    ])
    
    # 4단계: 부분 검색 전략
    if len(cleaned_query) > 2:
        search_strategies.extend([
            cleaned_query[:len(cleaned_query)//2],  # 절반만 검색
            cleaned_query.split()[0] if ' ' in cleaned_query else None,  # 첫 단어만
        ])
    
    # None 값 제거
    search_strategies = [q for q in search_strategies if q]
    
    console.log(f"📝 검색 전략 목록: {search_strategies}")
    
    all_candidates = []  # 모든 후보 저장
    
    for search_term in search_strategies:
        try:
            params = {
                "query": search_term,
                "size": 20,  # 더 많은 결과 검색
                "sort": "accuracy"  # 정확도 순으로 정렬
            }
            r = requests.get(url, headers=headers, params=params)
            data = r.json()
            
            if data.get("documents"):
                for doc in data["documents"]:
                    place_name = doc.get("place_name", "")
                    address = doc.get("address_name", "")
                    road_address = doc.get("road_address_name", "")
                    category = doc.get("category_name", "")
                    
                    # ✅ 종합 점수 계산 시스템
                    score = 0
                    
                    # 1. 장소명 정확도 (가장 중요)
                    if place_name.lower() == cleaned_query.lower():
                        score += 100  # 완전 일치
                    elif cleaned_query.lower() in place_name.lower():
                        score += 80  # 부분 일치
                    elif place_name.lower() in cleaned_query.lower():
                        score += 70  # 역방향 부분 일치
                    else:
                        # 유사도 계산
                        similarity = difflib.SequenceMatcher(None, cleaned_query.lower(), place_name.lower()).ratio()
                        score += int(similarity * 50)
                    
                    # 2. 장소 유형별 특별 처리
                    if is_cafe_search:
                        if "카페" in category or "커피" in category or "음식점" in category:
                            score += 30
                        if "카페" in place_name.lower() or "커피" in place_name.lower():
                            score += 25
                        if "카페" in address or "커피" in address:
                            score += 15
                    elif is_restaurant_search:
                        if "음식점" in category or "식당" in category:
                            score += 30
                        if any(keyword in place_name.lower() for keyword in restaurant_keywords):
                            score += 25
                    elif is_tourist_search:
                        if "관광" in category or "명소" in category:
                            score += 30
                        if any(keyword in place_name.lower() for keyword in tourist_keywords):
                            score += 25
                    
                    # 3. 지역명 일치도
                    if detected_region:
                        if detected_region in address or detected_region in road_address:
                            score += 20
                        if detected_region in place_name:
                            score += 15
                    
                    # 4. 카테고리 우선순위
                    if "관광" in category or "명소" in category:
                        score += 10
                    elif "음식점" in category or "카페" in category:
                        score += 8
                    elif "산" in category or "공원" in category:
                        score += 5
                    
                    # 5. 주소 정확도 (지역별)
                    if detected_region and detected_region in address:
                        score += 10
                    
                    # 6. 좌표 유효성 검사 (한국 내 좌표)
                    lat = float(doc.get("y", 0))
                    lng = float(doc.get("x", 0))
                    if validate_korean_coordinates(lat, lng, f"{place_name} {address}"):
                        score += 10
                    else:
                        continue  # 한국 밖이면 제외
                    
                    # 7. 장소 유형별 좌표 검증
                    if is_cafe_search:
                        # 카페는 도시 지역에 있어야 함
                        is_urban_area = (
                            (35.0 <= lat <= 35.5 and 128.5 <= lng <= 129.5) or  # 부산
                            (37.4 <= lat <= 37.7 and 126.8 <= lng <= 127.2) or  # 서울
                            (33.0 <= lat <= 33.5 and 126.0 <= lng <= 126.5) or  # 제주도
                            (35.7 <= lat <= 36.0 and 128.4 <= lng <= 128.8) or  # 대구
                            (37.4 <= lat <= 37.6 and 126.4 <= lng <= 126.8)    # 인천
                        )
                        if is_urban_area:
                            score += 20
                        else:
                            score -= 10  # 도시 지역이 아니면 감점
                    
                    # 후보에 추가
                    all_candidates.append({
                        'doc': doc,
                        'score': score,
                        'place_name': place_name,
                        'address': address,
                        'road_address': road_address,
                        'category': category,
                        'lat': lat,
                        'lng': lng
                    })
                    
                    console.log(f"📊 후보 점수: {place_name} = {score}점 (카테고리: {category}, 주소: {address})")
                        
        except Exception as e:
            console.log(f"카카오 지도 검색 오류 ({search_term}): {e}")
            continue
    
    # ✅ 모든 후보 중에서 최고 점수 선택
    if all_candidates:
        # 점수순으로 정렬
        all_candidates.sort(key=lambda x: x['score'], reverse=True)
        best_candidate = all_candidates[0]
        
        console.log(f"🏆 최고 점수 후보: {best_candidate['place_name']} = {best_candidate['score']}점")
        
        # ✅ 최소 점수 기준을 낮춰서 정확한 좌표를 무조건 반환
        if best_candidate['score'] > 10:  # 최소 점수를 10점으로 낮춤
            lat = best_candidate['lat']
            lng = best_candidate['lng']
            place_name = best_candidate['place_name']
            address = best_candidate['address']
            road_address = best_candidate['road_address']
            
            # 특별 처리 (유달산 등)
            if "유달산" in place_name and "목포" in address:
                lat = 34.786800
                lng = 126.415300
                console.log(f"✅ 유달산 좌표 수정: {place_name} ({lat}, {lng})")
            
            console.log(f"✅ 정확한 좌표 검색 성공: {place_name} ({lat}, {lng}) - 점수: {best_candidate['score']}")
            console.log(f"📍 주소: {road_address or address}")
            return lat, lng, place_name
        else:
            console.log(f"⚠️ 모든 후보의 점수가 낮음. 최고 점수: {best_candidate['score']}")
    
    # ✅ 백업 시스템: 정확한 좌표를 찾지 못한 경우
    from .coordinates import try_backup_coordinate_search
    console.log(f"🔄 백업 좌표 시스템 실행: '{query}'")
    backup_result = try_backup_coordinate_search(cleaned_query)
    if backup_result:
        console.log(f"✅ 백업 좌표 시스템 성공: {backup_result['place_name']} ({backup_result['lat']}, {backup_result['lng']})")
        return backup_result['lat'], backup_result['lng'], backup_result['place_name']
    
    console.log(f"❌ 모든 검색 방법 실패: {query}")
    return None


def clean_place_query(text: str) -> str:
    """자연어 입력에서 장소명만 추출"""
    # 불필요한 단어들 제거
    remove_words = [
        "근처", "추천", "정보", "상세", "맛집", "카페", "식당", "레스토랑",
        "해줘", "알려줘", "보여줘", "찾아줘", "검색해줘",
        "개", "곳", "군데", "어디", "뭐가", "뭐", "좀"
    ]
    
    cleaned = text
    # 숫자 제거
    cleaned = re.sub(r"\d+", "", cleaned)
    
    # 불필요한 단어 제거
    for word in remove_words:
        cleaned = cleaned.replace(word, "")
    
    # 연속된 공백 정리
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    
    return cleaned


def google_place_details(query: str):
    """구글 플레이스 API로 장소 상세정보 가져오기 (안전 버전)"""
    if not GOOGLE_API_KEY:
        return None

    try:
        # 1) 장소 검색 (Text Search API 호출)
        search_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        search_params = {
            "query": query,
            "key": GOOGLE_API_KEY,
            "language": "ko"
        }
        resp = requests.get(search_url, params=search_params, timeout=5)
        data = resp.json()

        # 응답 상태 확인
        if data.get("status") != "OK" or not data.get("results"):
            return None

        # 검색 결과에서 첫 번째 장소의 place_id 추출
        place_id = data["results"][0].get("place_id")
        if not place_id:
            return None

        # 2) 장소 상세정보 요청 (Details API 호출)
        details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        details_params = {
            "place_id": place_id,
            "key": GOOGLE_API_KEY,
            "language": "ko",
            "fields": "name,formatted_address,formatted_phone_number,geometry,opening_hours"
        }
        details_resp = requests.get(details_url, params=details_params, timeout=5)
        details = details_resp.json()

        if details.get("status") != "OK":
            return None

        result = details.get("result", {})

        # 운영시간 텍스트 정리
        opening_hours = result.get("opening_hours", {}).get("weekday_text", [])
        opening_hours_str = "\n".join(opening_hours) if opening_hours else "운영시간 정보 없음"

        return {
            "name": result.get("name", "이름 없음"),
            "address": result.get("formatted_address", "주소 없음"),
            "phone": result.get("formatted_phone_number", "전화번호 없음"),
            "location": result.get("geometry", {}).get("location"),  # 위도/경도 좌표
            "opening_hours": opening_hours_str
        }

    except Exception as e:
        # 네트워크 문제, JSON 파싱 문제 등
        console.log(f"[구글플레이스상세] 오류 발생: {e}")
        return None



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
            
            # 카카오 API 응답 검증 및 오류 처리
            if 'routes' in result and result['routes']:
                route = result['routes'][0]
                if 'result_code' in route and route['result_code'] != 0:
                    # 길찾기 실패 시 대체 좌표로 재시도
                    print(f"길찾기 실패: {route.get('result_msg', '알 수 없는 오류')}")
                    
                    # 좌표를 도로 근처로 조정하여 재시도
                    adjusted_origin_x, adjusted_origin_y = adjust_coordinates_to_road(origin_x, origin_y)
                    adjusted_dest_x, adjusted_dest_y = adjust_coordinates_to_road(dest_x, dest_y)
                    
                    if adjusted_origin_x != origin_x or adjusted_dest_x != dest_x:
                        print(f"좌표 조정 후 재시도: 원본({origin_x}, {origin_y}) -> 조정({adjusted_origin_x}, {adjusted_origin_y})")
                        kakao_body['origin'] = {'x': adjusted_origin_x, 'y': adjusted_origin_y}
                        kakao_body['destination'] = {'x': adjusted_dest_x, 'y': adjusted_dest_y}
                        
                        response = requests.post(kakao_url, headers=headers, json=kakao_body, timeout=10)
                        if response.status_code == 200:
                            result = response.json()
                            if 'routes' in result and result['routes']:
                                route = result['routes'][0]
                                if 'result_code' in route and route['result_code'] == 0:
                                    print("좌표 조정 후 길찾기 성공!")
                                else:
                                    print(f"좌표 조정 후에도 실패: {route.get('result_msg', '알 수 없는 오류')}")
            
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
        return JsonResponse({
            'error': '서버 내부 오류 발생',
            'error_message': str(e),
            'error_type': type(e).__name__
        }, status=500)


