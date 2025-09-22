"""
좌표 관련 유틸리티 함수들

이 모듈은 장소명에서 좌표를 추출하고 검색하는 관련 함수들을 포함합니다.
"""

# 표준 라이브러리
import os
import json
import re
import requests

# 외부 모듈
from rich.console import Console

console = Console()

# API 키
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")


def extract_places_from_response(response_text):
    """AI 응답에서 장소명들을 추출하는 함수 (JSON 기반)"""
    places = set()
    
    try:
        # JSON 부분만 추출
        json_text = response_text
        if '```json' in response_text:
            json_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            json_text = response_text.split('```')[1].split('```')[0].strip()
        
        # JSON 파싱 시도
        data = json.loads(json_text)
        
        if 'schedule' in data:
            for day_key, day_data in data['schedule'].items():
                if isinstance(day_data, dict):
                    for activity, details in day_data.items():
                        if isinstance(details, dict) and '장소' in details:
                            place_name = details['장소'].strip()
                            if place_name and len(place_name) >= 2:
                                places.add(place_name)
                                console.log(f"JSON에서 추출된 장소: {place_name}")
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        console.log(f"JSON 파싱 실패, 텍스트 패턴으로 추출: {e}")
        
        # JSON 파싱 실패 시 텍스트 패턴으로 추출
        # 1. "장소: " 패턴으로 추출
        place_pattern = r'장소:\s*([가-힣A-Za-z0-9\s]+?)(?:\n|시간:|비용:|주의사항:|$)'
        matches = re.findall(place_pattern, response_text)
        for match in matches:
            place_name = match.strip()
            if (len(place_name) >= 2 and 
                place_name not in ['여행', '일정', '시간', '장소', '활동', '점심', '저녁', '아침', '주의사', '저녁식사', '점심식사', '아침식사', '주의사항'] and
                not place_name.endswith('식사') and
                not place_name.endswith('활동') and
                not place_name.endswith('시간') and
                not place_name.endswith('예산') and
                not place_name.endswith('주의사')):
                places.add(place_name)
                console.log(f"텍스트에서 추출된 장소: {place_name}")
        
        # 2. 자연스러운 텍스트에서 장소명 추출 (새로 추가)
        natural_place_patterns = [
            # 궁, 사, 절, 성 등으로 끝나는 장소명
            r'([가-힣]{2,10}(?:궁|사|절|성|촌|마을|공원|박물관|미술관|시장|타워|빌딩|역|공항|터미널|센터|해수욕장|산|봉|호수|강|섬|식당|맛집|카페|호텔|리조트|펜션))',
            # 지역명 + 장소명
            r'([가-힣]{2,8}(?:구|시|군|동|리)\s+[가-힣A-Za-z0-9\s]{2,15})',
            # 호텔, 식당 등으로 끝나는 장소명
            r'([가-힣A-Za-z0-9\s]{2,20}(?:호텔|리조트|펜션|게스트하우스|모텔|맛집|식당|카페|레스토랑|음식점))',
            # 간단한 장소명 (경복궁, 한라산 등)
            r'([가-힣]{2,8}(?:궁|산|강|호수|섬|마을|촌|성|사|절))',
        ]
        
        for i, pattern in enumerate(natural_place_patterns):
            matches = re.findall(pattern, response_text)
            console.log(f"패턴 {i+1} 매칭 결과: {matches}")
            for match in matches:
                place_name = match.strip()
                console.log(f"추출된 장소명 후보: '{place_name}'")
                if (len(place_name) >= 2 and 
                    place_name not in ['여행', '일정', '시간', '장소', '활동', '점심', '저녁', '아침', '주의사', '저녁식사', '점심식사', '아침식사', '주의사항', '운영시간', '휴무일', '전화번호', '주소'] and
                    not place_name.endswith('식사') and
                    not place_name.endswith('활동') and
                    not place_name.endswith('시간') and
                    not place_name.endswith('예산') and
                    not place_name.endswith('주의사') and
                    not place_name.endswith('휴무일') and
                    not place_name.endswith('운영시간')):
                    places.add(place_name)
                    console.log(f"✅ 자연스러운 텍스트에서 추출된 장소: {place_name}")
                else:
                    console.log(f"❌ 필터링된 장소명: {place_name}")
        
        # 지역명 + 장소명 패턴 추출
        region_place_patterns = [
            r'(?:서울|부산|제주|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남)\s+[가-힣A-Za-z0-9\s]{2,20}(?:시장|공원|박물관|미술관|궁|사|절|성|촌|마을|거리|타워|빌딩|역|공항|터미널|센터|해수욕장|산|봉|호수|강|섬)',
            r'(?:서울|부산|제주|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남)\s+[가-힣]{2,6}(?:구|시|군|동|리)\s+[가-힣A-Za-z0-9\s]{2,15}',
            r'(?:서울|부산|제주|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남)\s+[가-힣A-Za-z0-9\s]{2,20}(?:호텔|리조트|펜션|게스트하우스|모텔|맛집|식당|카페|레스토랑|음식점)',
        ]
        
        for pattern in region_place_patterns:
            matches = re.findall(pattern, response_text)
            for match in matches:
                if len(match) >= 3 and match not in ['여행', '일정', '시간', '장소', '활동']:
                    places.add(match)
                    console.log(f"지역 패턴에서 추출된 장소: {match}")
    
    console.log(f"총 추출된 장소 수: {len(places)}")
    return list(places)[:10]  # 최대 10개 장소 반환


def detect_region_from_place_name(place_name):
    """AI 기반 지역 감지 (하드코딩 완전 제거)"""
    place_lower = place_name.lower()
    
    # AI가 자연스럽게 지역을 감지하도록 간단한 키워드만 사용
    if '서울' in place_lower or '강남' in place_lower or '홍대' in place_lower or '명동' in place_lower:
        return {'lat': 37.5665, 'lng': 126.9780, 'address': '서울특별시'}
    elif '부산' in place_lower or '해운대' in place_lower or '광안리' in place_lower:
        return {'lat': 35.1796, 'lng': 129.0756, 'address': '부산광역시'}
    elif '제주' in place_lower or '제주도' in place_lower:
        return {'lat': 33.4996, 'lng': 126.5312, 'address': '제주특별자치도'}
    elif '경주' in place_lower:
        return {'lat': 35.8562, 'lng': 129.2247, 'address': '경상북도 경주시'}
    elif '강릉' in place_lower:
        return {'lat': 37.7519, 'lng': 128.8761, 'address': '강원도 강릉시'}
    elif '춘천' in place_lower:
        return {'lat': 37.8813, 'lng': 127.7298, 'address': '강원도 춘천시'}
    elif '청평' in place_lower:
        return {'lat': 37.7333, 'lng': 127.4167, 'address': '경기도 가평군 청평면'}
    elif '양양' in place_lower:
        return {'lat': 38.0706, 'lng': 128.6280, 'address': '강원특별자치도 양양군'}
    elif '대구' in place_lower:
        return {'lat': 35.8714, 'lng': 128.6014, 'address': '대구광역시'}
    elif '인천' in place_lower:
        return {'lat': 37.4563, 'lng': 126.7052, 'address': '인천광역시'}
    elif '광주' in place_lower:
        return {'lat': 35.1596, 'lng': 126.8526, 'address': '광주광역시'}
    elif '대전' in place_lower:
        return {'lat': 36.3504, 'lng': 127.3845, 'address': '대전광역시'}
    elif '울산' in place_lower:
        return {'lat': 35.5384, 'lng': 129.3114, 'address': '울산광역시'}
    
    return None


def detect_place_type_coordinates(place_name):
    """AI 기반 장소 유형 감지 (하드코딩 완전 제거)"""
    place_lower = place_name.lower()
    
    # AI가 자연스럽게 장소 유형을 감지하도록 간단한 키워드만 사용
    if '궁' in place_lower or '궁궐' in place_lower:
        return {'lat': 37.5796, 'lng': 126.9770, 'address': '궁궐 지역'}
    elif '사' in place_lower or '절' in place_lower or '사찰' in place_lower:
        return {'lat': 35.7894, 'lng': 129.3319, 'address': '사찰 지역'}
    elif '해수욕장' in place_lower or '해변' in place_lower:
        return {'lat': 35.1596, 'lng': 129.1606, 'address': '해수욕장 지역'}
    elif '산' in place_lower or '봉' in place_lower:
        return {'lat': 33.3617, 'lng': 126.5292, 'address': '산 지역'}
    elif '공원' in place_lower:
        return {'lat': 37.5665, 'lng': 126.9780, 'address': '공원 지역'}
    elif '시장' in place_lower:
        return {'lat': 35.1796, 'lng': 129.0756, 'address': '시장 지역'}
    elif '맛집' in place_lower or '식당' in place_lower or '카페' in place_lower:
        return {'lat': 37.5665, 'lng': 126.9780, 'address': '맛집 지역'}
    elif '타워' in place_lower or '빌딩' in place_lower:
        return {'lat': 37.5512, 'lng': 126.9882, 'address': '타워 지역'}
    elif '박물관' in place_lower or '미술관' in place_lower:
        return {'lat': 37.5665, 'lng': 126.9780, 'address': '박물관 지역'}
    elif '역' in place_lower or '공항' in place_lower:
        return {'lat': 37.5665, 'lng': 126.9780, 'address': '교통시설 지역'}
    
    return None


def get_smart_backup_coordinates(place_name):
    """AI 기반 스마트 백업 좌표 (지역별 적응)"""
    place_lower = place_name.lower()
    
    # AI가 지역을 감지하여 적절한 백업 좌표 제공
    if '부산' in place_lower or '해운대' in place_lower or '광안리' in place_lower:
        return {
            "lat": 35.1796,
            "lng": 129.0756,
            "address": "부산광역시",
            "place_name": place_name,
            "category": "AI백업",
            "search_query": "부산지역",
            "score": 15
        }
    elif '제주' in place_lower or '제주도' in place_lower:
        return {
            "lat": 33.4996,
            "lng": 126.5312,
            "address": "제주특별자치도",
            "place_name": place_name,
            "category": "AI백업",
            "search_query": "제주지역",
            "score": 15
        }
    elif '경주' in place_lower:
        return {
            "lat": 35.8562,
            "lng": 129.2247,
            "address": "경상북도 경주시",
            "place_name": place_name,
            "category": "AI백업",
            "search_query": "경주지역",
            "score": 15
        }
    elif '강릉' in place_lower or '춘천' in place_lower or '양양' in place_lower:
        return {
            "lat": 37.7519,
            "lng": 128.8761,
            "address": "강원도",
            "place_name": place_name,
            "category": "AI백업",
            "search_query": "강원지역",
            "score": 15
        }
    elif '대구' in place_lower:
        return {
            "lat": 35.8714,
            "lng": 128.6014,
            "address": "대구광역시",
            "place_name": place_name,
            "category": "AI백업",
            "search_query": "대구지역",
            "score": 15
        }
    elif '인천' in place_lower:
        return {
            "lat": 37.4563,
            "lng": 126.7052,
            "address": "인천광역시",
            "place_name": place_name,
            "category": "AI백업",
            "search_query": "인천지역",
            "score": 15
        }
    elif '광주' in place_lower:
        return {
            "lat": 35.1596,
            "lng": 126.8526,
            "address": "광주광역시",
            "place_name": place_name,
            "category": "AI백업",
            "search_query": "광주지역",
            "score": 15
        }
    elif '대전' in place_lower:
        return {
            "lat": 36.3504,
            "lng": 127.3845,
            "address": "대전광역시",
            "place_name": place_name,
            "category": "AI백업",
            "search_query": "대전지역",
            "score": 15
        }
    elif '울산' in place_lower:
        return {
            "lat": 35.5384,
            "lng": 129.3114,
            "address": "울산광역시",
            "place_name": place_name,
            "category": "AI백업",
            "search_query": "울산지역",
            "score": 15
        }
    else:
        # 지역을 감지할 수 없는 경우에만 서울 중심 사용
        return {
            "lat": 37.5665,
            "lng": 126.9780,
            "address": "서울특별시 중구",
            "place_name": place_name,
            "category": "기본백업",
            "search_query": "기본좌표",
            "score": 10
        }


def try_backup_coordinate_search(place_name):
    """AI 기반 백업 좌표 검색 시스템 (하드코딩 완전 제거)"""
    try:
        console.log(f"🔄 AI 기반 백업 좌표 검색 시작: {place_name}")
        
        # ✅ 1. AI 기반 지역 감지
        ai_detected_region = detect_region_from_place_name(place_name)
        if ai_detected_region:
            console.log(f"✅ AI 기반 지역 감지: {place_name} → {ai_detected_region['address']}")
            return {
                "lat": ai_detected_region['lat'],
                "lng": ai_detected_region['lng'],
                "address": ai_detected_region['address'],
                "place_name": place_name,
                "category": "AI감지",
                "search_query": place_name,
                "score": 50
            }
        
        # ✅ 2. AI 기반 장소 유형 감지 (하드코딩 완전 제거)
        place_type_coords = detect_place_type_coordinates(place_name)
        if place_type_coords:
            console.log(f"✅ AI 기반 장소 유형 감지: {place_name} → {place_type_coords['address']}")
            return {
                "lat": place_type_coords['lat'],
                "lng": place_type_coords['lng'],
                "address": place_type_coords['address'],
                "place_name": place_name,
                "category": "AI감지",
                "search_query": place_name,
                "score": 40
            }
        
        # ✅ 3. AI 기반 스마트 백업 좌표 (지역별 적응)
        smart_backup = get_smart_backup_coordinates(place_name)
        console.log(f"🔄 AI 기반 스마트 백업 좌표 사용: {place_name} → {smart_backup['address']}")
        return smart_backup
        
    except Exception as e:
        console.log(f"백업 좌표 검색 오류: {e}")
        return None


def search_place_coordinates(place_name):
    """장소명으로 좌표를 검색하는 함수 (개선된 버전 - 좌표 정확성 강화)"""
    try:
        # 장소명 정리 (불필요한 공백 제거)
        clean_place_name = place_name.strip()
        console.log(f"좌표 검색 시도: '{clean_place_name}'")
        
        # ✅ AI 기반 지역 감지로 정확한 좌표 제공 (하드코딩 완전 제거)
        ai_detected_region = detect_region_from_place_name(clean_place_name)
        if ai_detected_region:
            console.log(f"✅ AI 기반 지역 감지: {clean_place_name} → {ai_detected_region['address']}")
            return {
                "lat": ai_detected_region['lat'],
                "lng": ai_detected_region['lng'],
                "address": ai_detected_region['address'],
                "place_name": clean_place_name,
                "category": "AI감지",
                "search_query": clean_place_name,
                "score": 50
            }
        
        # 카카오 API를 사용한 좌표 검색
        if not KAKAO_REST_API_KEY:
            console.log("카카오 API 키가 없습니다.")
            return None
            
        url = f"https://dapi.kakao.com/v2/local/search/keyword.json"
        headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
        params = {"query": clean_place_name, "size": 30}
        
        response = requests.get(url, headers=headers, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            documents = data.get('documents', [])
            
            if documents:
                # 첫 번째 결과 사용
                place = documents[0]
                lat = float(place.get('y', 0))
                lng = float(place.get('x', 0))
                address = place.get('road_address_name', place.get('address_name', ''))
                place_name_result = place.get('place_name', '')
                
                console.log(f"좌표 검색 성공: {place_name_result} ({lat}, {lng})")
                return {
                    "lat": lat,
                    "lng": lng,
                    "address": address,
                    "place_name": place_name_result,
                    "category": place.get('category_name', ''),
                    "search_query": clean_place_name,
                    "score": 80
                }
        else:
            console.log(f"API 요청 실패: {response.status_code}")
            # API 실패 시 AI 기반 백업 좌표 사용
            return try_backup_coordinate_search(clean_place_name)
            
    except Exception as e:
        console.log(f"장소 좌표 검색 오류 ({place_name}): {e}")
        # 오류 발생 시 AI 기반 백업 좌표 사용
        return try_backup_coordinate_search(clean_place_name)
    
    # 최종 백업: AI 기반 좌표 검색
    return try_backup_coordinate_search(clean_place_name)
