// ================================ */
// 🔹 지도 페이지 서버 통신 함수들    */
// ================================ */

// ✅ URL 파라미터에서 schedule_id 확인 후 API로 일정 불러오기
async function loadScheduleFromServer() {
    const params = new URLSearchParams(window.location.search);
    if (params.has("schedule_id")) {
        const sid = params.get("schedule_id");
        
        // 임시 ID인 경우 sessionStorage에서 데이터 가져오기
        if (sid.startsWith('temp_')) {
            console.log('임시 ID 감지:', sid);
            try {
                const sel = sessionStorage.getItem('selected_schedule');
                console.log('sessionStorage에서 가져온 데이터:', sel);
                if (sel) {
                    const parsed = JSON.parse(sel);
                    console.log('파싱된 데이터:', parsed);
                    if (parsed && parsed.data) {
                        const data = parsed.data;
                        console.log('임시 데이터 로드:', data);
                        
                        // 최신 JSON 구조 처리
                        if (data.schedule && typeof data.schedule === 'object') {
                            console.log('최신 JSON 구조 감지됨:', data.schedule);
                            schedule = {};
                            let totalPlaces = 0;
                            
                            for (const [dayKey, dayData] of Object.entries(data.schedule)) {
                                schedule[dayKey] = structuredClone(DEFAULT_DAY_SCHEDULE);
                                
                                for (const [activity, details] of Object.entries(dayData)) {
                                    if (details.장소 && details.좌표) {
                                        const place = {
                                            name: details.장소,
                                            address: details.주소 || "",
                                            lat: parseFloat(details.좌표.lat),
                                            lng: parseFloat(details.좌표.lng)
                                        };
                                        
                                        console.log(`장소 추가: ${place.name} (${place.lat}, ${place.lng})`);
                                        
                                        // 활동 유형에 따라 카테고리 분류 (개선된 분류)
                                        const activityLower = activity.toLowerCase();
                                        const placeNameLower = place.name.toLowerCase();
                                        
                                        // 공통 유틸리티를 사용한 카테고리 분류
                                        const category = Utils.categorizePlace(place.name, activity);
                                        schedule[dayKey][category].push(place);
                                        totalPlaces++;
                                    } else {
                                        console.warn(`좌표가 없는 활동: ${activity}`, details);
                                    }
                                }
                            }
                            
                            currentDay = Object.keys(schedule)[0] || "Day1";
                            saveSchedule();
                            console.log(`총 ${totalPlaces}개의 장소가 로드됨`);
                            alert(`지도에 ${totalPlaces}개의 장소가 표시됩니다!`);
                            
                            // 지도 중심점 업데이트
                            updateMapCenter();
                            return;
                        }
                    }
                }
            } catch (err) {
                console.error("임시 데이터 로드 실패:", err);
            }
        }
        
        try {
            const res = await fetch(`/get_schedule/${sid}/`);
            if (!res.ok) throw new Error("서버 응답 오류");
            const data = await res.json();
            console.log('서버에서 받은 데이터:', data);

            // ✅ 1) 최신 JSON 구조로 저장된 경우 (schedule.Day1 형태)
            if (data && data.schedule && typeof data.schedule === 'object') {
                console.log('최신 JSON 구조 감지됨:', data.schedule);
                // 최신 JSON 구조를 기존 형식으로 변환
                schedule = {};
                let totalPlaces = 0;
                
                for (const [dayKey, dayData] of Object.entries(data.schedule)) {
                    schedule[dayKey] = { 숙소: [], 식당: [], 카페: [], 관광지: [], 기타: [] };
                    
                    for (const [activity, details] of Object.entries(dayData)) {
                        if (details.장소 && details.좌표) {
                            const place = {
                                name: details.장소,
                                address: details.주소 || "",
                                lat: parseFloat(details.좌표.lat),
                                lng: parseFloat(details.좌표.lng)
                            };
                            
                            console.log(`서버에서 장소 로드: ${place.name} (${place.lat}, ${place.lng})`);
                            
                            // 활동 유형에 따라 카테고리 분류 (개선된 분류)
                            const activityLower = activity.toLowerCase();
                            const placeNameLower = place.name.toLowerCase();
                            
                            // 공통 유틸리티를 사용한 카테고리 분류
                            const category = Utils.categorizePlace(place.name, activity);
                            schedule[dayKey][category].push(place);
                            totalPlaces++;
                        } else {
                            console.warn(`서버 데이터에서 좌표가 없는 활동: ${activity}`, details);
                        }
                    }
                }
                
                currentDay = Object.keys(schedule)[0] || "Day1";
                saveSchedule();
                console.log(`서버에서 총 ${totalPlaces}개의 장소 로드됨`);
                alert(`지도에 ${totalPlaces}개의 장소가 표시됩니다!`);
                
                // 지도 중심점 업데이트
                updateMapCenter();
            }
            // ✅ 1-2) data 자체가 schedule 구조인 경우 (직접 schedule 객체)
            else if (data && typeof data === 'object' && (data.Day1 || data.Day2 || data.Day3)) {
                console.log('직접 schedule 구조 감지됨');
                schedule = data;
                currentDay = Object.keys(schedule)[0] || "Day1";
                
                // 기존 데이터에서 "좌표 x" 형태의 장소명을 실제 장소명으로 변환
                let totalPlaces = 0;
                for (const dayKey of Object.keys(schedule)) {
                    for (const category of ['숙소', '식당', '카페', '관광지', '기타']) {
                        if (schedule[dayKey][category]) {
                            schedule[dayKey][category] = schedule[dayKey][category].map((place, index) => {
                                // "좌표 x" 형태인 경우 실제 장소명으로 변환
                                if (place.name && place.name.startsWith('좌표')) {
                                    const placeName = `장소 ${index + 1}`;
                                    console.log(`장소명 변환: ${place.name} → ${placeName}`);
                                    return { ...place, name: placeName };
                                }
                                return place;
                            });
                            totalPlaces += schedule[dayKey][category].length;
                        }
                    }
                }
                saveSchedule();
                alert(`지도에 ${totalPlaces}개의 장소가 표시됩니다!`);
            }
            // ✅ 2) 기존 Day 구조(JSON)로 저장된 경우 그대로 사용 (이미 위에서 처리됨)
            else if (data && typeof data === 'object' && (data.Day1 || data.Day2 || data.Day3)) {
                console.log('기존 Day 구조 감지됨 (중복 처리)');
                // 이미 위에서 처리되었으므로 여기서는 건너뛰기
                
                // 기존 데이터에서 "좌표 x" 형태의 장소명을 실제 장소명으로 변환
                let totalPlaces = 0;
                for (const dayKey of Object.keys(schedule)) {
                    for (const category of ['숙소', '식당', '카페', '관광지', '기타']) {
                        if (schedule[dayKey][category]) {
                            schedule[dayKey][category] = schedule[dayKey][category].map((place, index) => {
                                // "좌표 x" 형태인 경우 실제 장소명으로 변환
                                if (place.name && place.name.startsWith('좌표')) {
                                    // 좌표를 기반으로 실제 장소명 생성
                                    const placeName = `장소 ${index + 1}`;
                                    console.log(`장소명 변환: ${place.name} → ${placeName}`);
                                    return { ...place, name: placeName };
                                }
                                return place;
                            });
                            totalPlaces += schedule[dayKey][category].length;
                        }
                    }
                }
                console.log(`기존 데이터에서 총 ${totalPlaces}개의 장소 발견`);
                
                saveSchedule();
                if (totalPlaces > 0) {
                    alert(`지도에 ${totalPlaces}개의 장소가 표시됩니다!`);
                    // 지도 중심점 업데이트
                    updateMapCenter();
                }
            } else {
                // ✅ 3) 기존 텍스트 기반 일정 (하위 호환성)
                console.log('기존 텍스트 형식 일정 처리:', data);
                alert('기존 형식의 일정입니다. 최신 JSON 형식으로 다시 생성해주세요.');
            }
        } catch (err) {
            console.error("일정 불러오기 실패:", err);
            alert("일정을 불러올 수 없습니다.");
        }
    }
}

// === 초기 렌더 ===
async function loadChatbotSchedule() {
    // ✅ sessionStorage에 선택된 일정이 있으면 우선 사용
    try {
        const sel = sessionStorage.getItem('selected_schedule');
        if (sel) {
            const parsed = JSON.parse(sel);
            if (parsed && parsed.data && typeof parsed.data === 'object') {
                // 최신 JSON 구조 처리
                if (parsed.data.schedule && typeof parsed.data.schedule === 'object') {
                    console.log('sessionStorage에서 최신 JSON 구조 로드:', parsed.data.schedule);
                    schedule = {};
                    let totalPlaces = 0;
                    
                    for (const [dayKey, dayData] of Object.entries(parsed.data.schedule)) {
                        schedule[dayKey] = structuredClone(DEFAULT_DAY_SCHEDULE);
                        
                        for (const [activity, details] of Object.entries(dayData)) {
                            if (details.장소 && details.좌표) {
                                const place = {
                                    name: details.장소,
                                    address: details.주소 || "",
                                    lat: parseFloat(details.좌표.lat),
                                    lng: parseFloat(details.좌표.lng)
                                };
                                
                                console.log(`sessionStorage에서 장소 로드: ${place.name} (${place.lat}, ${place.lng})`);
                                
                                // 활동 유형에 따라 카테고리 분류 (개선된 분류)
                                const activityLower = activity.toLowerCase();
                                const placeNameLower = place.name.toLowerCase();
                                
                                // 공통 유틸리티를 사용한 카테고리 분류
                                const category = Utils.categorizePlace(place.name, activity);
                                schedule[dayKey][category].push(place);
                                totalPlaces++;
                            } else {
                                console.warn(`sessionStorage에서 좌표가 없는 활동: ${activity}`, details);
                            }
                        }
                    }
                    
                    currentDay = Object.keys(schedule)[0] || 'Day1';
                    console.log(`sessionStorage에서 총 ${totalPlaces}개의 장소 로드됨`);
                    alert(`지도에 ${totalPlaces}개의 장소가 표시됩니다!`);
                    
                    // 지도 중심점 업데이트
                    updateMapCenter();
                }
                // ✅ 챗봇에서 전달된 places 배열 처리
                else if (parsed.data.places && Array.isArray(parsed.data.places)) {
                    console.log('챗봇 places 데이터 처리:', parsed.data.places);
                    schedule = { Day1: structuredClone(DEFAULT_DAY_SCHEDULE) };
                    currentDay = 'Day1';
                    let totalPlaces = 0;
                    
                    parsed.data.places.forEach(place => {
                        if (place.lat && place.lng && !isNaN(parseFloat(place.lat)) && !isNaN(parseFloat(place.lng))) {
                            const placeObj = {
                                name: place.name || '장소',
                                address: place.address || "",
                                lat: parseFloat(place.lat),
                                lng: parseFloat(place.lng)
                            };
                            
                            console.log(`places에서 장소 로드: ${placeObj.name} (${placeObj.lat}, ${placeObj.lng})`);
                            
                            // 공통 유틸리티를 사용한 카테고리 분류
                            const category = Utils.categorizePlace(place.name);
                            schedule.Day1[category].push(placeObj);
                            totalPlaces++;
                        } else {
                            console.warn(`places에서 유효하지 않은 좌표:`, place);
                        }
                    });
                    
                    console.log(`places 데이터로 총 ${totalPlaces}개의 장소 생성됨:`, schedule);
                    alert(`지도에 ${totalPlaces}개의 장소가 표시됩니다!`);
                    
                    // 지도 중심점 업데이트
                    updateMapCenter();
                }
                // 기존 Day 구조 처리
                else if (parsed.data.Day1 || parsed.data.Day2 || parsed.data.Day3) {
                    schedule = parsed.data;
                    currentDay = Object.keys(schedule)[0] || 'Day1';
                    
                    // 기존 데이터에서 "좌표 x" 형태의 장소명을 실제 장소명으로 변환
                    for (const dayKey of Object.keys(schedule)) {
                        for (const category of ['숙소', '식당', '카페', '관광지', '기타']) {
                            if (schedule[dayKey][category]) {
                                schedule[dayKey][category] = schedule[dayKey][category].map((place, index) => {
                                    if (place.name && place.name.startsWith('좌표')) {
                                        const placeName = `장소 ${index + 1}`;
                                        return { ...place, name: placeName };
                                    }
                                    return place;
                                });
                            }
                        }
                    }
                }
                saveSchedule();
            }
        }
    } catch {}

    // ✅ sessionStorage가 없거나 불완전하면 서버에서 로드
    if (!schedule || Object.keys(schedule).length===0 || !schedule[currentDay]) {
        await loadScheduleFromServer();
    }

    // ✅ 일정이 여전히 없으면 기본 일정 생성
    if (!schedule || Object.keys(schedule).length===0 || !schedule[currentDay]) {
        console.log('일정이 없어서 기본 일정 생성');
        schedule = { Day1: structuredClone(DEFAULT_DAY_SCHEDULE) };
        currentDay = 'Day1';
        saveSchedule();
    }

    // 카테고리 네비게이션 초기화
    updateCategoryDisplay();
    
    initDayMarkers();                 
    renderSchedule();                 
    
    // 초기화 시에는 모든 Day의 마커를 표시 (map 객체가 있을 때만)
    if (map) {
        Object.keys(dayMarkers).forEach(day => {
            if(dayMarkers[day]) {
                dayMarkers[day].forEach(marker => {
                    marker.setMap(map);
                });
                console.log(`${day}의 ${dayMarkers[day].length}개 마커 초기화 시 표시됨`);
            }
        });
    } else {
        console.warn('map 객체가 없어서 마커를 표시할 수 없습니다.');
    }
    
    // Polyline 렌더링 비활성화 - 마커만 표시
    // renderPolyline();
    
    // 지도 중심점 업데이트
    updateMapCenter();
}

// 기존 장소들을 재분류하는 함수
function recategorizeExistingPlaces() {
    console.log('기존 장소들 재분류 시작');
    
    // 모든 Day의 모든 카테고리에서 장소들을 수집
    const allPlaces = [];
    Object.keys(schedule).forEach(dayKey => {
        CATEGORIES.forEach(category => {
            if (schedule[dayKey][category]) {
                schedule[dayKey][category].forEach(place => {
                    allPlaces.push({
                        ...place,
                        day: dayKey,
                        originalCategory: category
                    });
                });
            }
        });
    });
    
    // 각 카테고리 초기화
    Object.keys(schedule).forEach(dayKey => {
        schedule[dayKey] = structuredClone(DEFAULT_DAY_SCHEDULE);
    });
    
    // 재분류
    allPlaces.forEach(place => {
        // 공통 유틸리티를 사용한 카테고리 분류
        const newCategory = Utils.categorizePlace(place.name);
        
        // 새로운 카테고리에 추가
        schedule[place.day][newCategory].push({
            name: place.name,
            address: place.address,
            lat: place.lat,
            lng: place.lng
        });
        
        // 카테고리가 변경된 경우 로그 출력
        if (place.originalCategory !== newCategory) {
            console.log(`재분류: ${place.name} (${place.originalCategory} → ${newCategory})`);
        }
    });
    
    // 변경사항 저장
    saveSchedule();
    
    // UI 업데이트
    if (typeof updateCategoryPlaces === 'function') {
        updateCategoryPlaces();
    }
    if (typeof renderSchedule === 'function') {
        renderSchedule();
    }
    
    console.log('기존 장소들 재분류 완료');
}

// 페이지 로드 시 초기화 실행
window.addEventListener('load', function() {
    // constants.js가 로드되지 않은 경우를 대비한 fallback
    if (typeof DEFAULT_DAY_SCHEDULE === 'undefined') {
        window.DEFAULT_DAY_SCHEDULE = { 숙소: [], 식당: [], 카페: [], 관광지: [], 기타: [] };
    }
    if (typeof Utils === 'undefined') {
        window.Utils = {
            categorizePlace: function(placeName, activity = '') {
                return '기타'; // fallback
            }
        };
    }
    
    // initializeMap() 호출 제거 - map.html의 kakao.maps.load()에서 처리
    console.log('DOM 로드 완료, 카카오맵 API 로드 대기 중...');
});
