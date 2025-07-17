# characters/gpt_client.py
import os
import openai
import json
import uuid
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
    sub_info = "\n".join([
    f"- {c.characterName} ({c.age}살 {c.gender}): {c.characterDescription}"
    for c in sub_characters
    ]) if sub_characters else "None"

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
{sub_info}

Instructions:

- The {scene_count} scenes must form a continuous and coherent story arc (beginning → middle → end).
- Do not generate isolated or disconnected scenes.
- Each scene should build logically upon the previous one.
- Ensure that the characters’ emotions and actions evolve naturally from scene to scene.
- Dialogue and character actions must reflect prior events and emotional states.

Scene format:

- sceneId: a sequential number starting from 1 (e.g., 1, 2, 3, ...)
- background: visual description of location and time (in English)
- mood: emotional atmosphere (in English)
- style: visual style (e.g., cinematic, anime-style)
- camera: camera movement or framing (e.g., tracking shot, zoom-in)
- soundtrack: description of background music and sound effects (in English)
- characters: list of 1 or 2 characters (each with name, appearance, expression, and action — all in English)
- lines: list of dialogues. Each line includes:
  - speaker: name
  - line_en: dialogue in English
  - line_ko: dialogue translated in Korean
- Only one character should speak per scene.
- The Korean dialogue (line_ko) must be short enough to be spoken in 3–4 seconds (about 10–15 characters).
- Use natural, simple expressions. Avoid long or complex sentences.

  - rewriting_prompt: a single, richly detailed English sentence (between 400 and 500 characters).
  - It must describe:
    - the visual background (time, place, weather),
    - the main character’s appearance, expression, and action,
    - the mood or emotional tone,
    - the camera framing or motion (e.g., tracking shot, zoom-in),
    - and the soundtrack or ambient sounds.
  - It must be written as **one continuous, vivid sentence**.

Output rules:
- Only return pure, valid JSON. No explanations or markdown.
- All strings must be enclosed in double quotes (").
- The JSON structure must be strictly correct.
- Each scene must include exactly 1 or 2 characters. Not all supporting characters need to appear in every scene.

Each scene should be a JSON object with the following keys:

- sceneId: a sequential number starting from 1
- background: string
- mood: string
- style: string
- camera: string
- soundtrack: string
- characters: list of character objects
    - name, appearance, expression, action
- lines: list of dialogue objects
    - speaker, line_en, line_ko
- rewriting_prompt: a richly detailed English sentence (400–500 characters)

Return a JSON array of scenes, with no extra explanation or markdown.
"""



    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
    )

    raw_text = response.choices[0].message.content
    print("🧠 대본 생성 GPT 응답:\n", raw_text)  # ✅ 이 줄이 여기로 정렬돼야 함
    return parse_scene_list(raw_text)


# GPT 응답 파싱
def parse_scene_list(raw_text):
    try:
        print(f"📥 씬 raw_text (type: {type(raw_text)}):", repr(raw_text)[:200] + "..." if len(str(raw_text)) > 200 else repr(raw_text))
        
        # 이미 파싱된 데이터인지 확인
        if isinstance(raw_text, list):
            print("✅ 이미 파싱된 씬 리스트입니다.")
            scenes = raw_text
            script_id = f"scpt-{uuid.uuid4().hex[:8]}"
        elif isinstance(raw_text, dict):
            print("✅ 이미 파싱된 딕셔너리입니다.")
            scenes = raw_text.get("scenes", [])
            script_id = raw_text.get("script_id", f"scpt-{uuid.uuid4().hex[:8]}")
        else:
            # 문자열인 경우 정상적으로 파싱
            cleaned = clean_gpt_response(raw_text)
            print("🧼 씬 cleaned:", cleaned[:200] + "..." if len(cleaned) > 200 else cleaned)

            parsed = json.loads(cleaned)
            
            # GPT가 배열을 반환하는지 객체를 반환하는지 확인
            if isinstance(parsed, list):
                # GPT가 배열을 반환한 경우 (일반적인 경우)
                scenes = parsed
                script_id = f"scpt-{uuid.uuid4().hex[:8]}"
            elif isinstance(parsed, dict):
                # GPT가 객체를 반환한 경우
                scenes = parsed.get("scenes", [])
                script_id = parsed.get("script_id", f"scpt-{uuid.uuid4().hex[:8]}")
            else:
                raise ValueError(f"Unexpected GPT response type: {type(parsed)}")

        # ✅ sceneId 및 rewriting_id 부여
        for idx, scene in enumerate(scenes):
            scene["sceneId"] = idx + 1
            scene["rewriting_id"] = f"{script_id}-scene-{idx + 1}"

        # 표준 형식으로 반환 (배열이든 객체든 동일한 형식)
        return {
            "script_id": script_id,
            "scenes": scenes
        }

    except json.JSONDecodeError as e:
        print("⚠️ 씬 JSON 디코딩 실패:", e)
        print("🧠 최종 파싱 대상:", cleaned if 'cleaned' in locals() else raw_text)
        raise
    except ValueError as ve:
        print("⚠️ 씬 파싱 실패:", ve)
        print("🧠 최종 파싱 대상:", cleaned if 'cleaned' in locals() else raw_text)
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
    # 입력값이 문자열이 아닌 경우 안전하게 처리
    if not isinstance(text, str):
        print(f"⚠️ clean_gpt_response에 문자열이 아닌 값이 전달됨: {type(text)} - {repr(text)}")
        if isinstance(text, (list, dict)):
            # 이미 파싱된 JSON 데이터인 경우 그대로 JSON 문자열로 변환
            import json
            return json.dumps(text, ensure_ascii=False)
        else:
            # 다른 타입인 경우 문자열로 변환
            text = str(text)
    
    if "```json" in text:
        text = text.split("```json", 1)[1]
    if "```" in text:
        text = text.split("```", 1)[0]
    return text.strip()

# 캐릭터 데이터 파싱 (배열 형태)
def parse_character_list(raw_text):
    try:
        print(f"📥 캐릭터 raw_text (type: {type(raw_text)}):", repr(raw_text)[:200] + "..." if len(str(raw_text)) > 200 else repr(raw_text))
        
        # 이미 파싱된 데이터인지 확인
        if isinstance(raw_text, list):
            print("✅ 이미 파싱된 캐릭터 리스트입니다.")
            return raw_text
        elif isinstance(raw_text, dict):
            print("✅ 이미 파싱된 딕셔너리입니다.")
            return raw_text.get('characters', raw_text)
        
        # 문자열인 경우 정상적으로 파싱
        cleaned = clean_gpt_response(raw_text)
        print("🧼 캐릭터 cleaned:", cleaned[:200] + "..." if len(cleaned) > 200 else cleaned)
        
        parsed = json.loads(cleaned)
        
        # GPT는 캐릭터 배열을 반환해야 함
        if not isinstance(parsed, list):
            raise ValueError(f"Expected character array but got: {type(parsed)}")
        
        print(f"✅ 파싱된 캐릭터 {len(parsed)}개")
        return parsed
        
    except json.JSONDecodeError as e:
        print("⚠️ 캐릭터 JSON 디코딩 실패:", e)
        print("🧠 최종 파싱 대상:", cleaned)
        raise
    except ValueError as ve:
        print("⚠️ 캐릭터 파싱 실패:", ve)
        print("🧠 최종 파싱 대상:", cleaned if 'cleaned' in locals() else raw_text)
        raise


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

    raw_text = response.choices[0].message.content
    character_data = parse_character_list(raw_text)
    print("🧠 캐릭터 생성 GPT 응답:\n", raw_text)
    return character_data
