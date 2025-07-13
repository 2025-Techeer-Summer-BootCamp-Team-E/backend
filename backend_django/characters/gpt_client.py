# characters/gpt_client.py
import os
import openai
import json
from django.conf import settings
import re 

# settings.py에서 OPENAI_API_KEY를 가져옴.
client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

# GPT-4o 모델로 대본 생성하기
def generate_scenes_with_gpt(main_character, sub_characters, scene_count):
    # 주연 캐릭터 정보 분해
    main_name = main_character.characterName
    age = main_character.age
    gender = main_character.gender
    description = main_character.characterDescription

    # 조연 캐릭터 정보 정리
    sub_info = ""
    for c in sub_characters:
        sub_info += f"- {c.characterName} ({c.age}살 {c.gender}): {c.characterDescription}\n"

    # 프롬프트 구성
    prompt = f"""
다음은 브이로그 영상의 주인공과 조연들입니다.

[주인공]
이름: {main_name}
나이: {age}
성별: {gender}
설명: {description}

[조연 등장인물]
{sub_info if sub_info else "없음"}

요청 사항:
- 총 {scene_count}개의 장면을 만들어줘.
- 각 장면은 약 10초 분량이며, 캐릭터들의 대사로만 구성해줘.
- 한 장면에는 주인공의 독백이거나, 주인공과 조연 간의 짧은 대화가 포함될 수 있어.
- 출력은 JSON 배열 형식으로 해줘.
- 꼭 유효한 JSON 형식만 출력해줘.
- 설명 없이 JSON만 순수하게 출력해줘. JSON 바깥에 문장은 넣지 마.
- 문자열은 반드시 큰따옴표(")로 감싸줘.
- JSON 형식이 틀리면 나는 에러가 나서 실패하니까, 꼭 문법을 맞춰줘.
- 각 장면은 다음과 같은 구조로 작성해줘:

형식 예시:
[
{{
    "scene": 1,
    "lines": [
        {{ "speaker": "산티아고", "line": "오늘도 나는 바다에 나간다." }},
        {{ "speaker": "마르틴", "line": "무사히 다녀오세요." }}
    ]
}},
...
]

각 장면은 위 형식처럼 JSON 배열로 묶어줘. 장면 번호는 "scene": 1, 2, 3... 으로 명시해줘.

"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    content = response.choices[0].message.content
    print("🧠 GPT 응답:\n", content)  # 디버깅용 로그
    return content


# GPT 응답 파싱
def parse_scene_list(raw_text):
    try:
        print("📥 raw_text:", raw_text)
        cleaned = clean_gpt_response(raw_text)
        print("🧼 cleaned:", cleaned)
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print("⚠️ JSON 디코딩 실패:", e)
        print("🧠 최종 파싱 대상:", cleaned)
        raise
    except ValueError as ve:
        print("⚠️ JSON 추출 실패:", ve)
        print("🧠 최종 파싱 대상:", cleaned)
        raise

# GPT 응답에서 JSON 배열만 추출하는 헬퍼 함수
def extract_json_array(text):
    match = re.search(r"\[\s*{.*?}\s*]", text, re.DOTALL)
    if not match:
        # 설명 텍스트를 제거하고 다시 시도
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1:
            return text[start:end+1]
        raise ValueError("⚠️ GPT 응답에서 JSON 배열을 찾을 수 없습니다.")
    return match.group(0)

def clean_gpt_response(text):
    """
    GPT 응답에서 ```json ... ``` 블록 제거
    """
    if "```json" in text:
        text = text.split("```json", 1)[1]
    if "```" in text:
        text = text.split("```", 1)[0]
    return text.strip()