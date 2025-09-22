// ================================ */
// 🔹 챗봇 페이지 JavaScript 기능들    */
// ================================ */

// ✅ CSRF 토큰 가져오기 함수 (Django 보안용)
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return decodeURIComponent(parts.pop().split(';').shift());
}
const CSRF_TOKEN = getCookie('csrftoken');  // Django가 발급한 csrftoken 쿠키 사용

// ✅ 마지막 여행 일정 데이터 (챗봇 응답을 저장해 두는 임시 변수)
let lastScheduleData = null;

// ✅ 지도 관련 변수들
let chatbotMap = null;
let chatbotMarkers = [];

// ✅ 지도 초기화 함수
function initializeChatbotMap() {
  if (chatbotMap) return; // 이미 초기화된 경우
  
  const mapContainer = document.getElementById('chatbot-map');
  if (!mapContainer) return;
  
  // 카카오 API가 로드되었는지 확인
  if (typeof kakao === 'undefined' || !kakao.maps) {
    console.error('카카오 지도 API가 로드되지 않았습니다.');
    return;
  }
  
  const options = {
    center: new kakao.maps.LatLng(37.5665, 126.9780), // 서울 중심
    level: 8
  };
  chatbotMap = new kakao.maps.Map(mapContainer, options);
}

// ✅ 지도에 마커 추가
function addMarkerToChatbotMap(lat, lng, title, address) {
  if (!chatbotMap) return;
  
  // 카카오 API가 로드되었는지 확인
  if (typeof kakao === 'undefined' || !kakao.maps) {
    console.error('카카오 지도 API가 로드되지 않았습니다.');
    return;
  }
  
  // 빨간색 핀 이미지 생성
  const imageSrc = 'data:image/svg+xml;base64,' + btoa(`
    <svg width="24" height="35" viewBox="0 0 24 35" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 0C5.373 0 0 5.373 0 12c0 7.5 12 23 12 23s12-15.5 12-23c0-6.627-5.373-12-12-12z" fill="#ff0000"/>
      <circle cx="12" cy="12" r="8" fill="#ffffff"/>
      <circle cx="12" cy="12" r="4" fill="#ff0000"/>
    </svg>
  `);
  
  const imageSize = new kakao.maps.Size(24, 35);
  const markerImage = new kakao.maps.MarkerImage(imageSrc, imageSize);
  
  const marker = new kakao.maps.Marker({
    map: chatbotMap,
    position: new kakao.maps.LatLng(parseFloat(lat), parseFloat(lng)),
    image: markerImage,
    title: title
  });
  
  // 마커에 주소 정보 저장
  marker.address = address || '주소 정보 없음';
  chatbotMarkers.push(marker);
}

// ✅ 지도 마커 지우기
function clearChatbotMarkers() {
  chatbotMarkers.forEach(marker => marker.setMap(null));
  chatbotMarkers = [];
}

// ✅ 추천 장소들을 지도에 표시
function showPlacesOnChatbotMap(places) {
  // 카카오 API가 로드되었는지 확인
  if (typeof kakao === 'undefined' || !kakao.maps) {
    console.error('카카오 지도 API가 로드되지 않았습니다.');
    return;
  }
  
  if (!chatbotMap) initializeChatbotMap();
  
  clearChatbotMarkers();
  
  if (!places || places.length === 0) return;
  
  const bounds = new kakao.maps.LatLngBounds();
  
  places.forEach(place => {
    if (place.lat && place.lng) {
      addMarkerToChatbotMap(place.lat, place.lng, place.name, place.address);
      bounds.extend(new kakao.maps.LatLng(place.lat, place.lng));
    }
  });
  
  // 지도 범위 조정
  if (chatbotMarkers.length > 0) {
    chatbotMap.setBounds(bounds);
  }
}

// ✅ 채팅창을 항상 맨 아래로 스크롤
function scrollToBottom() {
  const chatBox = document.getElementById("chat-messages");
  if (chatBox) {
    chatBox.scrollTop = chatBox.scrollHeight;
  }
}

// ✅ 메시지 전송 (사용자 입력 → Django chatbot_view POST 요청)
async function sendMessage(event) {
  event.preventDefault(); // form 기본 동작 방지
  const input  = document.getElementById("chat-input-box");
  const chatBox = document.getElementById("chat-messages");
  const userText = input.value;
  if (!userText.trim()) return; // 공백 입력 방지

  // 사용자 메시지 즉시 화면에 출력
  const now = new Date();
  const timeString = now.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });

  chatBox.insertAdjacentHTML('beforeend', `
    <div class="message user-message">
      ${userText}
      <div class="timestamp">${timeString}</div>
    </div>
  `);
  input.value = "";
  scrollToBottom();

  try {
    // Django 서버로 메시지 전송
    const response = await fetch("/chatbot/", {
      method: "POST",
      headers: { 
        "X-CSRFToken": CSRF_TOKEN,  // Django CSRF 보호
        "Content-Type": "application/x-www-form-urlencoded"
      },
      body: new URLSearchParams({ message: userText }) // 전달 데이터
    });

    if (!response.ok) throw new Error("네트워크 오류");
    const data = await response.json();

    // 로그인 필요 시 처리
    if (data.login_required) {
      if (confirm("로그인이 필요합니다. 로그인 하시겠습니까?")) {
        window.location.href = "/login/";
      }
      return;
    }

    // 일반 텍스트 응답 (Markdown 파싱 후 출력)
    if (!data.yt_html && data.reply) {
      const mdHtml = marked.parse(data.reply);
      const botWrapper = document.createElement("div");
      botWrapper.className = "bot-message-wrapper";
      const now2 = new Date();
      const timeString2 = now2.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });

      botWrapper.innerHTML = `
        <i class="fab fa-github-alt bot-floating-icon"></i>
        <div class="message bot-message">
          ${mdHtml}
          <div class="timestamp">${timeString2}</div>
        </div>
      `;
      chatBox.appendChild(botWrapper);
      convertYoutubeLinks(botWrapper); // botWrapper로 변경
      scrollToBottom();
    }

    // 유튜브 카드 응답
    if (data.yt_html) {
      const ytWrapper = document.createElement("div");
      ytWrapper.className = "bot-message-wrapper";
      const ytTime = new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });

      ytWrapper.innerHTML = `
        <i class="fab fa-github-alt bot-floating-icon"></i>
        <div class="message bot-message">
          <div class="intro-text"><b>${userText}</b> 관련 브이로그 추천 영상입니다 😊</div>
          ${data.yt_html}
          <div class="timestamp">${ytTime}</div>
        </div>
      `;

      chatBox.appendChild(ytWrapper);
      scrollToBottom();
    }


    // ✅ 일정 추천 요청 감지 (더 정확한 키워드 체크)
    const isScheduleRequest = /일정|짜줘|추천|계획|여행.*일정|여행.*계획|여행.*짜줘|여행.*추천|코스|여행코스|여행.*코스/i.test(userText);
    
    if (isScheduleRequest || data.save_button_enabled) {
      // JSON 데이터가 있는지 확인
      let jsonData = null;
      try {
        // 응답에서 JSON 부분 추출 시도
        if (data.reply && data.reply.includes('{') && data.reply.includes('}')) {
          const jsonMatch = data.reply.match(/\{[\s\S]*\}/);
          if (jsonMatch) {
            jsonData = JSON.parse(jsonMatch[0]);
          }
        }
      } catch (e) {
        console.log('JSON 파싱 실패, 텍스트 형태로 저장');
      }
      
      // 현재 세션 ID 가져오기
      const currentSessionId = document.querySelector('.history-item[data-id]')?.getAttribute('data-id');
      
      lastScheduleData = {
        title: userText,
        data: jsonData || {
          query: userText,
          schedule: data.reply,
          places: data.places || data.map || [],
          created_at: new Date().toISOString()
        },
        sessionId: currentSessionId  // 현재 세션 ID 저장
      };
      
      console.log('일정 추천 요청 감지 - lastScheduleData 설정:', lastScheduleData);
      
      // ✅ 버튼 컨테이너 표시
      const buttonContainer = document.getElementById("scheduleButtons");
      if (buttonContainer) {
        buttonContainer.style.display = "block";
      }
      
      // ✅ 개별 버튼들 활성화
      const saveBtn = document.getElementById("saveScheduleBtn");
      const mapBtn = document.getElementById("viewOnMapBtn");
      const showMapBtn = document.getElementById("showMapBtn");
      if (saveBtn) {
        saveBtn.disabled = false;
      }
      if (mapBtn) {
        mapBtn.disabled = false;
      }
      if (showMapBtn) {
        showMapBtn.disabled = false;
      }
      
      // ✅ 추천 장소가 있으면 지도에 표시 (카카오 API 로드 후)
      if (data.places && data.places.length > 0) {
        // 카카오 API가 로드되었는지 확인
        if (typeof kakao !== 'undefined' && kakao.maps) {
          showPlacesOnChatbotMap(data.places);
        } else {
          console.log('카카오 지도 API가 아직 로드되지 않음, 지도 보기 버튼을 눌러주세요');
        }
      }
    } else {
      // ✅ 일정 추천 요청이 아닌 경우 버튼 숨김
      const buttonContainer = document.getElementById("scheduleButtons");
      if (buttonContainer) {
        buttonContainer.style.display = "none";
      }
      
      // lastScheduleData 초기화
      lastScheduleData = null;
    }

  } catch (err) {
    console.error('메시지 전송 중 오류:', err);
    // 오류 메시지 제거 - 사용자에게 불필요한 오류 표시 방지
  }
}

// ✅ 일정 저장 기능 (서버에 일정 저장 API 호출)
async function saveSchedule() {
  if (!lastScheduleData) {
      alert("저장할 일정이 없습니다. 먼저 챗봇에게 일정을 받아보세요!");
      return;
  }
  this.disabled = true;
  
  try {
      // 현재 세션 ID 가져오기
      const currentSessionId = document.querySelector('.history-item[data-id]')?.getAttribute('data-id');
      
      const response = await fetch("/save_schedule/", {
          method: "POST",
          headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": CSRF_TOKEN
          },
          body: JSON.stringify({
              title: lastScheduleData.title || "새 여행 일정",
              data: lastScheduleData.data || {}, // 빈 객체라도 전달
              question: lastScheduleData.title,
              session_id: currentSessionId
          })
      });

      const data = await response.json();
      
      // 저장 실패 처리
      if (!response.ok) {
          if (response.status === 401) {
              if (confirm("로그인이 필요합니다. 로그인 페이지로 이동하시겠습니까?")) {
                  window.location.href = "/login/";
              }
              return;
          }
          throw new Error(data.error || "서버 응답 오류");
      }

      // 저장 성공 시 사이드바에 새 일정 추가
      if (data.success) {
          const historyList = document.getElementById("history-list");
          const emptyMessage = historyList.querySelector("li:not(.history-item)");
          if (emptyMessage) emptyMessage.remove();
          
          const newItem = document.createElement("li");
          newItem.className = "history-item";
          newItem.setAttribute("data-id", data.session_id); // 세션 ID 사용
          newItem.setAttribute("tabindex", "0");
          newItem.innerHTML = `
              <span class="history-title">${lastScheduleData.title}</span>
              <button class="delete-btn" onclick="deleteSession('${data.session_id}')" title="삭제">×</button>
          `;
          historyList.insertBefore(newItem, historyList.firstChild);
          
          // lastScheduleData에 저장된 일정 ID 추가
          lastScheduleData.scheduleId = data.id;
          lastScheduleData.sessionId = data.session_id;
          
          alert("일정이 성공적으로 저장되었습니다!");
          console.log('일정 저장 완료:', data);
      } else {
          alert(data.error || "일정 저장에 실패했습니다.");
          this.disabled = false;
      }
  } catch (err) {
      console.error("일정 저장 중 오류:", err);
      alert(err.message || "일정을 저장하는 중에 오류가 발생했습니다.");
      this.disabled = false;
  }
}

// ✅ 맵에서 보기 버튼 이벤트 리스너
async function viewOnMap() {
  console.log('맵 보기 버튼 클릭됨');
  console.log('현재 lastScheduleData:', lastScheduleData);
  
  if (!lastScheduleData) {
    console.log('lastScheduleData가 없음, 현재 세션에서 일정 데이터 찾기 시도');
    
    // 현재 세션 ID 가져오기
    const currentSessionId = document.querySelector('.history-item[data-id]')?.getAttribute('data-id');
    console.log('현재 세션 ID:', currentSessionId);
    
    if (currentSessionId) {
      try {
        // 세션에서 일정 데이터 가져오기
        const mapRes = await fetch(`/find_schedule_by_session/${currentSessionId}/`);
        if (mapRes.ok) {
          const mapData = await mapRes.json();
          console.log('세션 매핑 데이터:', mapData);
          
          if (mapData.schedule_id) {
            const schedRes = await fetch(`/get_schedule/${mapData.schedule_id}/`);
            if (schedRes.ok) {
              const schedData = await schedRes.json();
              console.log('서버에서 가져온 일정 데이터:', schedData);
              
              // lastScheduleData 설정
              let jsonData = schedData;
              if (typeof schedData === 'string') {
                try {
                  jsonData = JSON.parse(schedData);
                } catch (e) {
                  console.log('JSON 파싱 실패, 원본 데이터 사용');
                }
              }
              
              lastScheduleData = {
                title: schedData.title || "일정",
                data: jsonData
              };
              
              console.log('lastScheduleData 재설정됨:', lastScheduleData);
            }
          }
        }
      } catch (err) {
        console.error('세션에서 일정 데이터 가져오기 실패:', err);
      }
    }
    
    // 여전히 lastScheduleData가 없으면 에러
    if (!lastScheduleData) {
      alert("표시할 일정이 없습니다. 먼저 일정을 생성하거나 저장된 일정을 선택해주세요.");
      return;
    }
  }

  try {
    // lastScheduleData에 저장된 세션 ID와 일정 ID 우선 사용
    if (lastScheduleData && lastScheduleData.sessionId && lastScheduleData.scheduleId) {
      console.log('저장된 세션/일정 ID 사용:', lastScheduleData.sessionId, lastScheduleData.scheduleId);
      
      // 해당 일정 데이터를 sessionStorage에 저장
      sessionStorage.setItem('selected_schedule', JSON.stringify({ 
        id: lastScheduleData.scheduleId, 
        data: lastScheduleData.data 
      }));
      
      // 지도 페이지로 이동
      console.log('저장된 일정으로 맵 이동:', lastScheduleData.scheduleId);
      window.location.href = `/map/?schedule_id=${lastScheduleData.scheduleId}`;
      return;
    }
    
    // lastScheduleData에 세션/일정 ID가 없는 경우, 현재 세션에서 찾기
    const currentSessionId = document.querySelector('.history-item[data-id]')?.getAttribute('data-id');
    console.log('맵 보기용 세션 ID:', currentSessionId);
    
    if (currentSessionId) {
      // 기존 저장된 일정이 있는 경우
      const mapRes = await fetch(`/find_schedule_by_session/${currentSessionId}/`);
      if (mapRes.ok) {
        const mapData = await mapRes.json();
        console.log('세션 매핑 결과:', mapData);
        
        if (mapData.schedule_id) {
          // 일정 데이터를 sessionStorage에 저장
          const schedRes = await fetch(`/get_schedule/${mapData.schedule_id}/`);
          if (schedRes.ok) {
            const schedData = await schedRes.json();
            console.log('저장된 일정 데이터:', schedData);
            
            sessionStorage.setItem('selected_schedule', JSON.stringify({ 
              id: mapData.schedule_id, 
              data: schedData 
            }));
          }
          // 지도 페이지로 이동
          console.log('저장된 일정으로 맵 이동:', mapData.schedule_id);
          window.location.href = `/map/?schedule_id=${mapData.schedule_id}`;
          return;
        }
      }
    }
    
    // 저장된 일정이 없거나 새 일정인 경우, 현재 데이터를 직접 사용
    const tempId = 'temp_' + Date.now();
    console.log('임시 ID로 맵 보기:', tempId);
    console.log('전달할 데이터:', lastScheduleData.data);
    
    sessionStorage.setItem('selected_schedule', JSON.stringify({ 
      id: tempId, 
      data: lastScheduleData.data 
    }));
    
    // 지도 페이지로 이동 (임시 ID 사용)
    window.location.href = `/map/?schedule_id=${tempId}`;
    
  } catch (err) {
    console.error("맵 보기 중 오류:", err);
    alert("맵을 불러오는 중 오류가 발생했습니다.");
  }
}

// ✅ 유튜브 링크를 iframe 영상으로 변환
function convertYoutubeLinks(container) {
  container.querySelectorAll("a").forEach(a => {
    const url = a.href;
    if (url.includes("youtube.com/watch") || url.includes("youtu.be")) {
      // 링크에서 영상 ID 추출
      const videoId = url.split("v=")[1]?.split("&")[0] || url.split("/").pop();
      if (videoId) {
        a.outerHTML = `<iframe width="560" height="315"
          src="https://www.youtube.com/embed/${videoId}"
          frameborder="0" allowfullscreen></iframe>`;
      }
    } else {
      a.target = "_blank"; a.rel = "noopener";
    }
  });
}

// ✅ 대화 세션 삭제 요청
async function deleteSession(sessionId) {
  if (!confirm("이 대화를 정말 삭제하시겠습니까?")) return;
  try {
    const response = await fetch(`/delete_session/${sessionId}/`, {
      method: "POST",
      headers: { "X-CSRFToken": CSRF_TOKEN }
    });
    if (!response.ok) throw new Error("서버 응답 오류");
    const data = await response.json();
    if (data.success) {
      // 성공 시 목록에서 해당 아이템 제거
      const item = document.querySelector(`.history-item[data-id="${sessionId}"]`);
      if (item) item.remove();
    } else if (data.login_required) {
      window.location.href = "/login/";
    } else {
      alert(data.error || "삭제에 실패했습니다.");
    }
  } catch (err) {
    console.error("대화내역 삭제 중 오류:", err);
    alert("대화내역을 삭제하는 중에 오류가 발생했습니다.");
  }
}

// ✅ 사이드바 토글 (햄버거 버튼 클릭 시 열기/닫기)
function toggleSidebar() {
  const sidebar = document.getElementById("chat-sidebar");
  sidebar.classList.toggle("open");
}

// ✅ 과거 세션 클릭 시 해당 세션 불러오기
async function loadSession(sessionId) {
  try {
    // 1) 대화 메시지 로드
    const res = await fetch(`/load_session/${sessionId}/`);
    if (!res.ok) throw new Error("세션 불러오기 실패");
    const data = await res.json();

    // URL을 현재 세션으로 변경하여 대화를 이어갈 수 있도록 함
    const newUrl = `/?session_id=${sessionId}`;
    window.history.pushState({}, '', newUrl);

    const chatBox = document.getElementById("chat-messages");
    chatBox.innerHTML = "";
    data.messages.forEach(m => {
      const now = new Date(m.timestamp || Date.now());

      const dateString = now.toLocaleDateString("ko-KR", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit"
      }).replace(/\./g, ".").replace(/\s/g, "");

      const timeString = now.toLocaleTimeString("ko-KR", {
        hour: "2-digit",
        minute: "2-digit"
      });

      if (m.role === "assistant") {
        // 봇 메시지면 wrapper 만들고 아이콘과 메시지 따로 넣기
        const wrapper = document.createElement("div");
        wrapper.classList.add("bot-message-wrapper");

        const icon = document.createElement("i");
        icon.className = "fab fa-github-alt bot-floating-icon";

        const messageDiv = document.createElement("div");
        messageDiv.classList.add("message", "bot-message");
        messageDiv.id = `msg-${m.id}`;
        messageDiv.innerHTML = `
          ${m.content}
          <div class="timestamp">${dateString} ${timeString}</div>
        `;

        wrapper.appendChild(icon);
        wrapper.appendChild(messageDiv);
        chatBox.appendChild(wrapper);

      } else if (m.role === "user") {
        // 사용자 메시지는 기존 구조
        const messageDiv = document.createElement("div");
        messageDiv.classList.add("message", "user-message");
        messageDiv.id = `msg-${m.id}`;
        messageDiv.innerHTML = `
          ${m.content}
          <div class="timestamp">${dateString} ${timeString}</div>
        `;
        chatBox.appendChild(messageDiv);
      }
    });
    scrollToBottom();

    // 2) 세션 → 일정 매핑 조회 후 일정 데이터 준비
    try {
      const mapRes = await fetch(`/find_schedule_by_session/${sessionId}/`);
      if (mapRes.ok) {
        const mapData = await mapRes.json();
        if (mapData.schedule_id) {
        const sid = mapData.schedule_id;
        const schedRes = await fetch(`/get_schedule/${sid}/`);
        if (schedRes.ok) {
          const schedData = await schedRes.json();
          console.log('서버에서 받은 일정 데이터:', schedData);
          
          try {
            sessionStorage.setItem('selected_schedule', JSON.stringify({ id: sid, data: schedData }));
            
            // 일정 데이터를 lastScheduleData에 저장하여 맵 보기 버튼 활성화
            // JSON 구조가 있는지 확인하고 적절히 처리
            let jsonData = schedData;
            if (typeof schedData === 'string') {
              try {
                jsonData = JSON.parse(schedData);
                console.log('문자열 데이터를 JSON으로 파싱:', jsonData);
              } catch (e) {
                console.log('JSON 파싱 실패, 원본 데이터 사용');
              }
            }
            
            lastScheduleData = {
              title: schedData.title || "일정",
              data: jsonData,
              sessionId: sessionId,  // 현재 세션 ID 저장
              scheduleId: sid       // 일정 ID 저장
            };
            
            console.log('lastScheduleData 설정됨:', lastScheduleData);
            console.log('lastScheduleData.data 타입:', typeof lastScheduleData.data);
            console.log('lastScheduleData.data 내용:', lastScheduleData.data);
            console.log('현재 세션 ID:', sessionId);
            console.log('일정 ID:', sid);
            
            // ✅ 버튼 컨테이너 표시
            const buttonContainer = document.getElementById("scheduleButtons");
            if (buttonContainer) {
              buttonContainer.style.display = "block";
            }
            
            // 맵 보기 버튼 활성화
            document.getElementById("viewOnMapBtn").disabled = false;
            console.log('맵 보기 버튼 활성화됨');
            
            // 일정 저장 버튼은 비활성화 (이미 저장된 일정이므로)
            document.getElementById("saveScheduleBtn").disabled = true;
            
          } catch {}
        }
        } else {
          // 일정이 없는 경우
          console.log('이 세션에는 저장된 일정이 없음');
          lastScheduleData = null;
          
          // ✅ 버튼 컨테이너 숨김
          const buttonContainer = document.getElementById("scheduleButtons");
          if (buttonContainer) {
            buttonContainer.style.display = "none";
          }
        }
      } else {
        // 일정 조회 실패
        console.log('일정 조회 실패:', mapRes.status);
        lastScheduleData = null;
        
        // ✅ 버튼 컨테이너 숨김
        const buttonContainer = document.getElementById("scheduleButtons");
        if (buttonContainer) {
          buttonContainer.style.display = "none";
        }
      }
    } catch (error) {
      // API 호출 오류 (404 등)
      console.log('세션-일정 매핑 조회 중 오류:', error);
      lastScheduleData = null;
      
      // ✅ 버튼 컨테이너 숨김
      const buttonContainer = document.getElementById("scheduleButtons");
      if (buttonContainer) {
        buttonContainer.style.display = "none";
      }
    }
  } catch (err) {
    console.error("세션 로드/매핑 중 오류:", err);
    // alert 제거 - 404 오류는 정상적인 상황일 수 있음
  }
}

// ✅ 지도 보기 버튼 이벤트 리스너
function showMap() {
  const mapArea = document.getElementById("map-area");
  if (mapArea.style.display === "none") {
    mapArea.style.display = "block";
    
    // 카카오 API가 로드되었는지 확인
    if (typeof kakao !== 'undefined' && kakao.maps) {
      initializeChatbotMap();
      // 저장된 장소 데이터가 있으면 지도에 표시
      if (lastScheduleData && lastScheduleData.data.places) {
        showPlacesOnChatbotMap(lastScheduleData.data.places);
      }
    } else {
      console.error('카카오 지도 API가 로드되지 않았습니다.');
      alert('지도를 불러오는 중입니다. 잠시 후 다시 시도해주세요.');
    }
  }
}

// ✅ 지도 숨기기 버튼 이벤트 리스너
function hideMap() {
  document.getElementById("map-area").style.display = "none";
}

// ✅ 챗봇 초기화 함수 (홈 버튼 클릭 시 호출 - 채팅만 초기화)
function resetChatbot() {
  console.log('챗봇 초기화 시작 (채팅만 초기화)');
  
  // 1. 채팅 메시지 영역 초기화
  const chatBox = document.getElementById("chat-messages");
  if (chatBox) {
    chatBox.innerHTML = `
      <div class="bot-message-wrapper">
        <i class="fab fa-github-alt bot-floating-icon"></i>
        <div class="message bot-message">안녕하세요! 어디로 가실 예정인가요?</div>
      </div>
    `;
  }
  
  // 2. 일정 관련 데이터 초기화
  lastScheduleData = null;
  
  // 3. 일정 저장/맵 보기 버튼들 숨김 및 비활성화
  const buttonContainer = document.getElementById("scheduleButtons");
  if (buttonContainer) {
    buttonContainer.style.display = "none";
  }
  
  const saveBtn = document.getElementById("saveScheduleBtn");
  const mapBtn = document.getElementById("viewOnMapBtn");
  const showMapBtn = document.getElementById("showMapBtn");
  
  if (saveBtn) saveBtn.disabled = true;
  if (mapBtn) mapBtn.disabled = true;
  if (showMapBtn) showMapBtn.disabled = true;
  
  // 4. 지도 영역 숨김 및 마커 제거
  const mapArea = document.getElementById("map-area");
  if (mapArea) {
    mapArea.style.display = "none";
  }
  
  if (chatbotMap) {
    clearChatbotMarkers();
  }
  
  // 5. 입력창 초기화
  const inputBox = document.getElementById("chat-input-box");
  if (inputBox) {
    inputBox.value = "";
    inputBox.focus();
  }
  
  // 6. 사이드바에서 현재 선택된 항목 해제 (URL은 변경하지 않음)
  document.querySelectorAll('.history-item').forEach(item => {
    item.classList.remove('selected', 'active');
  });
  
  console.log('챗봇 초기화 완료 (현재 세션 유지)');
}

// ✅ 새 대화 세션 시작 함수
async function startNewSession() {
  try {
    console.log('새 대화 세션 시작');
    
    // 서버에 새 세션 생성 요청
    const response = await fetch('/start_new_session/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': CSRF_TOKEN
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      console.log('새 세션 생성됨:', data.session_id);
      
      // URL을 새 세션으로 업데이트
      const newUrl = `/?session_id=${data.session_id}`;
      window.history.pushState({}, '', newUrl);
      
      // 사이드바에 새 세션 추가 (선택적으로)
      if (data.session_id) {
        // 새 세션이 생성되었으므로 페이지 새로고침하여 사이드바 업데이트
        setTimeout(() => {
          window.location.href = `/?session_id=${data.session_id}`;
        }, 100);
      }
    } else {
      console.log('새 세션 생성 실패, 기본 초기화만 수행');
      resetChatbot();
    }
  } catch (error) {
    console.error('새 세션 생성 중 오류:', error);
    // 오류가 발생해도 기본 초기화는 수행
    resetChatbot();
  }
}

// ✅ 맵에서 보기 버튼 이벤트 리스너 (새 탭에서 지도 페이지 열기)
function viewOnMapNewTab() {
  console.clear()
  console.log('맵에서 보기 버튼 클릭됨');
  console.log('현재 lastScheduleData:', lastScheduleData);
  
  if (lastScheduleData && lastScheduleData.scheduleId) {
    // 저장된 일정이 있는 경우
    console.log('저장된 일정으로 맵 열기:', lastScheduleData.scheduleId);
    window.open(`/map/?schedule_id=${lastScheduleData.scheduleId}`, "_blank");
  } else if (lastScheduleData && lastScheduleData.data) {
    // 저장되지 않았지만 데이터가 있는 경우
    console.log('임시 데이터로 맵 열기');
    
    // sessionStorage에 임시 데이터 저장
    const tempScheduleData = {
      id: 'temp_' + Date.now(),
      data: lastScheduleData.data
    };
    sessionStorage.setItem('selected_schedule', JSON.stringify(tempScheduleData));
    console.log('sessionStorage에 저장된 데이터:', tempScheduleData);
    
    // 지도 페이지 열기
    window.open('/map/', "_blank");
  } else {
    alert("맵에서 열 일정이 없습니다. 먼저 챗봇에게 일정을 받아보세요!");
  }
}

// ================================ */
// 🔹 다중 선택 삭제 기능 */
// ================================ */

let isSelectMode = false;
let selectedSessions = new Set();

// 선택 모드 토글
function toggleSelectMode() {
  isSelectMode = !isSelectMode;
  const toggleBtn = document.getElementById('select-mode-toggle');
  const icon = toggleBtn.querySelector('i');  // ⬅️ 아이콘 선택
  const bulkControls = document.getElementById('bulk-delete-controls');
  const historyItems = document.querySelectorAll('.history-item');

  if (isSelectMode) {
    // 선택 모드 활성화
    icon.classList.remove('fa-check');
    icon.classList.add('fa-xmark');  // 선택된 상태 아이콘
    toggleBtn.classList.add('active');
    bulkControls.style.display = 'block';

    historyItems.forEach(item => {
      item.classList.add('select-mode');
      item.onclick = null; // 기존 클릭 이벤트 비활성화
    });
  } else {
    // 선택 모드 비활성화
    icon.classList.remove('fa-square-check');
    icon.classList.add('fa-check');  // 기본 상태 아이콘
    toggleBtn.classList.remove('active');
    bulkControls.style.display = 'none';

    // 모든 선택 해제
    selectedSessions.clear();
    updateSelectedCount();

    historyItems.forEach(item => {
      item.classList.remove('select-mode', 'selected');
      const checkbox = item.querySelector('.history-checkbox');
      if (checkbox) checkbox.checked = false;

      // 기존 클릭 이벤트 복원
      item.onclick = async (e) => {
        if (e.target.classList.contains('delete-btn')) return;
        const sessionId = item.getAttribute("data-id");
        await loadSession(sessionId);
      };
    });
  }
}

// 체크박스 변경 이벤트
function handleCheckboxChange(checkbox, sessionId) {
  if (checkbox.checked) {
    selectedSessions.add(sessionId);
    checkbox.closest('.history-item').classList.add('selected');
  } else {
    selectedSessions.delete(sessionId);
    checkbox.closest('.history-item').classList.remove('selected');
  }
  updateSelectedCount();
}

// 선택된 개수 업데이트
function updateSelectedCount() {
  const countElement = document.getElementById('selected-count');
  const deleteBtn = document.getElementById('bulk-delete-btn');
  
  countElement.textContent = `${selectedSessions.size}개 선택됨`;
  deleteBtn.disabled = selectedSessions.size === 0;
}

// 전체 선택/해제
function toggleSelectAll() {
  const checkboxes = document.querySelectorAll('.history-checkbox');
  const selectAllBtn = document.getElementById('select-all-btn');
  
  const allChecked = Array.from(checkboxes).every(cb => cb.checked);
  
  checkboxes.forEach(checkbox => {
    checkbox.checked = !allChecked;
    const sessionId = checkbox.value;
    
    if (!allChecked) {
      selectedSessions.add(sessionId);
      checkbox.closest('.history-item').classList.add('selected');
    } else {
      selectedSessions.delete(sessionId);
      checkbox.closest('.history-item').classList.remove('selected');
    }
  });
  
  selectAllBtn.textContent = allChecked ? '전체 선택' : '전체 해제';
  updateSelectedCount();
}

// 다중 삭제 실행
async function bulkDeleteSessions() {
  if (selectedSessions.size === 0) return;
  
  const confirmMessage = `선택한 ${selectedSessions.size}개의 일정을 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.`;
  if (!confirm(confirmMessage)) return;
  
  try {
    const response = await fetch('/api/bulk-delete-sessions/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': CSRF_TOKEN
      },
      body: JSON.stringify({
        session_ids: Array.from(selectedSessions)
      })
    });
    
    const result = await response.json();
    
    if (response.ok && result.success) {
      alert(result.message);
      // 페이지 새로고침하여 삭제된 항목 제거
      location.reload();
    } else {
      alert(`삭제 실패: ${result.error || '알 수 없는 오류가 발생했습니다.'}`);
    }
  } catch (error) {
    console.error('다중 삭제 오류:', error);
    alert('삭제 중 오류가 발생했습니다.');
  }
}

// ================================ */
// 🔹 이벤트 리스너 등록 (DOM 로드 후) */
// ================================ */
document.addEventListener('DOMContentLoaded', function() {
  // 메시지 전송 폼 이벤트 리스너
  document.getElementById('chat-form').addEventListener('submit', sendMessage);

  // 일정 저장 버튼 이벤트 리스너
  document.getElementById("saveScheduleBtn").addEventListener("click", saveSchedule);

  // 맵에서 보기 버튼 이벤트 리스너
  document.getElementById("viewOnMapBtn").addEventListener("click", viewOnMap);

  // 사이드바 토글 버튼 이벤트 리스너
  const toggleBtn = document.getElementById("toggle-history-btn");
  toggleBtn.addEventListener("click", toggleSidebar);

  // 과거 세션 클릭 이벤트 리스너
  document.querySelectorAll(".history-item").forEach(item => {
    item.addEventListener("click", async (e) => {
      if (e.target.classList.contains('delete-btn')) return; // 삭제 버튼은 무시
      const sessionId = item.getAttribute("data-id");
      await loadSession(sessionId);
    });
  });

  // 지도 보기 버튼 이벤트 리스너
  document.getElementById("showMapBtn").addEventListener("click", showMap);

  // 지도 숨기기 버튼 이벤트 리스너
  document.getElementById("hideMapBtn").addEventListener("click", hideMap);

  // 맵에서 보기 버튼 이벤트 리스너 (새 탭에서 지도 페이지 열기)
  document.getElementById("viewOnMapBtn").addEventListener("click", viewOnMapNewTab);
  
  // 다중 선택 관련 이벤트 리스너
  document.getElementById('select-mode-toggle').addEventListener('click', toggleSelectMode);
  document.getElementById('bulk-delete-btn').addEventListener('click', bulkDeleteSessions);
  document.getElementById('select-all-btn').addEventListener('click', toggleSelectAll);
  
  // 체크박스 이벤트 리스너 (동적으로 추가된 요소들을 위해 이벤트 위임 사용)
  document.addEventListener('change', function(e) {
    if (e.target.classList.contains('history-checkbox')) {
      const sessionId = e.target.value;
      handleCheckboxChange(e.target, sessionId);
    }
  });
  
  // ✅ 홈 버튼 클릭 이벤트 리스너 추가 (홈 버튼만 채팅 초기화)
  console.log('홈 버튼 이벤트 리스너 설정 중...');
  
  function handleHomeClick(e) {
    console.log('홈 버튼 클릭됨:', e.target);
    console.log('현재 경로:', window.location.pathname);
    
    // 홈 버튼 클릭 시 항상 채팅 초기화 (페이지 이동 없이)
    e.preventDefault(); // 기본 링크 동작 방지
    console.log('홈 버튼 클릭 - 채팅 초기화 실행');
    resetChatbot(); // 채팅만 초기화 (새 세션 생성 없이)
  }
  
  // home-reset-btn 클래스를 가진 홈 버튼만 찾기
  const homeButtons = document.querySelectorAll('.home-reset-btn');
  console.log('찾은 홈 버튼 개수:', homeButtons.length);
  
  homeButtons.forEach((button, index) => {
    console.log(`홈 버튼 ${index + 1}에 이벤트 리스너 추가:`, button);
    button.addEventListener('click', handleHomeClick);
  });
  
  // 추가적인 방법: 이벤트 위임 사용
  document.addEventListener('click', function(e) {
    if (e.target.classList.contains('home-reset-btn')) {
      console.log('이벤트 위임으로 홈 버튼 클릭 감지:', e.target);
      handleHomeClick(e);
    }
  });
});

// 🎨 스타일 옵션 토글
document.getElementById("options-toggle").addEventListener("click", () => {
  const panel = document.getElementById("options-panel");
  panel.style.display = panel.style.display === "flex" ? "none" : "flex";
});

// 🎨 폰트 변경
document.getElementById("font-select").addEventListener("change", (e) => {
  document.querySelector(".chat-messages").style.fontFamily = e.target.value;
  localStorage.setItem("chatFontFamily", e.target.value); // 저장
});

// 🎨 말풍선 색 변경
document.getElementById("bubble-color").addEventListener("input", (e) => {
  document.querySelectorAll(".message").forEach(msg => {
    msg.style.backgroundColor = e.target.value;
  });
  localStorage.setItem("chatBubbleColor", e.target.value); // 저장
});

// 🎨 글씨 색 변경
document.getElementById("font-color").addEventListener("input", (e) => {
  document.querySelectorAll(".message").forEach(msg => {
    msg.style.color = e.target.value;
  });
  localStorage.setItem("chatFontColor", e.target.value); // 저장
});

// 🎨 폰트 크기 변경
document.getElementById("font-size-range").addEventListener("input", function() {
  document.documentElement.style.setProperty("--chat-font-size", this.value + "px");
  localStorage.setItem("chatFontSize", this.value); // 저장
});

// 🎨 페이지 로드 시 저장된 값 복원
window.addEventListener("DOMContentLoaded", () => {
  const savedFont = localStorage.getItem("chatFontFamily");
  const savedBubbleColor = localStorage.getItem("chatBubbleColor");
  const savedFontColor = localStorage.getItem("chatFontColor");
  const savedFontSize = localStorage.getItem("chatFontSize");

  if (savedFont) {
    document.querySelector(".chat-messages").style.fontFamily = savedFont;
    document.getElementById("font-select").value = savedFont;
  }

  if (savedBubbleColor) {
    document.querySelectorAll(".message").forEach(msg => {
      msg.style.backgroundColor = savedBubbleColor;
    });
    document.getElementById("bubble-color").value = savedBubbleColor;
  }

  if (savedFontColor) {
    document.querySelectorAll(".message").forEach(msg => {
      msg.style.color = savedFontColor;
    });
    document.getElementById("font-color").value = savedFontColor;
  }

  if (savedFontSize) {
    document.documentElement.style.setProperty("--chat-font-size", savedFontSize + "px");
    document.getElementById("font-size-range").value = savedFontSize;
  }
});
