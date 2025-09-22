// ================================ */
// 🔹 공통 상수 및 설정값들        */
// ================================ */

// === 카테고리 분류 키워드 ===
const CATEGORY_KEYWORDS = {
    // 숙소 관련 키워드
    accommodation: [
        '숙소', '호텔', '펜션', '리조트', '모텔', '게스트하우스', '민박', 
        '캠핑', '글램핑', '콘도', '아파트', '빌라'
    ],
    
    // 식당 관련 키워드 (음식명 포함)
    restaurant: [
        '식당', '맛집', '레스토랑', '점심', '저녁', '아침', '식사',
        '막국수', '해장국', '국수', '냉면', '라면', '김치찌개', '된장찌개', '비빔밥', '불고기', '갈비',
        '치킨', '피자', '햄버거', '샐러드', '파스타', '스테이크', '초밥', '회', '생선', '고기',
        '떡볶이', '순대', '김밥', '만두', '전', '부침개', '찜', '탕', '찌개', '국',
        '밥', '죽', '면', '빵', '케이크', '디저트', '아이스크림', '과자', '과일', '야채',
        '술', '맥주', '소주', '와인', '칵테일', '바', '펍', '이자카야', '포차'
    ],
    
    // 관광지 관련 키워드
    tourist: [
        '공원', '박물관', '미술관', '전시관', '갤러리', '문화관', '예술관', '기념관', '기념탑',
        '사찰', '절', '교회', '성당', '사원', '궁', '궁전', '성', '성벽', '문',
        '탑', '다리', '교', '광장', '시장', '상가', '쇼핑', '마트', '백화점',
        '해변', '바다', '산', '봉', '봉우리', '계곡', '폭포', '호수', '강', '섬',
        '동물원', '식물원', '수목원', '아쿠아리움', '테마파크', '놀이공원', '워터파크', '스키장',
        '온천', '스파', '찜질방', '사우나', '헬스', '피트니스', '골프', '테니스',
        '캠핑장', '야영장', '관광지', '명소', '유적', '유적지', '문화재', '보물'
    ],
    
    // 카페 관련 키워드
    cafe: [
        '카페', '커피', '음료', '차', '티', '라떼', '아메리카노', '에스프레소', '쥬스', '스무디'
    ]
};

// === 좌표 검증 설정 ===
const COORDINATE_BOUNDS = {
    // 한국 전체 좌표 범위
    korea: {
        lat: { min: 33, max: 39 },
        lng: { min: 124, max: 132 }
    },
    
    // 지역별 세부 좌표 범위
    regions: {
        '목포': {
            lat: { min: 34.5, max: 35.0 },
            lng: { min: 126.0, max: 126.5 }
        },
        '경주': {
            lat: { min: 35.7, max: 36.0 },
            lng: { min: 129.0, max: 129.5 }
        },
        '서울': {
            lat: { min: 37.4, max: 37.7 },
            lng: { min: 126.8, max: 127.2 }
        },
        '부산': {
            lat: { min: 35.0, max: 35.3 },
            lng: { min: 128.8, max: 129.3 }
        },
        '해운대': {
            lat: { min: 35.15, max: 35.17 },
            lng: { min: 129.15, max: 129.18 }
        }
    }
};

// === 기본 일정 구조 ===
const DEFAULT_DAY_SCHEDULE = { 
    숙소: [], 
    식당: [], 
    카페: [], 
    관광지: [], 
    기타: [] 
};

// === Day별 색상 ===
const DAY_COLORS = { 
    Day1: '#FF0000', 
    Day2: '#007bff', 
    Day3: '#00c853', 
    Day4: '#ff6d00', 
    Day5: '#6a1b9a' 
};

// === 카테고리 목록 ===
const CATEGORIES = ['숙소', '식당', '카페', '관광지', '기타'];

// === 유틸리티 함수들 ===
const Utils = {
    // 카테고리 분류 함수
    categorizePlace: function(placeName, activity = '') {
        const name = placeName.toLowerCase();
        const activityLower = activity.toLowerCase();
        
        // 숙소 분류
        if (CATEGORY_KEYWORDS.accommodation.some(keyword => 
            name.includes(keyword) || activityLower.includes(keyword))) {
            return '숙소';
        }
        
        // 카페 분류 (식당보다 먼저 확인)
        if (CATEGORY_KEYWORDS.cafe.some(keyword => 
            name.includes(keyword) || activityLower.includes(keyword))) {
            return '카페';
        }
        
        // 식당 분류
        if (CATEGORY_KEYWORDS.restaurant.some(keyword => 
            name.includes(keyword) || activityLower.includes(keyword))) {
            return '식당';
        }
        
        // 관광지 분류
        if (CATEGORY_KEYWORDS.tourist.some(keyword => 
            name.includes(keyword) || activityLower.includes(keyword))) {
            return '관광지';
        }
        
        // 분류되지 않으면 기타
        return '기타';
    },
    
    // 좌표 검증 함수
    validateCoordinate: function(placeName, lat, lng) {
        const latNum = parseFloat(lat);
        const lngNum = parseFloat(lng);
        
        console.log(`=== 좌표 검증: ${placeName} ===`);
        console.log(`원본 좌표: (${lat}, ${lng})`);
        console.log(`파싱된 좌표: (${latNum}, ${lngNum})`);
        
        // 기본 유효성 검사
        if (isNaN(latNum) || isNaN(lngNum)) {
            console.error(`❌ 숫자가 아닌 좌표: ${placeName}`);
            return false;
        }
        
        if (latNum < -90 || latNum > 90 || lngNum < -180 || lngNum > 180) {
            console.error(`❌ 좌표 범위 초과: ${placeName} (${latNum}, ${lngNum})`);
            return false;
        }
        
        // 한국 지역 검사
        const korea = COORDINATE_BOUNDS.korea;
        if (!(korea.lat.min <= latNum <= korea.lat.max) || 
            !(korea.lng.min <= lngNum <= korea.lng.max)) {
            console.error(`❌ 한국 지역이 아닌 좌표: ${placeName} (${latNum}, ${lngNum})`);
            return false;
        }
        
        // ✅ 카페 특별 검증 (산에 찍히는 문제 방지)
        const cafeKeywords = ['카페', '커피', 'coffee', 'cafe'];
        const isCafe = cafeKeywords.some(keyword => placeName.toLowerCase().includes(keyword));
        
        if (isCafe) {
            console.log(`☕ 카페 좌표 특별 검증: ${placeName}`);
            
            // 카페는 도시 지역에 있어야 함
            const isUrbanArea = (
                // 부산 지역
                (35.0 <= latNum <= 35.5 && 128.5 <= lngNum <= 129.5) ||
                // 서울 지역
                (37.4 <= latNum <= 37.7 && 126.8 <= lngNum <= 127.2) ||
                // 제주도 지역
                (33.0 <= latNum <= 33.5 && 126.0 <= lngNum <= 126.5) ||
                // 대구 지역
                (35.7 <= latNum <= 36.0 && 128.4 <= lngNum <= 128.8) ||
                // 인천 지역
                (37.4 <= latNum <= 37.6 && 126.4 <= lngNum <= 126.8)
            );
            
            if (!isUrbanArea) {
                console.warn(`⚠️ 카페가 도시 지역이 아닌 곳에 위치: ${placeName} (${latNum}, ${lngNum})`);
                console.warn(`📍 이 좌표는 산이나 시골 지역일 가능성이 높습니다.`);
                return false;
            } else {
                console.log(`✅ 카페 도시 지역 좌표 확인: ${placeName}`);
            }
        }
        
        // 지역별 세부 검사
        for (const [region, bounds] of Object.entries(COORDINATE_BOUNDS.regions)) {
            if (placeName.includes(region)) {
                if (!(bounds.lat.min <= latNum <= bounds.lat.max) || 
                    !(bounds.lng.min <= lngNum <= bounds.lng.max)) {
                    console.warn(`⚠️ ${region} 지역이 아닌 좌표: ${placeName} (${latNum}, ${lngNum})`);
                    console.warn(`${region} 지역 좌표 범위: 위도 ${bounds.lat.min}-${bounds.lat.max}, 경도 ${bounds.lng.min}-${bounds.lng.max}`);
                    return false;
                } else {
                    console.log(`✅ ${region} 지역 좌표 확인: ${placeName}`);
                }
            }
        }
        
        return true;
    },
    
    // 검색어 정리 함수
    cleanQuery: function(text) {
        const STOPWORDS = ["추천", "일정", "시간", "도착", "출발", "점심", "저녁", "식사", "활동", "옵션", "여행", "코스", "계획", "그럼"];
        const cleaned = text.replace(/[^가-힣A-Za-z0-9 ]/g, " ");
        const tokens = cleaned.split().filter(t => !STOPWORDS.includes(t) && t.length > 1);
        return tokens.join(" ");
    }
};

// 전역에서 사용할 수 있도록 window 객체에 추가
if (typeof window !== 'undefined') {
    window.CATEGORY_KEYWORDS = CATEGORY_KEYWORDS;
    window.COORDINATE_BOUNDS = COORDINATE_BOUNDS;
    window.DEFAULT_DAY_SCHEDULE = DEFAULT_DAY_SCHEDULE;
    window.DAY_COLORS = DAY_COLORS;
    window.CATEGORIES = CATEGORIES;
    window.Utils = Utils;
}
