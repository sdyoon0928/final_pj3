"""
프롬프트 템플릿 유틸리티 (교정된 버전)

- AI 기반 여행 목적지 감지
- 요약 코스(summary) 필드 강화
- 도구 활용 강제 규칙 추가
- 좌표/운영시간은 반드시 도구에서 가져오도록 명시
- 중복 장소 제거 지침 추가
- 대화 연속성(이전 히스토리 반영) 강화
"""

import re
from openai import OpenAI
from chatbot.models import ChatSession

client = OpenAI()

def detect_travel_destination(user_input: str, session_id: str = None, city_db: list[str] = None) -> str:
    """
    AI 기반 여행 목적지 추출 함수 (세션 기반 연속성 지원)
    - city_db가 있으면 DB와 매칭
    - 새로운 목적지가 감지되면 세션에 저장
    - 감지되지 않으면 세션의 마지막 목적지를 유지
    - 아무것도 없으면 fallback = "서울"
    """
    # 1️⃣ 먼저 DB 기반 매칭 시도
    tokens = re.findall(r"[가-힣]+", user_input)
    if city_db:
        for token in tokens:
            if token in city_db:
                # 세션에 목적지 저장
                if session_id:
                    try:
                        chat_session = ChatSession.objects.get(id=session_id)  # session_key → id 수정
                        chat_session.last_detected_destination = token
                        chat_session.save()
                    except ChatSession.DoesNotExist:
                        pass
                return token

    # 2️⃣ AI 기반 추출 시도
    prompt = f"""
    사용자 입력: "{user_input}"
    출력: 한국의 도시명 또는 지역명만 **딱 한 단어**로 적어.
    추가 설명, 문장, 따옴표 없이 단어 하나만 출력할 것.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "너는 한국 여행 목적지 추출 전문가다. 사용자의 입력에서 한국 도시/지역명을 가장 정확히 식별하고 단어 하나로만 답한다."
            },
            {"role": "user", "content": prompt}
        ]
    )
    destination = response.choices[0].message.content.strip()


    # 3️⃣ AI가 목적지를 제대로 반환했는지 확인
    if destination and destination not in ["", "None", "null"]:
        # 세션에 목적지 저장
        if session_id:
            try:
                chat_session = ChatSession.objects.get(id=session_id)  # session_key → id 수정
                chat_session.last_detected_destination = destination
                chat_session.save()
            except ChatSession.DoesNotExist:
                pass
        return destination

    # 4️⃣ 새로운 목적지가 감지되지 않으면, 세션의 마지막 값 유지
    if session_id:
        try:
            chat_session = ChatSession.objects.get(id=session_id)  # session_key → id 수정
            if chat_session.last_detected_destination:
                return chat_session.last_detected_destination
        except ChatSession.DoesNotExist:
            pass

    # 5️⃣ 마지막 값도 없다면 fallback = "서울"
    return "서울"


def get_common_tools_description(travel_destination="서울"):
    """공통 도구 설명 반환 (강화된/안전 버전)"""
    return f"""
## 🔧 사용 가능한 도구들 (기능에 맞는 도구만 사용하세요.)

1. **카카오지도검색**
   - 목적: {travel_destination} 지역 장소의 **정확한 위도/경도 좌표와 주소** 검색
   - 규칙:
     - 모든 좌표값(lat, lng)은 반드시 여기서 가져와야 함
     - 텍스트 기반 장소명만 사용하지 말고 반드시 좌표와 함께 출력
     - 화면에는 좌표값은 표시하지 말고, 주소만 표시하세요.
   - 출력 예시: `"경복궁" → {{ "lat": 37.5796, "lng": 126.9770, "address": "서울 종로구 사직로 161" }}`

2. **구글플레이스상세**
   - 목적: {travel_destination} 지역 장소의 **운영시간, 전화번호, 휴무일, 상세정보** 확인
   - 규칙:
     - 운영시간/휴무일은 반드시 이 도구에서 가져와야 함
     - 전화번호/상세정보도 필요 시 반드시 포함
   - 출력 예시: `"경복궁" → {{ "open_hours": "09:00-18:00", "closed": "화요일", "tel": "02-3700-3900" }}`

3. **유튜브검색**
   - 목적: {travel_destination} 지역의 **여행 브이로그 영상** 검색 (맛집·관광지 포함)
   - 규칙:
     - 반드시 여행지명 + 브이로그 키워드로 검색
     - 관광지/맛집과 직접적으로 관련된 영상만 제공
   - 출력 예시: `[{{ "title": "경주 여행 브이로그", "url": "https://youtu.be/xxxx", "channel": "여행유튜버" }}]`

4. **외부지식검색**
   - 목적: {travel_destination} 지역의 **역사, 문화, 배경지식, 지역 특징** 정보 검색
   - 규칙:
     - 장소/지역 맥락을 풍부하게 설명할 때 사용
     - 반드시 최신·정확한 정보를 우선 제공
   - 출력 예시: `"경주 불국사" → "통일신라시대의 대표 사찰로 UNESCO 세계문화유산에 등재됨"`

---

### ⚠️ 공통 주의사항
- 도구를 사용할 때는 **정확성 우선** (좌표·운영시간·휴무일은 반드시 출처 있는 값 사용).
- 출력 시 장소명만 나열하지 말고 **좌표/운영시간/배경지식**을 반드시 함께 제시.
- 모호한 답변 금지: 반드시 도구를 활용한 구체적 결과만 반환.
"""



def get_schedule_json_template(travel_destination="서울"):
    """일정 JSON 템플릿 반환 (summary 필드 강화)"""
    return f"""
```json
{{
  "schedule": {{
    "Day1": {{
      "오전활동": {{
        "장소": "{travel_destination} 지역 장소명",
        "시간": "09:00-11:00",
        "비용": "적절한 비용",
        "주의사항": "실용적인 주의사항",
        "좌표": {{"lat": 위도, "lng": 경도}},
        "주소": "{travel_destination} 지역 주소"
      }},
      "점심": {{
        "장소": "{travel_destination} 지역 맛집",
        "시간": "11:30-12:30",
        "비용": "적절한 비용",
        "주의사항": "실용적인 주의사항",
        "좌표": {{"lat": 위도, "lng": 경도}},
        "주소": "{travel_destination} 지역 주소"
      }},
      "오후활동": {{
        "장소": "{travel_destination} 지역 장소명",
        "시간": "13:00-17:00",
        "비용": "적절한 비용",
        "주의사항": "실용적인 주의사항",
        "좌표": {{"lat": 위도, "lng": 경도}},
        "주소": "{travel_destination} 지역 주소"
      }},
      "저녁": {{
        "장소": "{travel_destination} 지역 맛집",
        "시간": "18:00-19:30",
        "비용": "적절한 비용",
        "주의사항": "실용적인 주의사항",
        "좌표": {{"lat": 위도, "lng": 경도}},
        "주소": "{travel_destination} 지역 주소"
      }}
    }}
  }},
  "summary": "Day1: 오전활동장소 → 점심장소 → 오후활동장소 → 저녁장소, Day2: 오전활동장소 → 점심장소 → 오후활동장소 → 저녁장소 (모든 Day의 모든 활동을 반드시 포함할 것)"
}}
```"""


def get_common_checklist():
    """공통 체크리스트 반환 (도구 강제 + 유연한 fallback 포함)"""
    return """
## ⚠️ 최종 체크리스트

1. **도구 활용 (핵심 데이터)**
   - 장소명, 좌표(lat/lng), 주소, 운영시간, 휴무일, 전화번호는 반드시 카카오지도검색/구글플레이스상세 도구로만 가져올 것
   - 도구 결과가 없으면 "검색 결과 없음"이라고 명시
   - 임의로 새로운 상호명이나 장소명을 만들어내면 절대 안 됨 (허구 금지)

2. **유연한 Fallback (부가 설명)**
   - 도구에서 결과가 없을 경우:
     - "검색 결과 없음"을 출력
     - 대신 외부지식검색으로 일반적인 음식/지역 특징 설명은 가능
     - 단, 설명은 장소명이 아닌 "음식 종류/문화" 수준으로 제한
     - 예시: "전주는 비빔밥과 콩나물국밥으로 유명합니다."

3. **좌표 확인**
   - 모든 장소의 위도(lat)/경도(lng)는 반드시 카카오지도검색에서 가져올 것
   - 좌표 값이 null, 빈값이면 안 됨

4. **상세정보**
   - 운영시간, 휴무일, 전화번호는 반드시 구글플레이스상세에서 가져올 것
   - 주소 필드도 반드시 포함해야 함

5. **JSON 형식**
   - 반드시 유효한 JSON 객체만 출력
   - 응답은 ```json ... ``` 코드 블록 안에만 작성
   - JSON 외 텍스트/설명은 출력하지 않음

6. **중복 금지**
   - 같은 장소명/좌표는 2번 이상 등장 금지
   - Day별 일정에 동일 장소 반복 금지

7. **요약 코스(summary)**
   - summary 필드는 반드시 모든 활동을 누락 없이 포함
   - 형식: 'Day1: 오전활동장소 → 점심장소 → 오후활동장소 → 저녁장소'
   - 모든 Day의 모든 활동을 반드시 포함
   - 실제 도구 결과 기반 장소명을 사용 (허구 금지)

8. **연속성 유지**
   - 이전 대화에서 언급된 장소, 선호도, 요구사항 반드시 반영
   - 여행지와 무관한 장소 포함 금지

9. **실용성**
   - 각 활동에는 시간, 비용, 주의사항을 반드시 채움
   - 실제 여행에 도움이 되는 현실적인 값으로 설정
"""




def get_schedule_prompt(conversation_str, user_input, session_id=None, is_modification=False, existing_data_str="", context_info=None, city_db=None):
    """일정 관련 프롬프트 생성 (연속성 강화)"""
    # 세션 기반으로 목적지 감지
    travel_destination = detect_travel_destination(user_input, session_id, city_db)
    
    tools_desc = get_common_tools_description(travel_destination)
    json_template = get_schedule_json_template(travel_destination)
    checklist = get_common_checklist()
    
    # 컨텍스트 정보 포맷팅
    context_section = ""
    if context_info:
        mentioned_places = list(context_info.get('mentioned_places', [])) if context_info.get('mentioned_places') else []
        user_preferences = list(context_info.get('user_preferences', [])) if context_info.get('user_preferences') else []
        
        context_section = f"""
### 📋 추출된 대화 컨텍스트:
- **언급된 장소들**: {', '.join(mentioned_places) if mentioned_places else '없음'}
- **사용자 선호도**: {', '.join(user_preferences) if user_preferences else '없음'}
- **여행 기간**: {context_info.get('travel_duration', '미지정')}
- **이전 질문 수**: {len(context_info.get('previous_questions', []))}
- **일정 논의 여부**: {'있음' if context_info.get('has_schedule_discussion') else '없음'}
- **맛집 논의 여부**: {'있음' if context_info.get('has_food_discussion') else '없음'}
- **관광지 논의 여부**: {'있음' if context_info.get('has_tourist_discussion') else '없음'}
- **예산 논의 여부**: {'있음' if context_info.get('has_budget_discussion') else '없음'}
"""
    
    if is_modification:
        prompt_type = "일정 변경 요청"
        context_info_section = f"""
### 대화 히스토리 (최근 30개 메시지):
{conversation_str}

### 기존 일정 데이터:
{existing_data_str}

### 현재 사용자 요청사항:
{user_input}
{context_section}"""
        
        guidelines = f"""
1. **대화 히스토리 분석**: 사용자의 원래 여행 목적지와 일정을 정확히 파악
2. **일정 재생성**: 기존 일정의 여행지({travel_destination})를 유지하면서 전체 일정을 새로 생성
3. **요청사항 반영**: 사용자가 언급한 불만사항/변경 요청사항을 반영
4. **지역 일관성**: 기존 일정과 동일한 여행 기간과 지역 유지
5. **완전한 새로고침**: 새로운 장소나 활동으로 일정을 완전히 새로 생성
6. **연속성 유지**: 이전 대화에서 언급된 장소, 선호도, 요구사항을 반드시 고려
7. **중복 금지**: 같은 장소/좌표 반복 금지
8. **요약 코스 작성**: summary 필드에 Day별 핵심 코스를 반드시 요약"""
    else:
        prompt_type = "새 일정 생성 요청"
        context_info_section = f"""
### 대화 히스토리 (최근 30개 메시지):
{conversation_str}

### 현재 사용자 요청사항:
{user_input}
{context_section}"""
        
        guidelines = """
1. **대화 히스토리 분석**: 사용자의 의도와 선호도를 정확히 파악
2. **요구사항 반영**: 이전 대화에서 언급된 장소나 요구사항을 반영
3. **맞춤형 일정**: 사용자가 원하는 지역, 기간, 관심사를 고려하여 일정 생성
4. **실용성**: 실제 여행에 도움이 되는 구체적이고 실용적인 정보 제공, 시간/비용/주의사항 포함
5. **연속성**: 이전 질문들과의 연관성을 고려하여 일관된 답변 제공
6. **중복 금지**: 같은 장소/좌표 반복 금지
7. **요약 코스 작성**: summary 필드에 Day별 핵심 코스를 반드시 요약"""
    
    return f"""# 🎯 AI 여행 전문가 시스템 프롬프트 ({prompt_type})

## 📋 기본 정보
- **역할**: 15년 경력의 국내 여행 전문 AI 어시스턴트
- **현재 상황**: 사용자가 {"기존 일정을 변경해달라고" if is_modification else "새로운 일정 추천을"} 요청
- **감지된 여행 목적지**: {travel_destination}
- **중요도**: ⚠️ 이 정보를 절대적으로 따라야 함!

## 📚 컨텍스트 정보
{context_info_section}

## 🎯 핵심 지침
{guidelines}

## 🚨 절대 위반 금지 규칙
- **감지된 여행 목적지**: {travel_destination}
- **반드시 {travel_destination} 지역의 장소들만 사용**
- **절대로 다른 지역(서울, 제주도, 강릉 등) 장소 사용 금지**
- **모든 좌표는 카카오지도검색에서 가져와야 함**
- **모든 운영시간/휴무일은 구글플레이스상세에서 가져와야 함**
- **중복 금지: 같은 장소/좌표는 1번만 출력**
- **summary 필드 반드시 포함 (모든 Day의 모든 활동을 누락 없이 포함해야 함)**
- **🚨 CRITICAL: summary에는 오전활동, 점심, 오후활동, 저녁을 모두 포함할 것!**

{tools_desc}

## 📋 응답 형식 (JSON)

반드시 다음 JSON 형식으로만 응답 ({travel_destination} 지역만 사용):

{json_template}

{checklist}

**중요**: summary 필드에는 반드시 모든 Day의 모든 활동(오전활동, 점심, 오후활동, 저녁)을 순서대로 포함해야 함"""


def get_general_prompt(request_type, user_input, travel_destination=None, session_id=None, search_query="", city_db=None, conversation_str=""):
    """일반 요청 프롬프트 생성 (하드코딩 제거 + 유튜브/맛집 강화)"""
    # travel_destination이 없으면 세션 기반으로 감지
    if not travel_destination:
        travel_destination = detect_travel_destination(user_input, session_id, city_db)
    
    tools_desc = get_common_tools_description(travel_destination)
    
    if request_type == "맛집 추천":
        return f"""# 🍽️ {travel_destination} 맛집 추천

**대화 히스토리 (최근 30개 메시지):**
{conversation_str}

**요청**: {user_input}

{tools_desc}

**응답 형식**: {travel_destination} 지역 맛집명, 주소, 좌표(카카오지도검색), 운영시간/휴무일(구글플레이스상세), 전화번호, 유튜브 영상 링크
"""

    elif request_type == "브이로그 추천":
        return f"""# 🎥 {travel_destination} 브이로그 추천

**대화 히스토리 (최근 30개 메시지):**
{conversation_str}

**요청**: {user_input}

{tools_desc}

**응답 형식**: 유튜브 영상 링크, 채널명, 주요 장소와 좌표, 여행 팁
"""

    else:
        return f"""# 🌟 {travel_destination} 여행 정보

**대화 히스토리 (최근 30개 메시지):**
{conversation_str}

**요청**: {user_input}

{tools_desc}

## ⚠️ 출력 규칙
- 반드시 JSON 형식으로만 출력하세요.
- JSON 이외의 설명, 마크다운, 불필요한 텍스트는 절대 포함하지 마세요.
- 키 구조는 다음 예시를 따르세요:

{{
  "장소명": "홍천군",
  "주소": "대한민국 강원특별자치도 홍천군",
  "좌표": {{ "lat": 37.6899, "lng": 127.8880 }},
  "운영시간": "정보 없음",
  "전화번호": "없음",
  "비용": "N/A",
  "날씨": "맑음, 기온 23°C",   # ✅ 날씨 필드 추가
  "유튜브": "https://youtu.be/xxxx"
}}
"""



def get_conversation_context(session, conversation_history):
    """대화 컨텍스트 생성"""
    context = ""
    if session and session.title:
        context += f"세션 제목: {session.title}\n"
        context += f"대화 시작 시간: {session.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
    
    if conversation_history:
        context += "대화 히스토리:\n"
        context += "\n".join(conversation_history)
    else:
        context += "대화 히스토리가 없습니다."
    
    return context
