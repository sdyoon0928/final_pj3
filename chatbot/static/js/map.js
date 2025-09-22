// ================================ */
// 🔹 지도 페이지 JavaScript 기능들    */
// ================================ */

// === 기본 데이터 (공통 상수 사용) ===
// constants.js에서 로드된 값들을 사용
let currentCategoryIndex = 0;

// ✅ constants.js 로드 확인 및 초기화
function initializeConstants() {
    if (typeof CATEGORIES === 'undefined' || typeof DEFAULT_DAY_SCHEDULE === 'undefined' || typeof Utils === 'undefined') {
        console.error('❌ constants.js가 제대로 로드되지 않았습니다!');
        console.log('CATEGORIES:', typeof CATEGORIES);
        console.log('DEFAULT_DAY_SCHEDULE:', typeof DEFAULT_DAY_SCHEDULE);
        console.log('Utils:', typeof Utils);
        
        // fallback 값들 정의
        if (typeof CATEGORIES === 'undefined') {
            window.CATEGORIES = ['숙소', '식당', '카페', '관광지', '기타'];
        }
        if (typeof DEFAULT_DAY_SCHEDULE === 'undefined') {
            window.DEFAULT_DAY_SCHEDULE = { 숙소: [], 식당: [], 카페: [], 관광지: [], 기타: [] };
        }
        if (typeof DAY_COLORS === 'undefined') {
            window.DAY_COLORS = { Day1: '#FF0000', Day2: '#007bff', Day3: '#00c853', Day4: '#ff6d00', Day5: '#6a1b9a' };
        }
        if (typeof Utils === 'undefined') {
            window.Utils = {
                validateCoordinate: function(placeName, lat, lng) {
                    const latNum = parseFloat(lat);
                    const lngNum = parseFloat(lng);
                    
                    if (isNaN(latNum) || isNaN(lngNum)) {
                        console.error(`❌ 숫자가 아닌 좌표: ${placeName}`);
                        return false;
                    }
                    
                    if (latNum < -90 || latNum > 90 || lngNum < -180 || lngNum > 180) {
                        console.error(`❌ 좌표 범위 초과: ${placeName} (${latNum}, ${lngNum})`);
                        return false;
                    }
                    
                    if (!(33 <= latNum && latNum <= 39) || !(124 <= lngNum && lngNum <= 132)) {
                        console.error(`❌ 한국 지역이 아닌 좌표: ${placeName} (${latNum}, ${lngNum})`);
                        return false;
                    }
                    
                    return true;
                },
                categorizePlace: function(placeName, activity = '') {
                    const name = placeName.toLowerCase();
                    const activityLower = activity.toLowerCase();
                    
                    const accommodationKeywords = ['숙소', '호텔', '펜션', '리조트', '모텔', '게스트하우스', '민박'];
                    const restaurantKeywords = ['식당', '맛집', '레스토랑', '막국수', '해장국', '국수', '냉면', '라면'];
                    const cafeKeywords = ['카페', '커피', '음료', '차', '티', '라떼', '아메리카노'];
                    const touristKeywords = ['공원', '박물관', '미술관', '관광지', '명소', '산', '해변', '바다'];
                    
                    if (accommodationKeywords.some(keyword => name.includes(keyword) || activityLower.includes(keyword))) {
                        return '숙소';
                    }
                    if (restaurantKeywords.some(keyword => name.includes(keyword) || activityLower.includes(keyword))) {
                        return '식당';
                    }
                    if (cafeKeywords.some(keyword => name.includes(keyword) || activityLower.includes(keyword))) {
                        return '카페';
                    }
                    if (touristKeywords.some(keyword => name.includes(keyword) || activityLower.includes(keyword))) {
                        return '관광지';
                    }
                    return '기타';
                }
            };
        }
        
        console.log('✅ fallback 상수들이 정의되었습니다.');
    } else {
        console.log('✅ constants.js가 성공적으로 로드되었습니다.');
    }
}

// 카테고리별 샘플 장소 데이터 (빈 배열로 초기화)
const samplePlaces = {
    '숙소': [],
    '식당': [],
    '카페': [],
    '관광지': [],
    '기타': []
};

function loadSchedule() {
    try {
        const raw = localStorage.getItem('schedule_v2');
        if (!raw) return { Day1: structuredClone(DEFAULT_DAY_SCHEDULE) };
        return JSON.parse(raw);
    } catch { return { Day1: structuredClone(DEFAULT_DAY_SCHEDULE) }; }
}

let schedule = loadSchedule();
let currentDay = Object.keys(schedule)[0];

// 일정 업데이트 시 길찾기 옵션도 함께 업데이트하는 함수
function updateScheduleAndRouteOptions(newSchedule) {
    if (newSchedule) {
        schedule = newSchedule;
        console.log('일정 업데이트됨:', schedule);
        
        // 길찾기 옵션 업데이트
        populateRouteSelects();
        console.log('일정 변경 후 길찾기 옵션 업데이트 완료');
    }
}

// === Day별 마커/Polyline 관리 ===
let dayMarkers = {};  
let polylines = {};
let currentInfoWindow = null; // 현재 열린 InfoWindow 관리   

// ✅ 좌표 검증 및 디버깅 함수
function validateCoordinate(placeName, lat, lng) {
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
    if (!(33 <= latNum <= 39) || !(124 <= lngNum <= 132)) {
        console.error(`❌ 한국 지역이 아닌 좌표: ${placeName} (${latNum}, ${lngNum})`);
        return false;
    }
    
    // 부산 지역 검사
    if (placeName.includes('부산')) {
        if (!(35.0 <= latNum <= 35.3) || !(128.8 <= lngNum <= 129.3)) {
            console.warn(`⚠️ 부산 지역이 아닌 좌표: ${placeName} (${latNum}, ${lngNum})`);
            console.warn(`부산 지역 좌표 범위: 위도 35.0-35.3, 경도 128.8-129.3`);
            return false;
        } else {
            console.log(`✅ 부산 지역 좌표 확인: ${placeName}`);
        }
    }
    
    // 해운대 지역 검사
    if (placeName.includes('해운대')) {
        if (!(35.15 <= latNum <= 35.17) || !(129.15 <= lngNum <= 129.18)) {
            console.warn(`⚠️ 해운대 지역이 아닌 좌표: ${placeName} (${latNum}, ${lngNum})`);
            console.warn(`해운대 지역 좌표 범위: 위도 35.15-35.17, 경도 129.15-129.18`);
            return false;
        } else {
            console.log(`✅ 해운대 지역 좌표 확인: ${placeName}`);
        }
    }
    
    // 경주 지역 검사
    if (placeName.includes('경주')) {
        if (!(35.8 <= latNum <= 35.9) || !(129.2 <= lngNum <= 129.3)) {
            console.warn(`⚠️ 경주 지역이 아닌 좌표: ${placeName} (${latNum}, ${lngNum})`);
            console.warn(`경주 지역 좌표 범위: 위도 35.8-35.9, 경도 129.2-129.3`);
            return false;
        } else {
            console.log(`✅ 경주 지역 좌표 확인: ${placeName}`);
        }
    }
    
    // 동궁과 월지 특별 검사
    if (placeName.includes('동궁과 월지') || placeName.includes('동궁과월지')) {
        // 동궁과 월지 정확한 좌표: 35.8345, 129.2199
        if (!(35.83 <= latNum <= 35.84) || !(129.21 <= lngNum <= 129.22)) {
            console.error(`❌ 동궁과 월지 좌표가 부정확: ${placeName} (${latNum}, ${lngNum})`);
            console.error(`정확한 동궁과 월지 좌표: 위도 35.8345, 경도 129.2199`);
            return false;
        } else {
            console.log(`✅ 동궁과 월지 정확한 좌표 확인: ${placeName}`);
        }
    }
    
    console.log(`✅ 좌표 검증 통과: ${placeName}`);
    return true;
}

// === 지도 중심점 업데이트 함수 ===
function updateMapCenter(targetDay = null) {
    console.log(`updateMapCenter(${targetDay}) 호출`);
    console.log('2. map', map);
    if (!map) {
        console.warn('지도가 초기화되지 않았습니다.');
        return;
    }
    
    let targetPlaces = [];
    
    if (targetDay && schedule[targetDay]) {
        // 특정 Day의 장소들만 가져오기
        Object.values(schedule[targetDay]).forEach(categoryPlaces => {
            targetPlaces.push(...categoryPlaces);
        });
        console.log(`${targetDay}의 장소들로 중심점 업데이트:`, targetPlaces);
    } else {
        // 모든 Day의 장소들 가져오기
        Object.values(schedule).forEach(dayData => {
            Object.values(dayData).forEach(categoryPlaces => {
                targetPlaces.push(...categoryPlaces);
            });
        });
        console.log(`모든 Day의 장소들로 중심점 업데이트:`, targetPlaces);
    }
    
    if (targetPlaces.length > 0) {
        // 장소들의 중심점 계산
        const avgLat = targetPlaces.reduce((sum, place) => sum + parseFloat(place.lat), 0) / targetPlaces.length;
        const avgLng = targetPlaces.reduce((sum, place) => sum + parseFloat(place.lng), 0) / targetPlaces.length;
        
        console.log(`지도 중심점 업데이트: (${avgLat}, ${avgLng}) - ${targetPlaces.length}개 장소`);
        map.setCenter(new kakao.maps.LatLng(avgLat, avgLng));
        
        // 장소들을 포함하도록 지도 레벨 조정
        if (targetPlaces.length > 1) {
            const bounds = new kakao.maps.LatLngBounds();
            targetPlaces.forEach(place => {
                bounds.extend(new kakao.maps.LatLng(parseFloat(place.lat), parseFloat(place.lng)));
            });
            map.setBounds(bounds);
        }
    }
}

// === 지도/로드뷰 초기화 ===
let map = null;
let ps = null;
let markers = [];

// 카카오맵 API 로드 완료 후 지도 초기화
function initializeMap() {
    console.log(`initializeMap() 호출`);
    try {
        console.log("----- 1 -----")
        const mapContainer = document.getElementById('map');
        if (!mapContainer) {
            console.error('지도 컨테이너를 찾을 수 없습니다.');
            return;
        }
        
        console.log("----- 2 -----")
        // 카카오맵 API가 로드되었는지 확인
        if (typeof kakao === 'undefined' || !kakao.maps) {
            console.error('카카오맵 API가 로드되지 않았습니다.');
            return;
        }
        
        console.log("----- 3 -----")
        map = new kakao.maps.Map(mapContainer, { 
            center: new kakao.maps.LatLng(35.1796, 129.0756), 
            level: 7 
        });
        console.log("----- 4 -----")
        console.log('map', map);
        
        ps = new kakao.maps.services.Places();
        markers = [];
        
        console.log('지도 초기화 완료');
        
        // 지도 초기화 후 기존 기능들 실행
        initializeMapFeatures();
        
    } catch (error) {
        console.error('지도 초기화 오류:', error);
    }
}

// 지도 초기화 후 실행할 기능들
function initializeMapFeatures() {
    console.log(`initializeMapFeatures() 호출`);
    // 기존 마커 초기화
    initDayMarkers();
    
    // 일정 렌더링
    renderSchedule();
    
    // 카테고리별 장소 목록 업데이트
    updateCategoryPlaces();
}

let roadview = null;
let roadviewClient = null;

// 로드뷰 초기화
function initializeRoadview() {
    try {
        if (typeof kakao !== 'undefined' && kakao.maps) {
            roadview = new kakao.maps.Roadview(document.getElementById('roadview'));
            roadviewClient = new kakao.maps.RoadviewClient();
            console.log('로드뷰 초기화 완료');
        }
    } catch (error) {
        console.error('로드뷰 초기화 오류:', error);
    }
}

function showRoadview(lat,lng){
    if (!roadview || !roadviewClient) {
        console.error('로드뷰가 초기화되지 않았습니다.');
        return;
    }
    
    const pos = new kakao.maps.LatLng(lat,lng);
    roadviewClient.getNearestPanoId(pos,50,(panoId)=>{
        if(!panoId) return;
        roadview.setPanoId(panoId,pos);
        roadviewContainer.classList.remove('collapsed');
    });
}

// === 사이드바 Day 관리 ===
const daySelector = document.getElementById('daySelector');
const sidebarDaySelector = document.getElementById('sidebarDaySelector');
const dayScheduleDiv = document.getElementById('day-schedule');

function renderDayOptions() {
    console.log(`renderDayOptions() 호출`);
    daySelector.innerHTML = '';
    Object.keys(schedule).forEach(day => {
        const opt = document.createElement('option');
        opt.value = day;
        opt.textContent = day;
        if (day===currentDay) opt.selected=true;
        daySelector.appendChild(opt);
        if(!dayMarkers[day]) dayMarkers[day]=[];
    });
}

// ✅ 사이드바 Day 선택기 업데이트 함수
function updateSidebarDaySelector() {
    console.log(`updateSidebarDaySelector() 호출`);
    if (!sidebarDaySelector) return;
    
    sidebarDaySelector.innerHTML = '';
    Object.keys(schedule).forEach(day => {
        const opt = document.createElement('option');
        opt.value = day;
        opt.textContent = day.replace('Day', 'Day ');
        if (day === currentDay) opt.selected = true;
        sidebarDaySelector.appendChild(opt);
    });
    
    console.log(`사이드바 Day 선택기 업데이트: ${currentDay} 선택됨`);
}

// ✅ 현재 Day의 카테고리별 장소 목록 업데이트 함수
function updateCategoryPlaces() {
    console.log(`카테고리별 장소 목록 업데이트: ${currentDay}`);
    
    // 현재 Day의 스케줄 데이터 가져오기
    const currentDaySchedule = schedule[currentDay] || DEFAULT_DAY_SCHEDULE;
    
    // 각 카테고리별로 장소 목록 업데이트
    CATEGORIES.forEach(category => {
        const categoryList = document.getElementById(`${category}-list`);
        if (!categoryList) return;
        
        const places = currentDaySchedule[category] || [];
        
        // 기존 내용 지우기
        categoryList.innerHTML = '';
        
        if (places.length === 0) {
            // 저장된 장소가 없는 경우
            categoryList.innerHTML = `<div class="no-places">저장된 ${category} 없음</div>`;
        } else {
            // 저장된 장소가 있는 경우
            places.forEach(place => {
                const placeElement = document.createElement('div');
                placeElement.className = 'place-item';
                placeElement.innerHTML = `
                    <span class="place-name">${place.name}</span>
                    <button class="remove-place" onclick="removePlaceFromCategory('${category}', '${place.name}')" title="삭제">×</button>
                `;
                categoryList.appendChild(placeElement);
            });
        }
        
        console.log(`${category} 카테고리: ${places.length}개 장소 표시`);
    });
}

// ✅ 카테고리에서 장소 삭제 함수
function removePlaceFromCategory(category, placeName) {
    console.log(`장소 삭제 시도: ${placeName} (${category})`);
    
    // 현재 Day의 해당 카테고리에서 장소 찾기
    const dayData = schedule[currentDay];
    if (!dayData || !dayData[category]) return;
    
    const placeIndex = dayData[category].findIndex(place => place.name === placeName);
    if (placeIndex === -1) {
        console.log(`삭제할 장소를 찾을 수 없음: ${placeName}`);
        return;
    }
    
    // 장소 삭제
    const removedPlace = dayData[category].splice(placeIndex, 1)[0];
    console.log(`장소 삭제됨: ${removedPlace.name}`);
    
    // 마커도 제거
    removeMarkerByName(placeName, currentDay);
    
    // 저장 및 렌더링
    saveSchedule();
    renderSchedule();
    updateCategoryPlaces();
    
    alert(`✅ [${category}]에서 "${placeName}"이(가) 삭제되었습니다!`);
}

// ✅ 이름으로 마커 제거 함수
function removeMarkerByName(placeName, day) {
    if (!dayMarkers[day]) return;
    
    const markerIndex = dayMarkers[day].findIndex(marker => marker.placeName === placeName);
    if (markerIndex !== -1) {
        dayMarkers[day][markerIndex].setMap(null);
        dayMarkers[day].splice(markerIndex, 1);
        console.log(`마커 삭제됨: ${placeName}`);
    }
}

function saveSchedule() { 
    console.log(`saveSchedule() 호출`);
    localStorage.setItem('schedule_v2', JSON.stringify(schedule)); 
}

// === 카테고리 네비게이션 함수들 ===
function updateCategoryDisplay() {
    console.log(`updateCategoryDisplay() 호출`);
    const currentCategory = CATEGORIES[currentCategoryIndex];
    document.getElementById('current-category').textContent = currentCategory;
    updatePlaceSelector();
}

function updatePlaceSelector() {
    const currentCategory = CATEGORIES[currentCategoryIndex];
    const selector = document.getElementById('place-selector');
    const addButton = document.getElementById('add-selected-place');
    
    // 기존 옵션 제거
    selector.innerHTML = '<option value="">장소를 선택하세요</option>';
    
    // 현재 카테고리의 장소들 추가
    const places = samplePlaces[currentCategory] || [];
    places.forEach((place, index) => {
        const option = document.createElement('option');
        option.value = index;
        option.textContent = place.name;
        selector.appendChild(option);
    });
    
    // 선택 변경 이벤트
    selector.addEventListener('change', function() {
        addButton.disabled = this.value === '';
    });
}

function prevCategory() {
    currentCategoryIndex = (currentCategoryIndex - 1 + CATEGORIES.length) % CATEGORIES.length;
    updateCategoryDisplay();
}

function nextCategory() {
    currentCategoryIndex = (currentCategoryIndex + 1) % CATEGORIES.length;
    updateCategoryDisplay();
}

function addSelectedPlace() {
    const currentCategory = CATEGORIES[currentCategoryIndex];
    const selector = document.getElementById('place-selector');
    const selectedIndex = selector.value;
    
    if (selectedIndex === '') return;
    
    const place = samplePlaces[currentCategory][selectedIndex];
    if (place) {
        // 현재 Day에 장소 추가
        const dayData = schedule[currentDay];
        if (dayData && dayData[currentCategory]) {
            dayData[currentCategory].push({
                name: place.name,
                address: '',
                lat: place.lat,
                lng: place.lng
            });
            
            // 마커 추가
            addMarker(place.lat, place.lng, place.name, '', true, currentDay);
            
            // 일정 저장 및 렌더링
            saveSchedule();
            renderSchedule();
            
            alert(`${place.name}이(가) ${currentCategory}에 추가되었습니다!`);
            
            // 현재 Day의 장소들로 지도 중심점 업데이트
            updateMapCenter(currentDay);
            
            // 선택 초기화
            selector.value = '';
            document.getElementById('add-selected-place').disabled = true;
        }
    }
}

// === 카테고리 토글 함수 ===
function toggleCategory(category) {
    const content = document.getElementById(`${category}-content`);
    const icon = content.previousElementSibling.querySelector('.toggle-icon');
    
    if (content.classList.contains('show')) {
        content.classList.remove('show');
        icon.style.transform = 'rotate(-90deg)';
    } else {
        content.classList.add('show');
        icon.style.transform = 'rotate(0deg)';
    }
}

// === 일정 렌더링 (카테고리별 토글 형식) ===
function renderSchedule(){
    console.log(`renderSchedule() 호출`);
    renderDayOptions();
    updateSidebarDaySelector(); // ✅ 사이드바 Day 선택기도 업데이트
    const dayData=schedule[currentDay];
    
    // 기존 day-schedule은 숨김
    if (dayScheduleDiv) {
        dayScheduleDiv.style.display = 'none';
    }
    
    // 카테고리별로 렌더링
    CATEGORIES.forEach(cat=>{
        const list = document.getElementById(`${cat}-list`);
        if (list) {
            list.innerHTML = '';
            
            if(!dayData[cat] || dayData[cat].length===0) {
                list.innerHTML=`<span class="text-muted" style="font-size: 12px; color: #6c757d;">저장된 ${cat} 없음</span>`;
            } else {
                dayData[cat].forEach((item,idx)=>{
                    const tag=document.createElement('div');
                    tag.className=`tag ${cat}`;
                    tag.innerHTML=`<span>${item.name}</span>`;
                    
                    // 장소 클릭 시 해당 위치로 이동
                    tag.addEventListener('click', (e) => {
                        // 삭제 버튼 클릭이 아닌 경우에만 실행
                        if (e.target.tagName !== 'BUTTON') {
                            if (item.lat && item.lng) {
                                const lat = parseFloat(item.lat);
                                const lng = parseFloat(item.lng);
                                
                                // 지도 중심을 해당 위치로 이동
                                map.setCenter(new kakao.maps.LatLng(lat, lng));
                                
                                // 해당 마커 찾아서 강조 표시
                                const targetMarker = dayMarkers[currentDay]?.find(marker => {
                                    const pos = marker.getPosition();
                                    return Math.abs(pos.getLat() - lat) < 0.0001 && Math.abs(pos.getLng() - lng) < 0.0001;
                                });
                                
                                if (targetMarker) {
                                    // 마커 라벨 표시 (setLabel 대신 label 옵션 사용)
                                    if (targetMarker.setLabel) {
                                        targetMarker.setLabel({
                                            content: `${idx + 1}`,
                                            color: '#fff',
                                            fontSize: '12px',
                                            fontWeight: 'bold',
                                            backgroundColor: DAY_COLORS[currentDay] || '#007bff',
                                            padding: '2px 5px',
                                            borderRadius: '50%'
                                        });
                                    } else {
                                        // setLabel이 없는 경우 InfoWindow로 대체
                                        const infowindow = new kakao.maps.InfoWindow({
                                            content: `<div style="background: ${DAY_COLORS[currentDay] || '#007bff'}; color: white; padding: 2px 5px; border-radius: 50%; font-size: 12px; font-weight: bold; text-align: center; min-width: 20px;">${idx + 1}</div>`,
                                            removable: false
                                        });
                                        infowindow.open(map, targetMarker);
                                        setTimeout(() => infowindow.close(), 2000);
                                    }
                                    
                                    // InfoWindow 열기
                                    const infowindow = new kakao.maps.InfoWindow({
                                        content: `<div style="padding:5px;"><strong>${item.name}</strong><br>${item.address || ''}</div>`
                                    });
                                    infowindow.open(map, targetMarker);
                                    
                                    // 로드뷰 표시
                                    showRoadview(lat, lng);
                                    
                                    console.log(`마커 라벨 표시: ${item.name} (${idx + 1})`);
                                } else {
                                    console.warn(`마커를 찾을 수 없습니다: ${item.name}`);
                                }
                            }
                        }
                    });
                    
                    const btn=document.createElement('button');
                    btn.textContent='×';
                    btn.addEventListener('click',(e)=>{
                        e.stopPropagation(); // 이벤트 버블링 방지
                        
                        // 삭제할 장소 정보 저장
                        const placeToDelete = dayData[cat][idx];
                        const placeName = placeToDelete.name;
                        const placeLat = parseFloat(placeToDelete.lat);
                        const placeLng = parseFloat(placeToDelete.lng);
                        
                        // 올바른 삭제 함수 호출
                        removeMarker(placeName, placeLat, placeLng);
                    });
                    tag.appendChild(btn);
                    list.appendChild(tag);
                });
            }
        }
    });
}

// === Day별 마커 초기화(저장된 일정 불러오기) ===
function initDayMarkers() {
    console.log(`initDayMarkers() 호출`);
    Object.keys(schedule).forEach(day=>{
        if(!dayMarkers[day]) dayMarkers[day]=[];
        const dayData=schedule[day];
        console.log(`${day} 데이터:`, dayData);
        CATEGORIES.forEach(cat=>{
            const items = dayData[cat] || [];
            console.log(`${day} ${cat} 장소 수:`, items.length);
            items.forEach((item, index) => {
                console.log(`${day} ${cat} ${index + 1}번째 장소:`, item);
                if (item.lat && item.lng && !isNaN(parseFloat(item.lat)) && !isNaN(parseFloat(item.lng))) {
                    // ✅ 좌표 검증 함수 사용
                    if (validateCoordinate(item.name, item.lat, item.lng)) {
                        const lat = parseFloat(item.lat);
                        const lng = parseFloat(item.lng);
                        addMarker(lat, lng, item.name, item.address || "", true, day);
                        console.log(`마커 추가 성공: ${item.name} (${lat}, ${lng})`);
                    } else {
                        console.warn(`좌표 검증 실패로 마커 추가 건너뜀: ${item.name}`);
                    }
                } else {
                    console.warn(`좌표가 없거나 유효하지 않은 장소:`, item);
                }
            });
        });
    });
    console.log('initDayMarkers 완료, dayMarkers:', dayMarkers);
    
    // 일정 로드 후 길찾기 옵션 업데이트
    populateRouteSelects();
    console.log('일정 로드 후 길찾기 옵션 업데이트 완료');
}

// === 마커 추가/삭제/Polyline 갱신 ===
function addMarker(lat,lng,name,address, setMapToMap=true, day=currentDay){
    console.log(`마커 추가 시도: ${name} (${lat}, ${lng}) - Day: ${day}, setMapToMap: ${setMapToMap}, currentDay: ${currentDay}`);
    
    if (!map) {
        console.warn('지도가 초기화되지 않았습니다. 마커 추가를 건너뜁니다.');
        return;
    }
    
    // ✅ 좌표 검증 함수 사용
    if (!validateCoordinate(name, lat, lng)) {
        console.error(`좌표 검증 실패로 마커 추가 중단: ${name}`);
        return;
    }
    
    const latNum = parseFloat(lat);
    const lngNum = parseFloat(lng);
    
    if(!dayMarkers[day]) dayMarkers[day]=[];
    const order=dayMarkers[day].length+1;
    
    try {
        const marker=new kakao.maps.Marker({
            map: map, // 항상 지도에 표시
            position:new kakao.maps.LatLng(latNum,lngNum),
            label:{content:`${order}`, color:'#fff', fontSize:'12px', fontWeight:'bold', backgroundColor:DAY_COLORS[day]||'#007bff', padding:'2px 5px', borderRadius:'50%'}
        });

        console.log(`마커 생성 성공:`, marker);

        const iwContent=document.createElement('div');
        iwContent.style.padding='10px';
        iwContent.style.minWidth='200px';
        iwContent.innerHTML=`
            <div style="border-bottom: 1px solid #eee; padding-bottom: 8px; margin-bottom: 8px;">
                <h6 style="margin: 0; color: #333; font-weight: bold;">${name||'장소'}</h6>
                <small style="color: #666;">${address||'주소 정보 없음'}</small>
            </div>
            <div style="margin-bottom: 8px;">
                <small style="color: #888;">좌표: ${latNum.toFixed(6)}, ${lngNum.toFixed(6)}</small>
            </div>
        `;
        const iwButtons=createMarkerButtons(name,address,latNum,lngNum,day);
        iwContent.appendChild(iwButtons);
        const infowindow=new kakao.maps.InfoWindow({content:iwContent});

        // 마커 클릭 이벤트 - InfoWindow 표시
        let isInfoWindowOpen = false;
        
        kakao.maps.event.addListener(marker,'click',()=>{
            console.log(`마커 클릭: ${name}`);
            
            if (isInfoWindowOpen && currentInfoWindow === infowindow) {
                // InfoWindow 닫기
                infowindow.close();
                currentInfoWindow = null;
                isInfoWindowOpen = false;
                console.log(`InfoWindow 닫힘: ${name}`);
            } else {
                // 기존 InfoWindow 닫기
                if (currentInfoWindow) {
                    currentInfoWindow.close();
                }
                
                // InfoWindow 열기
                infowindow.open(map, marker);
                currentInfoWindow = infowindow;
                showRoadview(latNum, lngNum);
                isInfoWindowOpen = true;
                console.log(`InfoWindow 열림: ${name}`);
            }
        });

        dayMarkers[day].push(marker);
        console.log(`${day}에 마커 추가됨, 총 ${dayMarkers[day].length}개`);
        
        if(day===currentDay) {
            // 현재 Day의 장소들로 지도 중심점 업데이트
            updateMapCenter(currentDay);
        }
    } catch (error) {
        console.error(`마커 생성 실패: ${name} (${latNum}, ${lngNum})`, error);
    }
}

// 특정 마커 삭제 함수 (참고 파일 방식)
function removeMarker(name, lat, lng) {
    // 해당 좌표와 제목이 일치하는 마커 찾기
    let deleted = false;
    let deletedFrom = [];
    
    // 모든 Day에서 해당 마커 찾아서 삭제
    Object.keys(dayMarkers).forEach(dayKey => {
        const markerIndex = dayMarkers[dayKey].findIndex(marker => {
            const position = marker.getPosition();
            const markerLat = position.getLat();
            const markerLng = position.getLng();
            return Math.abs(markerLat - lat) < 0.0001 && Math.abs(markerLng - lng) < 0.0001;
        });
        
        if (markerIndex !== -1) {
            // 마커를 지도에서 완전히 제거
            const markerToRemove = dayMarkers[dayKey][markerIndex];
            markerToRemove.setMap(null);
            dayMarkers[dayKey].splice(markerIndex, 1);
            deleted = true;
            deletedFrom.push(dayKey);
            console.log(`${dayKey}에서 마커 삭제됨: ${name}`);
            
            // 삭제 후 남은 마커들의 라벨 번호 재정렬
            dayMarkers[dayKey].forEach((marker, newIndex) => {
                marker.setLabel({
                    content: `${newIndex + 1}`,
                    color: '#fff',
                    fontSize: '12px',
                    fontWeight: 'bold',
                    backgroundColor: DAY_COLORS[dayKey] || '#007bff',
                    padding: '2px 5px',
                    borderRadius: '50%'
                });
            });
        }
    });
    
    // schedule 데이터에서도 삭제
    Object.keys(schedule).forEach(dayKey => {
        Object.keys(schedule[dayKey]).forEach(category => {
            const index = schedule[dayKey][category].findIndex(place => 
                place.name === name && 
                Math.abs(parseFloat(place.lat) - parseFloat(lat)) < 0.0001 && 
                Math.abs(parseFloat(place.lng) - parseFloat(lng)) < 0.0001
            );
            if (index !== -1) {
                schedule[dayKey][category].splice(index, 1);
                deletedFrom.push(`${dayKey} ${category}`);
                console.log(`${dayKey} ${category}에서 ${name} 삭제됨`);
            }
        });
    });
    
    if (deleted) {
        // InfoWindow 닫기 (삭제된 마커의 InfoWindow가 열려있을 수 있음)
        if (currentInfoWindow) {
            currentInfoWindow.close();
            currentInfoWindow = null;
            console.log('삭제 시 InfoWindow 닫힘');
        }
        
        saveSchedule();
        renderSchedule();
        
        // 모든 마커를 다시 렌더링하여 확실히 삭제된 마커 제거
        renderAllMarkers();
        
        updateMapCenter(currentDay);
        console.log(`${name}이(가) 삭제되었습니다! 삭제된 위치: ${deletedFrom.join(', ')}`);
    } else {
        console.warn('삭제할 마커를 찾을 수 없습니다.');
    }
}

function renderPolyline(){
    // Polyline 기능 비활성화 - 마커만 표시
    // if(polylines[currentDay]) polylines[currentDay].setMap(null);
    // if(!dayMarkers[currentDay] || dayMarkers[currentDay].length===0) return;
    // const path=dayMarkers[currentDay].map(m=>m.getPosition());
    // const polyline=new kakao.maps.Polyline({
    //     map:map,
    //     path:path,
    //     strokeWeight:3,
    //     strokeColor:DAY_COLORS[currentDay]||'#007bff',
    //     strokeOpacity:0.7,
    //     strokeStyle:'solid'
    // });
    // polylines[currentDay]=polyline;
}

function renderDayMarkers(){
    console.log(`renderDayMarkers() 호출`);
    if (!map) {
        console.warn('지도가 초기화되지 않았습니다. 마커 렌더링을 건너뜁니다.');
        return;
    }
    
    // 모든 마커를 지도에서 제거
    Object.values(dayMarkers).flat().forEach(m=>m.setMap(null));
    
    // 현재 Day의 마커들만 표시
    if(dayMarkers[currentDay]) {
        dayMarkers[currentDay].forEach(m=>m.setMap(map));
        console.log(`${currentDay}의 ${dayMarkers[currentDay].length}개 마커 표시됨`);
    }
    
    // Polyline 렌더링 비활성화 - 마커만 표시
    // renderPolyline();
}

// 모든 마커를 다시 렌더링하는 함수 (삭제 후 사용)
function renderAllMarkers(){
    console.log(`renderAllMarkers() 호출`);
    if (!map) {
        console.warn('지도가 초기화되지 않았습니다. 마커 재렌더링을 건너뜁니다.');
        return;
    }
    
    // 모든 마커를 지도에서 제거
    Object.values(dayMarkers).flat().forEach(m=>m.setMap(null));
    
    // 모든 Day의 마커들을 표시
    Object.keys(dayMarkers).forEach(dayKey => {
        if(dayMarkers[dayKey]) {
            dayMarkers[dayKey].forEach(m=>m.setMap(map));
        }
    });
    
    console.log(`모든 마커 재렌더링 완료`);
}

// === 검색 ===
const placeList = document.getElementById('place-list');
const searchInput = document.getElementById('search-input');
const searchButton = document.getElementById('search-button');

function clearMarkers(){ 
    // InfoWindow 닫기
    if (currentInfoWindow) {
        currentInfoWindow.close();
        currentInfoWindow = null;
    }
    
    markers.forEach(m=>m.setMap(null)); 
    markers=[]; 
}

function createMarkerButtons(name,address,lat,lng,day=currentDay){
    const div=document.createElement('div');
    div.style.marginTop='8px';
    div.style.display='flex';
    div.style.gap='6px';
    div.style.flexWrap='wrap';
    
    // 카테고리 선택 드롭다운
    const select=document.createElement('select');
    select.className='form-select form-select-sm';
    select.style.flex='1';
    select.style.fontSize='12px';
    CATEGORIES.forEach(c=>{
        const option=document.createElement('option');
        option.value=c; option.textContent=c;
        select.appendChild(option);
    });
    
    // 추가 버튼
    const addBtn=document.createElement('button');
    addBtn.textContent='추가';
    addBtn.className='btn btn-sm btn-primary';
    addBtn.style.fontSize='11px';
    addBtn.style.padding='4px 8px';
    addBtn.addEventListener('click',()=>{
        const category=select.value;
        
        // ✅ 좌표 검증 후 장소 추가
        if (validateCoordinate(name, lat, lng)) {
            console.log(`장소보관함에 추가 시도: ${name} (${lat}, ${lng}) - 카테고리: ${category}`);
            
            // 중복 체크
            const existingPlace = schedule[currentDay][category].find(place => 
                place.name === name && 
                Math.abs(parseFloat(place.lat) - parseFloat(lat)) < 0.0001 && 
                Math.abs(parseFloat(place.lng) - parseFloat(lng)) < 0.0001
            );
            
            if (existingPlace) {
                alert(`${name}은(는) 이미 ${category}에 추가되어 있습니다!`);
                return;
            }
            
            // 장소 추가
            schedule[currentDay][category].push({name,address,lat,lng});
            addMarker(lat,lng,name,address,true,currentDay);
            saveSchedule();
            renderSchedule();
            
            // 카테고리별 장소 목록 업데이트
            updateCategoryPlaces();
            
            console.log(`✅ 장소보관함에 성공적으로 추가됨: ${name} (${category})`);
            alert(`✅ [${category}]에 "${name}"이(가) 추가되었습니다!`);
            
            // 현재 Day의 장소들로 지도 중심점 업데이트
            updateMapCenter(currentDay);
            
            // 추가 후 마커 제거 (검색 마커만 제거)
            const currentMarker = markers.find(marker => {
                const pos = marker.getPosition();
                return Math.abs(pos.getLat() - lat) < 0.0001 && Math.abs(pos.getLng() - lng) < 0.0001;
            });
            if (currentMarker) {
                currentMarker.setMap(null);
                const markerIndex = markers.indexOf(currentMarker);
                if (markerIndex > -1) {
                    markers.splice(markerIndex, 1);
                }
            }
        } else {
            console.error(`좌표 검증 실패로 장소보관함 추가 실패: ${name}`);
            alert(`❌ ${name}의 좌표가 유효하지 않아 추가할 수 없습니다.\n좌표: (${lat}, ${lng})`);
        }
    });
    
    // 삭제 버튼
    const deleteBtn=document.createElement('button');
    deleteBtn.textContent='삭제';
    deleteBtn.className='btn btn-sm btn-danger';
    deleteBtn.style.fontSize='11px';
    deleteBtn.style.padding='4px 8px';
    deleteBtn.addEventListener('click',(e)=>{
        e.stopPropagation(); // 이벤트 버블링 방지
        
        // 확인 대화상자
        if (!confirm(`${name}을(를) 정말 삭제하시겠습니까?`)) {
            return;
        }
        
        // removeMarker 함수 호출
        removeMarker(name, lat, lng);
    });
    
    div.appendChild(select);
    div.appendChild(addBtn);
    div.appendChild(deleteBtn);
    return div;
}

// ✅ 검색 버튼 클릭 이벤트 리스너
searchButton.addEventListener('click', () => {
    console.log(`searchButton.addEventListener('click') 호출`);
    const query = searchInput.value.trim();
    if (!query) return alert('검색어를 입력하세요.');

    if (!map || !ps) {
        alert('지도가 아직 로드되지 않았습니다. 잠시 후 다시 시도해주세요.');
        return;
    }

    // 검색 결과 초기화
    placeList.innerHTML = '';
    clearMarkers();

    // 카카오맵 키워드 검색
    ps.keywordSearch(query, (data, status) => {
        if (status !== kakao.maps.services.Status.OK) {
            return alert('검색 결과가 없습니다.');
        }

        // ✅ 검색 결과 처리
        data.forEach(place => {
            const position = new kakao.maps.LatLng(place.y, place.x);

            // 🔹 1. 마커 생성
            const marker = new kakao.maps.Marker({
                map,
                position
            });
            markers.push(marker); // 검색 마커 배열에 추가

            // 🔹 2. InfoWindow 생성
            const iwContent = document.createElement('div');
            iwContent.className = 'place-item'; // 기존 스타일 재사용
            iwContent.innerHTML = `<span class="place-name">${place.place_name}</span>`;

            // 🔹 3. 기존 버튼 생성 함수 재사용
            iwContent.appendChild(createMarkerButtons(
                place.place_name,
                place.road_address_name || place.address_name,
                place.y,
                place.x
            ));

            const infowindow = new kakao.maps.InfoWindow({
                content: iwContent
            });

            // 🔹 4. 마커 클릭 시 InfoWindow 토글
            kakao.maps.event.addListener(marker, 'click', () => {
                toggleInfoWindow(marker, infowindow, place.y, place.x);
            });

            // 🔹 5. 검색 결과 리스트에 추가
            const li = document.createElement('li');
            li.className = 'place-item'; // 기존 스타일 재사용
            li.innerHTML = `<span class="place-name">${place.place_name}</span>`;
            li.appendChild(createMarkerButtons(
                place.place_name,
                place.road_address_name || place.address_name,
                place.y,
                place.x
            ));

            // 리스트 클릭 시 InfoWindow 열기
            li.addEventListener('click', () => {
                toggleInfoWindow(marker, infowindow, place.y, place.x);
            });

            placeList.appendChild(li);
        });

        // 검색 결과 첫 번째 장소로 지도 중심 이동
        if (data.length > 0) {
            map.setCenter(new kakao.maps.LatLng(data[0].y, data[0].x));
        }
    });
});

// ✅ InfoWindow 토글 함수
function toggleInfoWindow(marker, infowindow, lat, lng) {
    if (currentInfoWindow && currentInfoWindow === infowindow) {
        // InfoWindow 닫기
        currentInfoWindow.close();
        currentInfoWindow = null;
    } else {
        // 기존 InfoWindow 닫기
        if (currentInfoWindow) {
            currentInfoWindow.close();
        }

        // 새 InfoWindow 열기
        infowindow.open(map, marker);
        currentInfoWindow = infowindow;

        // 로드뷰 표시
        showRoadview(lat, lng);
    }
}

// ================================ */
// 🔹 길찾기 관련 함수들 */
// ================================ */

// 경로 선택 옵션 채우기
function populateRouteSelects() {
    const startSelect = document.getElementById('start-point');
    const endSelect = document.getElementById('end-point');
    const container = document.getElementById('waypoints-container');

    // 기존 옵션 제거
    startSelect.innerHTML = '<option value="">출발지 선택</option>';
    endSelect.innerHTML = '<option value="">도착지 선택</option>';
    container.innerHTML = '';

    const allPlaces = [];

    // 모든 Day의 모든 카테고리 합치기
    Object.keys(schedule).forEach(dayKey => {
        const dayData = schedule[dayKey];
        CATEGORIES.forEach(cat => {
            (dayData[cat] || []).forEach(p => {
                // Day 정보를 포함하여 장소 정보 저장
                allPlaces.push({
                    ...p,
                    day: dayKey
                });
            });
        });
    });

    allPlaces.forEach((p) => {
        const val = JSON.stringify({ name: p.name, lat: parseFloat(p.lat), lng: parseFloat(p.lng) });
        const displayText = `${p.name} (${p.day})`;
        
        const o1 = document.createElement('option');
        o1.value = val;
        o1.textContent = displayText;
        startSelect.appendChild(o1);

        const o2 = document.createElement('option');
        o2.value = val;
        o2.textContent = displayText;
        endSelect.appendChild(o2);
    });

    // 기본 경유지 select 하나 추가
    const wpSelect = document.createElement('select');
    wpSelect.className = 'form-select mb-2 waypoint-input';
    wpSelect.innerHTML = '<option value="">경유지 선택</option>';
    allPlaces.forEach((p) => {
        const opt = document.createElement('option');
        opt.value = JSON.stringify({ name: p.name, lat: parseFloat(p.lat), lng: parseFloat(p.lng) });
        opt.textContent = `${p.name} (${p.day})`;
        wpSelect.appendChild(opt);
    });
    container.appendChild(wpSelect);
}

// 경유지 추가
function addWaypointInput() {
    const container = document.getElementById('waypoints-container');
    const inputs = container.querySelectorAll('.waypoint-input');
    if(inputs.length >= 30) return alert('경유지는 최대 30개까지 추가 가능합니다.');
    
    const allPlaces = [];
    
    // 모든 Day의 모든 카테고리 합치기
    Object.keys(schedule).forEach(dayKey => {
        const dayData = schedule[dayKey];
        ['숙소','식당','카페','관광지','기타'].forEach(cat => {
            (dayData[cat] || []).forEach(p => {
                allPlaces.push({
                    ...p,
                    day: dayKey
                });
            });
        });
    });
    
    const input = document.createElement('select');
    input.className = 'form-select mb-2 waypoint-input';
    input.innerHTML = '<option value="">경유지 선택</option>';
    allPlaces.forEach((p) => {
        const opt = document.createElement('option');
        opt.value = JSON.stringify({ name: p.name, lat: parseFloat(p.lat), lng: parseFloat(p.lng) });
        opt.textContent = `${p.name} (${p.day})`;
        input.appendChild(opt);
    });
    container.appendChild(input);
}

// 길찾기 실행
async function getRoute() {
    console.log('길찾기 시작...');
    
    const startVal = document.getElementById('start-point').value;
    const endVal = document.getElementById('end-point').value;
    const transport = document.getElementById('transport-select').value;
    const wpVals = Array.from(document.querySelectorAll('.waypoint-input'))
                        .map(i => i.value && i.value.trim())
                        .filter(v => v);

    console.log('선택된 값들:', { startVal, endVal, transport, wpVals });

    if(!startVal || !endVal) {
        alert("출발지와 도착지는 필수입니다.");
        return;
    }

    let start, end;
    try { 
        start = JSON.parse(startVal); 
        console.log('출발지 파싱 성공:', start);
    } catch (e) { 
        console.error('출발지 파싱 오류:', e);
        alert('출발지 데이터가 올바르지 않습니다.');
        return;
    }
    
    try { 
        end = JSON.parse(endVal); 
        console.log('도착지 파싱 성공:', end);
    } catch (e) { 
        console.error('도착지 파싱 오류:', e);
        alert('도착지 데이터가 올바르지 않습니다.');
        return;
    }
    
    const waypointObjs = wpVals.map(v => { 
        try { 
            const parsed = JSON.parse(v);
            console.log('경유지 파싱 성공:', parsed);
            return parsed;
        } catch (e) { 
            console.error('경유지 파싱 오류:', e, v);
            return null; 
        } 
    }).filter(Boolean);
    
    console.log('최종 경유지 객체들:', waypointObjs);

    // 좌표 유효성 검사
    const startLat = parseFloat(start.lat);
    const startLng = parseFloat(start.lng);
    const endLat = parseFloat(end.lat);
    const endLng = parseFloat(end.lng);
    
    if (isNaN(startLat) || isNaN(startLng) || isNaN(endLat) || isNaN(endLng)) {
        alert('출발지 또는 도착지의 좌표가 유효하지 않습니다.');
        return;
    }
    
    if (startLat < -90 || startLat > 90 || startLng < -180 || startLng > 180 ||
        endLat < -90 || endLat > 90 || endLng < -180 || endLng > 180) {
        alert('출발지 또는 도착지의 좌표 범위가 올바르지 않습니다.');
        return;
    }

    const body = {
        origin: { x: startLng, y: startLat },
        destination: { x: endLng, y: endLat },
        waypoints: waypointObjs.map(w => ({ 
            x: parseFloat(w.lng), 
            y: parseFloat(w.lat) 
        })),
        priority: (transport || 'RECOMMEND'),
        mode: (transport || 'RECOMMEND')
    };
    
    console.log('API 요청 데이터:', body);

    try {
        console.log('API 호출 시작...');
        const res = await fetch('/api/get-route/', {
            method: 'POST',
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });
        
        console.log('API 응답 상태:', res.status);
        
        const text = await res.text();
        console.log('API 응답 텍스트:', text);
        
        let data;
        try { 
            data = JSON.parse(text); 
            console.log('API 응답 파싱 성공:', data);
        } catch (e) { 
            console.error('API 응답 파싱 실패:', e);
            data = { error: text }; 
        }
        
        if (!res.ok) {
            console.error('경로 API 오류 상태:', res.status, data);
            const msg = data && (data.error_message || data.error || JSON.stringify(data));
            alert('경로 API 호출 실패: ' + res.status + (msg ? ('\n' + msg) : ''));
            return;
        }
        console.log("경로 결과:", data);

        // 길찾기 탭을 강제로 활성화하여 패널이 항상 보이게 함
        if (typeof directionsTabBtn !== 'undefined') {
            directionsTabBtn.click();
        }
        document.getElementById('route-info').style.display = 'block';

        if(!data.routes || !Array.isArray(data.routes) || data.routes.length === 0) {
            console.error('경로 데이터가 없거나 형식이 올바르지 않습니다:', data);
            alert('경로를 찾을 수 없습니다. 다른 출발지나 도착지를 선택해보세요.');
            return;
        }

        // 카카오 API 오류 코드 처리
        if (data.routes[0] && data.routes[0].result_code && data.routes[0].result_code !== 0) {
            const errorCode = data.routes[0].result_code;
            const errorMsg = data.routes[0].result_msg || '알 수 없는 오류';
            
            console.error('카카오 길찾기 API 오류:', errorCode, errorMsg);
            
            let userMessage = '';
            switch (errorCode) {
                case 102:
                    userMessage = '시작 지점 주변에 도로가 없습니다. 다른 출발지를 선택해주세요.';
                    break;
                case 103:
                    userMessage = '도착 지점 주변에 도로가 없습니다. 다른 도착지를 선택해주세요.';
                    break;
                case 104:
                    userMessage = '경유지 주변에 도로가 없습니다. 다른 경유지를 선택해주세요.';
                    break;
                case 105:
                    userMessage = '출발지와 도착지가 동일합니다.';
                    break;
                case 106:
                    userMessage = '경로를 찾을 수 없습니다. 출발지와 도착지가 너무 가깝거나 연결되지 않습니다.';
                    break;
                default:
                    userMessage = `길찾기 오류 (${errorCode}): ${errorMsg}`;
            }
            
            alert(userMessage);
            return;
        }

        if(data.routes && data.routes[0]){
            const path=[];
            const routeSteps = []; // 각 구간별 정보 저장
            const provider = data.provider || 'kakao';
            const sections = data.routes[0].sections || [];
            
            console.log('경로 섹션 데이터:', sections);
            console.log('경로 데이터 구조:', data.routes[0]);
            
            // 섹션이 없는 경우 다른 방법으로 경로 정보 추출 시도
            if (sections.length === 0) {
                console.log('섹션이 없음, 대체 방법으로 경로 정보 추출 시도');
                
                // summary 정보가 있으면 사용
                const summary = data.routes[0].summary || {};
                if (summary.distance && summary.duration) {
                    routeSteps.push({
                        name: '전체 경로',
                        distance: summary.distance,
                        duration: summary.duration,
                        transport: '자동차'
                    });
                }
                
                // guides가 있으면 사용
                const guides = data.routes[0].guides || [];
                if (guides.length > 0) {
                    guides.forEach((guide, idx) => {
                        routeSteps.push({
                            name: guide.name || guide.instructions || `안내 ${idx+1}`,
                            distance: guide.distance || 0,
                            duration: guide.duration || 0,
                            transport: '자동차'
                        });
                    });
                }
                
                // vertexes가 있으면 경로 생성
                const vertexes = data.routes[0].vertexes || [];
                if (vertexes.length > 1) {
                    for (let i = 0; i < vertexes.length - 1; i += 2) {
                        const x = vertexes[i];
                        const y = vertexes[i+1];
                        path.push(new kakao.maps.LatLng(y, x));
                    }
                }
            } else {
                // 기존 섹션 처리 로직
                sections.forEach((section, idx)=>{
                    if (provider === 'google_transit') {
                        const secPath = section.path || [];
                        secPath.forEach(coord => {
                            path.push(new kakao.maps.LatLng(coord.y, coord.x));
                        });
                        routeSteps.push({
                            name: section.name || `구간 ${idx+1}`,
                            distance: section.distance,
                            duration: section.duration,
                            transport: section.transport || '대중교통'
                        });
                    } else {
                        // Kakao 자동차 경로: section.vertexes 또는 section.roads[].vertexes 중 하나로 제공됨
                        let added = false;
                        if (Array.isArray(section.vertexes) && section.vertexes.length > 1) {
                            const vertexes = section.vertexes;
                            for (let i = 0; i < vertexes.length - 1; i += 2) {
                                const x = vertexes[i];
                                const y = vertexes[i+1];
                                path.push(new kakao.maps.LatLng(y, x));
                            }
                            added = true;
                        }
                        if (!added && Array.isArray(section.roads)) {
                            section.roads.forEach(road => {
                                const vtx = road.vertexes || [];
                                for (let i = 0; i < vtx.length - 1; i += 2) {
                                    const x = vtx[i];
                                    const y = vtx[i+1];
                                    path.push(new kakao.maps.LatLng(y, x));
                                }
                            });
                            added = true;
                        }
                        // 가이드가 있으면 가이드 기반으로 단계 표시
                        if (section.guides && Array.isArray(section.guides) && section.guides.length > 0) {
                            section.guides.forEach((g, gi) => {
                                routeSteps.push({
                                    name: (g.name || g.instructions || `안내 ${gi+1}`),
                                    distance: g.distance || 0,
                                    duration: g.duration || 0,
                                    transport: '자동차'
                                });
                            });
                        } else {
                            routeSteps.push({
                                name: section.name || `구간 ${idx+1}`,
                                distance: section.distance,
                                duration: section.duration,
                                transport: '자동차'
                            });
                        }
                    }
                });
            }

            if(polylines['multiRoute']) polylines['multiRoute'].setMap(null);
            polylines['multiRoute']=new kakao.maps.Polyline({
                map: map,
                path: path,
                strokeWeight: 5,
                strokeColor: "#ff0000",
                strokeOpacity: 0.7,
                strokeStyle: "solid"
            });

            clearMarkers();
            const allPoints = [body.origin, ...body.waypoints, body.destination];
            allPoints.forEach((pos, idx)=>{
                let markerOptions = {
                    map,
                    position: new kakao.maps.LatLng(pos.y,pos.x)
                };
                
                // 출발지 (첫 번째 마커)
                if (idx === 0) {
                    markerOptions.label = { 
                        content: '출발', 
                        color: '#fff', 
                        fontSize: '12px', 
                        fontWeight: 'bold', 
                        backgroundColor: '#28a745', 
                        padding: '4px 8px', 
                        borderRadius: '4px' 
                    };
                    // 출발지 마커는 초록색으로 설정
                    markerOptions.image = new kakao.maps.MarkerImage(
                        'data:image/svg+xml;base64,' + btoa(`
                            <svg width="30" height="30" viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg">
                                <circle cx="15" cy="15" r="12" fill="#28a745" stroke="#fff" stroke-width="2"/>
                                <text x="15" y="20" text-anchor="middle" fill="white" font-size="10" font-weight="bold">S</text>
                            </svg>
                        `),
                        new kakao.maps.Size(30, 30),
                        { offset: new kakao.maps.Point(15, 15) }
                    );
                }
                // 도착지 (마지막 마커)
                else if (idx === allPoints.length - 1) {
                    markerOptions.label = { 
                        content: '도착', 
                        color: '#fff', 
                        fontSize: '12px', 
                        fontWeight: 'bold', 
                        backgroundColor: '#dc3545', 
                        padding: '4px 8px', 
                        borderRadius: '4px' 
                    };
                    // 도착지 마커는 빨간색으로 설정
                    markerOptions.image = new kakao.maps.MarkerImage(
                        'data:image/svg+xml;base64,' + btoa(`
                            <svg width="30" height="30" viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg">
                                <circle cx="15" cy="15" r="12" fill="#dc3545" stroke="#fff" stroke-width="2"/>
                                <text x="15" y="20" text-anchor="middle" fill="white" font-size="10" font-weight="bold">E</text>
                            </svg>
                        `),
                        new kakao.maps.Size(30, 30),
                        { offset: new kakao.maps.Point(15, 15) }
                    );
                }
                // 경유지
                else {
                    markerOptions.label = { 
                        content: `${idx}`, 
                        color: '#fff', 
                        fontSize: '12px', 
                        fontWeight: 'bold', 
                        backgroundColor: '#007bff', 
                        padding: '2px 5px', 
                        borderRadius: '50%' 
                    };
                }
                
                const marker = new kakao.maps.Marker(markerOptions);
                markers.push(marker);
            });

            // 사이드바에 경로 정보 표시
            const summaryDiv = document.getElementById('route-summary');
            const stepsUl = document.getElementById('route-steps');
            const summary = data.routes[0].summary || {};
            if (summary.distance != null && summary.duration != null) {
                summaryDiv.textContent = `총 거리: ${(summary.distance/1000).toFixed(1)}km, 총 소요 시간: ${Math.round(summary.duration/60)}분`;
            } else {
                summaryDiv.textContent = '요약 정보를 표시할 수 없습니다.';
            }

            stepsUl.innerHTML = '';
            if (routeSteps.length === 0 && sections.length > 0) {
                // guides가 없어도 섹션 단위로 간단 표시
                sections.forEach((section, idx) => {
                    const li = document.createElement('li');
                    const dist = (section.distance!=null) ? `${section.distance}m` : '-';
                    const dur = (section.duration!=null) ? `${section.duration}초` : '-';
                    li.textContent = `[자동차] ${section.name || `구간 ${idx+1}`} - 거리: ${dist}, 시간: ${dur}`;
                    stepsUl.appendChild(li);
                });
            }

            routeSteps.forEach((s, idx)=>{
                const li = document.createElement('li');
                const dist = (s.distance!=null) ? `${s.distance}m` : '-';
                const dur = (s.duration!=null) ? `${s.duration}초` : '-';
                li.textContent = `[${s.transport}] ${s.name} - 거리: ${dist}, 시간: ${dur}`;
                stepsUl.appendChild(li);
            });

            // 경로에 맞춰 지도 범위 조정
            if (path.length > 0) {
                const bounds = new kakao.maps.LatLngBounds();
                path.forEach(p => bounds.extend(p));
                map.setBounds(bounds);
            }
            // 경로 정보가 전혀 없으면 기본 정보 표시
            if (routeSteps.length === 0) {
                const summaryDiv = document.getElementById('route-summary');
                const stepsUl = document.getElementById('route-steps');
                
                // summary 정보가 있으면 사용
                const summary = data.routes[0].summary || {};
                if (summary.distance && summary.duration) {
                    summaryDiv.textContent = `총 거리: ${(summary.distance/1000).toFixed(1)}km, 총 소요 시간: ${Math.round(summary.duration/60)}분`;
                    
                    const li = document.createElement('li');
                    li.textContent = `[자동차] 전체 경로 - 거리: ${summary.distance}m, 시간: ${Math.round(summary.duration/60)}분`;
                    stepsUl.appendChild(li);
                } else {
                    summaryDiv.textContent = '경로 정보를 표시할 수 없습니다.';
                    
                    const li = document.createElement('li');
                    try {
                        li.textContent = '수신 데이터 요약: ' + Object.keys(data.routes[0]).join(', ');
                    } catch(e) {
                        li.textContent = '수신 데이터 구조를 확인할 수 없습니다.';
                    }
                    stepsUl.appendChild(li);
                }
            }
        }

    } catch(err){
        console.error('길찾기 오류:', err);
        console.error('오류 스택:', err.stack);
        
        let errorMessage = "경로 조회 중 오류가 발생했습니다.";
        
        if (err.name === 'TypeError' && err.message.includes('fetch')) {
            errorMessage = "서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.";
        } else if (err.name === 'SyntaxError') {
            errorMessage = "서버 응답 형식이 올바르지 않습니다.";
        } else if (err.message) {
            errorMessage = `오류: ${err.message}`;
        }
        
        alert(errorMessage);
        
        // 오류 발생 시 길찾기 탭을 닫기
        const searchTabBtn = document.getElementById('search-tab');
        if (searchTabBtn) {
            searchTabBtn.click();
        }
    }
}

// ================================ */
// 🔹 이벤트 리스너 등록 (DOM 로드 후) */
// ================================ */
// loadChatbotSchedule 함수는 map-server.js에서 정의됨

document.addEventListener('DOMContentLoaded', function() {
    console.log(`document.addEventListener('DOMContentLoaded') 호출`);
    // ✅ constants.js 로드 확인 및 초기화
    initializeConstants();
    
    console.log('DOM 로드 완료, 카카오맵 API 로드 대기 중...');
    
    // Day 추가 버튼
    document.getElementById('addDay').addEventListener('click',()=>{
        const newDay=`Day${Object.keys(schedule).length+1}`;
        schedule[newDay]=structuredClone(DEFAULT_DAY_SCHEDULE);
        currentDay=newDay;
        saveSchedule();
        renderDayOptions();
        renderSchedule();
        renderDayMarkers();
        
        // 새로 추가된 Day의 장소들로 지도 중심점 업데이트 (빈 Day이므로 기본 중심점 유지)
        updateMapCenter(currentDay);
    });

    // Day 선택 변경
    daySelector.addEventListener('change',()=>{
        currentDay=daySelector.value;
        renderSchedule();
        renderDayMarkers();
        
        // 선택된 Day의 장소들로 지도 중심점 업데이트
        updateMapCenter(currentDay);
        
        // 길찾기 옵션 업데이트
        populateRouteSelects();
    });

    // ✅ 사이드바 Day 선택기 이벤트 리스너
    if (sidebarDaySelector) {
        sidebarDaySelector.addEventListener('change', () => {
            const selectedDay = sidebarDaySelector.value;
            console.log(`사이드바에서 Day 변경: ${currentDay} → ${selectedDay}`);
            
            currentDay = selectedDay;
            
            // 카테고리별 장소 목록 업데이트
            updateCategoryPlaces();
            
            // 왼쪽 사이드바의 Day 선택기도 동기화
            if (daySelector) {
                daySelector.value = selectedDay;
            }
            
            // 일정 렌더링 및 마커 업데이트
            renderSchedule();
            renderDayMarkers();
            
            // 선택된 Day의 장소들로 지도 중심점 업데이트
            updateMapCenter(currentDay);
            
            // 길찾기 옵션 업데이트
            populateRouteSelects();
            
            console.log(`Day 변경 완료: ${currentDay}`);
        });
    }

    // 탭 전환
    const searchTabBtn = document.getElementById('search-tab');
    const directionsTabBtn = document.getElementById('directions-tab');
    const searchTabContent = document.getElementById('searchTabContent');
    const directionsTabContent = document.getElementById('directionsTabContent');

    searchTabBtn.addEventListener('click', ()=>{
        searchTabContent.classList.remove('d-none');
        directionsTabContent.classList.add('d-none');
        searchTabBtn.classList.add('active');
        directionsTabBtn.classList.remove('active');
    });

    directionsTabBtn.addEventListener('click', ()=>{
        searchTabContent.classList.add('d-none');
        directionsTabContent.classList.remove('d-none');
        directionsTabBtn.classList.add('active');
        searchTabBtn.classList.remove('active');
        
        // 길찾기 탭 활성화 시 최신 일정으로 옵션 업데이트
        console.log('길찾기 탭 활성화, 옵션 업데이트 중...');
        populateRouteSelects();
    });

    // 길찾기 관련 이벤트 리스너
    document.getElementById('add-waypoint').addEventListener('click', addWaypointInput);
    document.getElementById('get-route').addEventListener('click', getRoute);

    // 검색 버튼 이벤트는 위에서 이미 등록됨

    // 재분류 버튼
    document.getElementById('recategorizePlaces').addEventListener('click',()=>{
        if (confirm('모든 장소를 카테고리별로 재분류하시겠습니까?')) {
            recategorizeExistingPlaces();
            
            // 재분류 후 UI 업데이트
            updateCategoryPlaces();
            renderSchedule();
            renderDayMarkers();
            populateRouteSelects();
            
            alert('카테고리 재분류가 완료되었습니다!');
        }
    });

    // 초기화 버튼
    document.getElementById('resetSchedule').addEventListener('click',()=>{
        localStorage.removeItem('schedule_v2');
        schedule={Day1:structuredClone(DEFAULT_DAY_SCHEDULE)};
        currentDay='Day1';
        dayMarkers={}; polylines={};
        initDayMarkers();
        
        // 카테고리별 장소 목록 업데이트
        updateCategoryPlaces();
        renderSchedule();
        renderDayMarkers();
        populateRouteSelects();
    });

    // UI 토글
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('toggleBtn');
    toggleBtn.addEventListener('click', e=>{
        e.stopPropagation();
        sidebar.classList.toggle('collapsed');
    });

    // 왼쪽 사이드바 토글
    const leftSidebar = document.getElementById('left-sidebar');
    const toggleSearchBtn = document.getElementById('toggle-search');
    if (toggleSearchBtn) {
        toggleSearchBtn.addEventListener('click', () => {
            leftSidebar.classList.toggle('collapsed');
            if (leftSidebar.classList.contains('collapsed')) {
                toggleSearchBtn.textContent = '검색';
            } else {
                toggleSearchBtn.textContent = '접기';
            }
        });
    }

    // 카테고리 네비게이션 이벤트 리스너
    document.getElementById('prev-category').addEventListener('click', prevCategory);
    document.getElementById('next-category').addEventListener('click', nextCategory);
    document.getElementById('add-selected-place').addEventListener('click', addSelectedPlace);

    const roadviewContainer = document.getElementById('roadviewContainer');
    document.getElementById('toggleRoadview').addEventListener('click', ()=>{
        roadviewContainer.classList.toggle('collapsed');
    });

    // 페이지 로드 시 카테고리별 장소 목록 업데이트 (챗봇 데이터 로드 후)
    setTimeout(() => {
        updateCategoryPlaces();
    }, 1000);
    
    // 일정 데이터 변경 감지를 위한 주기적 체크 (1초마다)
    setInterval(() => {
        const currentSchedule = loadSchedule();
        const currentScheduleStr = JSON.stringify(currentSchedule);
        const lastScheduleStr = JSON.stringify(schedule);
        
        if (currentScheduleStr !== lastScheduleStr) {
            console.log('일정 데이터 변경 감지됨, 길찾기 옵션 업데이트');
            updateScheduleAndRouteOptions(currentSchedule);
        }
    }, 1000);
});
