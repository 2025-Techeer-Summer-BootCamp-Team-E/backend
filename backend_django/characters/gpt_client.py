# characters/gpt_client.py
import os
import openai
import json
from django.conf import settings
import re 

# settings.py에서 OPENAI_API_KEY를 가져옴.
client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

'''GPT로 대본을 생성하는 함수'''
def generate_scenes_with_gpt(main_character, sub_characters, scene_count):
    # 주연 캐릭터 정보 분해
    main_name = main_character.characterName
    age = main_character.age
    gender = main_character.gender
    description = main_character.characterDescription

    # 책 정보
    book = main_character.book
    book_title = book.title
    book_content = book.content


    # 조연 캐릭터 정보 정리
    sub_info = ""
    for c in sub_characters:
        sub_info += f"- {c.characterName} ({c.age}살 {c.gender}): {c.characterDescription}\n"

    # 프롬프트 구성
    prompt = f"""
Here is the information about a novel:

[Novel]
Title: {book_title}
Content: {book_content}

[Main Character]
Name: {main_name}
Age: {age}
Gender: {gender}
Description: {description}

[Supporting Characters]
{sub_info if sub_info else "None"}

Instructions:

- Generate {scene_count} scenes.
- Each scene should be approximately 8 seconds long and include rich, compressed visual descriptions suitable for video generation.
- Output should be a JSON array with the following fields:

  - scene: scene number
  - background: visual description of location and time (in English)
  - mood: emotional atmosphere (in English)
  - style: visual style (e.g., cinematic, anime-style)
  - camera: camera movement or framing (e.g., tracking shot, zoom-in)
  - soundtrack: description of background music and sound effects (in English)
  - characters: list of characters, each with name, appearance, expression, and action (all in English)
  - lines: list of dialogues. Each line includes:
    - speaker: name
    - line_en: dialogue in English
    - line_ko: dialogue translated in Korean
  - rewriting_prompt: a single, richly detailed English description (At least 400 characters and less than 500 characters).  
  It should include:
  - the visual background (time, place, weather),
  - the main character’s appearance, expression, and action,
  - the mood or emotional tone,
  - the camera framing or motion (e.g., tracking shot, zoom-in),
  - and the soundtrack or ambient sounds.  
  This should be written as **one continuous, vivid sentence** for video generation.  

Output rules:
- Only return pure, valid JSON. No explanations or markdown.
- All strings must be enclosed in double quotes (").
- The JSON structure must be strictly correct.

Example format:

[
  {{
    "scene": 1,
    "background": "A misty fishing village at dawn",
    "mood": "Lonely and quiet",
    "style": "cinematic",
    "camera": "tracking shot from behind",
    "soundtrack": "soft piano melody with ambient sea waves",
    "characters": [
      {{
        "name": "Santiago",
        "appearance": "Slim, weathered face, old clothes",
        "expression": "determined gaze",
        "action": "loads supplies onto the boat"
      }}
    ],
    "lines": [
      {{
        "speaker": "Santiago",
        "line_en": "Once again, I head out to the sea.",
        "line_ko": "오늘도 나는 바다에 나간다."
      }}
    ],
    "rewriting_prompt": "A man loads a boat in a misty fishing village at dawn. Cinematic. Tracking shot. Ambient sea sound and soft piano."
  }}
]
"""


    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
    )

    content = response.choices[0].message.content
    print("🧠 대본 생성 GPT 응답:\n", content)  # 디버깅용 로그
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


'''GPT로 캐릭터 정보 생성 함수'''
def generate_characters_with_gpt(title: str, content: str):
    prompt = f"""
다음은 소설의 제목과 내용입니다.

제목: {title}
내용: {content}

요청 사항:
- 등장인물들을 JSON 배열 형식으로 출력해줘.
    - 각 인물은 다음 정보를 포함해야 해:
    - characterName: 이름
    - isMain: 주인공 여부 (true/false)
    - age: 나이 (정수)
    - gender: 성별 ("남성"/"여성" 등)
    - characterDescription: 인물의 성격, 역할, 외형 등을 설명하는 문장

- 설명 없이 JSON만 순수하게 출력해줘.
- 꼭 유효한 JSON 형식만 출력해줘.
- 문자열은 반드시 큰따옴표(")로 감싸줘.
- JSON 배열은 다음과 같은 형식이야:

예시:
[
  {{
    "characterName": "어린 왕자",
    "isMain": true,
    "age": 10,
    "gender": "남성",
    "characterDescription": "별을 여행하며 사람들과 교감하는 소년"
  }},
  ...
]
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    content = response.choices[0].message.content
    print("🧠 캐릭터 생성 GPT 응답:\n", content)
    return content
