# characters/gemini_client.py
import os
import json
import uuid
from django.conf import settings
import re 
import boto3
import google.generativeai as genai
from books.models import Book

# Gemini API 설정
genai.configure(api_key=settings.GEMINI_API_KEY)

# S3 클라이언트 설정
s3 = boto3.client(
    's3',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_S3_REGION_NAME
)

# S3에서 PDF 파일을 가져오는 함수
def fetch_pdf_from_s3(book_id):
    """S3에서 book_id에 해당하는 PDF 파일을 가져옴"""
    try:
        # Book 모델에서 PDF URL 정보 가져오기
        book = Book.objects.get(id=book_id)
        pdf_url = book.pdf_url
        
        # S3 URL에서 파일 경로 추출
        # 예: https://bucket-name.s3.region.amazonaws.com/books/file.pdf
        if pdf_url:
            # URL에서 S3 키 추출 (개선된 안전한 방식)
            from books.s3_client import extract_s3_key_from_url
            s3_key = extract_s3_key_from_url(pdf_url)
            
            # S3에서 PDF 파일 다운로드
            response = s3.get_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=s3_key
            )
            
            pdf_content = response['Body'].read()
            return pdf_content
        else:
            raise ValueError(f"Book {book_id}에 PDF URL이 없습니다.")
            
    except Book.DoesNotExist:
        raise ValueError(f"Book {book_id}를 찾을 수 없습니다.")
    except Exception as e:
        raise ValueError(f"S3에서 PDF를 가져오는 중 오류 발생: {str(e)}")

# Gemini 2.5 Flash API를 사용하여 캐릭터 정보를 생성하는 함수
def generate_characters_with_gemini(book_id: str):
    """
    Gemini 2.5 Flash API를 사용하여 PDF로부터 캐릭터 정보를 생성
    """
    try:
        # S3에서 PDF 가져오기
        pdf_content = fetch_pdf_from_s3(book_id)
        
        # Gemini 모델 설정
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # 프롬프트 설정
        prompt = """
다음 PDF 문서를 분석하여 등장인물들의 정보를 추출해주세요.

⚠️ 중요
- 반드시 유효한 JSON 배열만 출력하세요. 설명이나 추가 텍스트는 절대 포함하지 마세요.
- 책에서 묘사된 내용을 변형하거나 제외하지 말고 추가해주세요. 책에 없는 내용은 창작하지 마세요.

요청 사항:
- 등장인물들을 JSON 배열 형식으로 출력해줘
- 각 인물은 다음 정보를 포함해야 해:
  - characterName: 이름 (문자열)
  - isMain: 주인공 여부 (true 또는 false)
  - age: 나이 (정수, 명시되지 않은 경우 추정)
  - gender: 성별 ("남성" 또는 "여성")
  - characterDescription: 인물 설명 (최대 50자, 문자열)
  - scenes: 등장 장면 정보 배열 (1~5개 생성)
    - scene_content: 장면 내용 (⚠️ 반드시 400~500자로 상세하게 작성, 문자열)
      * 등장인물의 행동, 대화, 감정, 주변 상황을 구체적으로 묘사
      * 장면의 배경, 분위기, 다른 인물과의 상호작용 포함
      * 단순한 1문장이 아닌 풍부한 서술로 작성
    - start_page: 시작 페이지 (정수)
    - finish_page: 끝 페이지 (정수)

JSON 형식 규칙:
- 반드시 큰따옴표(") 사용
- 마지막 항목 뒤에 쉼표(,) 사용 금지
- 모든 문자열에서 줄바꿈은 \\n으로 이스케이프
- 각 캐릭터마다 1~5개의 scene 포함 (다양하게)
- scene_content는 반드시 400~500자의 상세한 묘사로 작성
- 정확히 다음 형식으로만 출력:

[
  {{
    "characterName": "홍길동",
    "isMain": true,
    "age": 25,
    "gender": "남성",
    "characterDescription": "의적으로 활동하며 백성들을 도와주는 정의로운 인물",
    "scenes": [
      {{
        "scene_content": "홍길동이 어둠 속에서 탐관오리의 저택에 침입하는 장면이다. 달빛이 희미하게 비치는 가운데, 그는 검은 의복을 입고 담장을 넘어든다. 저택 안에서는 탐관오리가 백성들의 세금을 횡령하며 호화로운 잔치를 벌이고 있다. 홍길동은 조용히 기와지붕 위를 이동하며 창문 너머로 그 광경을 지켜본다. 그의 눈빛에는 분노와 정의감이 타오르고 있다. 마침내 적절한 순간을 포착한 그는 창문을 열고 방 안으로 뛰어든다. '탐관오리여, 네 죄를 알겠느냐!' 홍길동의 외침이 저택 전체에 울려 퍼지며, 놀란 탐관오리와 하인들이 벌벌 떨기 시작한다.",
        "start_page": 15,
        "finish_page": 18
      }}
    ]
  }}
]

⚠️ JSON 형식 중요사항:
- 모든 문자열 값에서 큰따옴표(")는 반드시 \"로 이스케이프하세요
- 예: "그가 \"안녕하세요\"라고 말했다"
- 작은따옴표(')는 사용하지 마세요
- 줄바꿈은 \\n으로 표현하세요

⚠️ 다시 한번 강조: 오직 JSON 배열만 출력하세요. 다른 텍스트는 일절 포함하지 마세요.
"""
        
        # PDF 콘텐츠와 프롬프트를 함께 전송
        response = model.generate_content([
            prompt,
            {"mime_type": "application/pdf", "data": pdf_content}
        ])
        
        raw_text = response.text
        print("🧠 캐릭터 생성 Gemini 응답:\n", raw_text)
        
        # 응답 파싱
        character_data = parse_character_list(raw_text)
        return character_data
        
    except Exception as e:
        print(f"⚠️ Gemini API 호출 중 오류 발생: {str(e)}")
        raise

def clean_gemini_response(text):
    """
    GPT/Gemini 응답에서 ```json ... ``` 블록 제거
    """
    # 입력값이 문자열이 아닌 경우 안전하게 처리
    if not isinstance(text, str):
        print(f"⚠️ clean_gemini_response에 문자열이 아닌 값이 전달됨: {type(text)} - {repr(text)}")
        if isinstance(text, (list, dict)):
            # 이미 파싱된 JSON 데이터인 경우 그대로 JSON 문자열로 변환
            return json.dumps(text, ensure_ascii=False)
        else:
            # 다른 타입인 경우 문자열로 변환
            text = str(text)
    
    if "```json" in text:
        text = text.split("```json", 1)[1]
    if "```" in text:
        text = text.split("```", 1)[0]
    return text.strip()

def extract_json_with_regex(text):
    """
    정규식을 사용한 강제 JSON 추출 (최후 수단)
    """
    import re
    
    # 배열 패턴 찾기
    array_pattern = r'\[\s*\{.*?\}\s*\]'
    matches = re.findall(array_pattern, text, re.DOTALL)
    
    if matches:
        # 가장 긴 매치를 선택 (가장 완전한 JSON일 가능성)
        best_match = max(matches, key=len)
        return json.loads(best_match)
    
    raise ValueError("정규식으로도 유효한 JSON을 찾을 수 없습니다")

# 캐릭터 데이터 파싱 (배열 형태)
def parse_character_list(raw_text):
    try:
        print(f"📥 캐릭터 raw_text (type: {type(raw_text)}):", repr(raw_text)[:500] + "..." if len(str(raw_text)) > 500 else repr(raw_text))
        
        # 이미 파싱된 데이터인지 확인
        if isinstance(raw_text, list):
            print("✅ 이미 파싱된 캐릭터 리스트입니다.")
            return raw_text
        elif isinstance(raw_text, dict):
            print("✅ 이미 파싱된 딕셔너리입니다.")
            return raw_text.get('characters', raw_text)
        
        # 문자열인 경우 정상적으로 파싱
        cleaned = clean_gemini_response(raw_text)
        print("🧼 캐릭터 cleaned (처음 1000자):", cleaned[:1000])
        print("🧼 캐릭터 cleaned (전체 길이):", len(cleaned))
        
        # JSON 파싱 시도
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as json_error:
            print(f"❌ 1차 JSON 파싱 실패: {json_error}")
            
            # 2차 시도: 더 강력한 수정
            fixed_json = auto_fix_json(cleaned)
            try:
                parsed = json.loads(fixed_json)
                print("✅ 2차 시도로 JSON 파싱 성공")
            except json.JSONDecodeError as second_error:
                print(f"❌ 2차 JSON 파싱도 실패: {second_error}")
                
                # 3차 시도: 정규식으로 강제 파싱
                try:
                    parsed = extract_json_with_regex(cleaned)
                    print("✅ 정규식으로 강제 파싱 성공")
                except Exception as regex_error:
                    print(f"❌ 정규식 파싱도 실패: {regex_error}")
                    raise json_error  # 원래 오류 발생
        
        
        # Gemini는 캐릭터 배열을 반환해야 함
        if not isinstance(parsed, list):
            print(f"⚠️ 배열이 아닌 형태로 응답받음: {type(parsed)}")
            if isinstance(parsed, dict) and 'characters' in parsed:
                parsed = parsed['characters']
            else:
                raise ValueError(f"Expected character array but got: {type(parsed)}")
        
        print(f"✅ 파싱된 캐릭터 {len(parsed)}개")
        
        # 각 캐릭터 데이터 검증
        for i, char in enumerate(parsed):
            if not isinstance(char, dict):
                print(f"⚠️ 캐릭터 {i+1}: 딕셔너리가 아님 - {type(char)}")
                continue
            
            required_fields = ['characterName', 'isMain', 'age', 'gender', 'characterDescription']
            missing_fields = [field for field in required_fields if field not in char]
            if missing_fields:
                print(f"⚠️ 캐릭터 {i+1}: 필수 필드 누락 - {missing_fields}")
        
        return parsed
        
    except json.JSONDecodeError as e:
        print("⚠️ 캐릭터 JSON 디코딩 실패:", e)
        print("🧠 최종 파싱 대상 (처음 500자):", cleaned[:500] if 'cleaned' in locals() else str(raw_text)[:500])
        raise
    except ValueError as ve:
        print("⚠️ 캐릭터 파싱 실패:", ve)
        print("🧠 최종 파싱 대상 (처음 500자):", cleaned[:500] if 'cleaned' in locals() else str(raw_text)[:500])
        raise
    except Exception as e:
        print(f"⚠️ 예상치 못한 오류: {type(e).__name__}: {e}")
        print("🧠 최종 파싱 대상 (처음 500자):", cleaned[:500] if 'cleaned' in locals() else str(raw_text)[:500])
        raise



def auto_fix_json(json_str):
    """
    일반적인 JSON 오류들을 자동으로 수정
    """
    try:
        import re
        
        # 1. 기본 정리
        fixed = json_str.strip()
        
        # 2. 잘못된 따옴표 문제 해결
        # JSON 값 내부의 unescaped quotes 처리
        def escape_quotes_in_values(match):
            full_match = match.group(0)
            key = match.group(1)
            value = match.group(2)
            
            # 값 내부의 따옴표를 이스케이프
            escaped_value = value.replace('"', '\\"')
            return f'"{key}": "{escaped_value}"'
        
        # "key": "value with "quotes" inside" 패턴을 찾아서 수정
        fixed = re.sub(r'"([^"]+)":\s*"([^"]*"[^"]*)"', escape_quotes_in_values, fixed)
        
        # 3. 추가 정리
        fixed = fixed.replace("'", '"')  # 홑따옴표를 쌍따옴표로
        
        # 4. 마지막 쉼표 제거
        fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)
        
        # 5. 제어 문자 및 특수 문자 처리
        fixed = fixed.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        fixed = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', fixed)
        
        # 6. 연속된 쉼표 제거
        fixed = re.sub(r',+', ',', fixed)
        
        return fixed
        
    except Exception as e:
        print(f"JSON 자동 수정 실패: {e}")
        return json_str

def generate_scenes_with_gemini(main_character, sub_characters, scene_count):
    """
    Gemini API를 사용하여 캐릭터 정보 기반으로 대본 생성
    """
    try:
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
        ]) if sub_characters else "조연 캐릭터 없음"

        # 🆕 주인공의 등장 장면 정보 가져오기 (CharacterScene 모델에서)
        from .models import CharacterScene
        import random
        
        character_scenes = CharacterScene.objects.filter(
            character=main_character, 
            is_deleted=False
        )
        
        # 랜덤하게 1~2개 장면 선택
        selected_scenes = []
        if character_scenes.exists():
            scene_count_to_select = min(random.randint(1, 2), character_scenes.count())
            selected_scenes = random.sample(list(character_scenes), scene_count_to_select)
        
        # 선택된 장면들을 프롬프트용 텍스트로 변환
        scene_context = ""
        if selected_scenes:
            scene_context = "\n[참고할 주인공 등장 장면들]\n"
            for i, scene in enumerate(selected_scenes, 1):
                scene_context += f"{i}. 페이지 {scene.start_page}-{scene.finish_page}: {scene.scene_content}\n"
            scene_context += "\n위 장면들을 참고하여 일관성 있는 스토리를 만들어주세요.\n"
        else:
            scene_context = "\n[주인공 등장 장면 정보 없음 - 캐릭터 설명을 바탕으로 창작해주세요]\n"

        # Gemini 모델 설정
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # 프롬프트 구성
        prompt = f"""
Please create {str(scene_count)} continuous and consistent story scenes based on the following novel information.

[info novel]
title: {str(book_title)}
content: {str(book_content[:5000])}

[Main character]
name: {str(main_name)}
age: {str(age)}
gender: {str(gender)}
description: {str(description)}

[Sub characters]
{str(sub_info)}

{str(scene_context)}

Requirements:
Unified Prompt Architecture and Requirements for Sequential Scene Generation
1.0 Objective
- The objective of these requirements is to define a Unified Prompt Architecture for generating multiple consecutive scenes (three scenes, 8 seconds each) from a single request. This architecture must ensure perfect visual consistency of characters, style, and mood, and implement a complete, coherent narrative. This is achieved not through interactive system functionality, but through the structural design of the prompt itself.
2.0 Core Principles
- {str(scene_count)} scenes must form a continuous and consistent story (start → middle → end).
- Each scene is made of an 8-second video, with a total of three. It should be storytelling when three videos are joined together.
- Global Declaration: Core elements common to all scenes (e.g., characters, style, lighting) are to be explicitly declared at the beginning of the prompt to establish a definitive baseline.
- Consistent Reference: In the scene-by-scene descriptions, the names and details of elements defined in the Global Declaration must be used accurately and consistently to aid the AI's continuity recognition.
- Sequential Narrative: Each scene must be clearly distinguished and arranged chronologically to construct a natural and logical narrative flow.

3.0 Storytelling & Continuity Requirements
All generated scenes must strictly adhere to the following narrative and content requirements:
- Complete Narrative: The three 8-second videos, when concatenated in order, must form a single, complete mini-story.
- Contextual and Mood Consistency: The prompt must faithfully reflect the context and mood of the provided examples (i.e., serious, contemplative, with a touch of mystery).
- Character Consistency: The protagonist's personality (serious, determined), behavioral patterns (intensely focused), and manner of speech must be perfectly consistent with established character traits.
- Logical Cohesion: The system must not generate isolated or disconnected scenes. Each scene must logically follow and build upon the events and emotional state of the preceding scene.
- Emotional and Behavioral Progression: A character's emotions and actions should not be static; they must evolve or intensify naturally with the flow of the narrative (e.g., from focus to surprise to realization).
- Plausible Reactivity: Dialogue and character actions must clearly reflect preceding events and the emotional states resulting from them.

4.0 Unified Prompt Structure Requirements
To successfully implement the storytelling requirements above, the prompt must be composed of the following two main parts:
Part 1: Preamble / Global Setup:
This section is located at the very beginning of the prompt and defines the governing rules for all subsequent scenes.
- 4.1 Master Instruction:
The prompt must begin with a master instruction that clearly informs the AI of the overall task (e.g., generating three consecutive scenes) and the mandate for consistency.
Example: "Please generate three consecutive 8-second scenes based on the following global settings and sequential descriptions. Maintain all character and style details consistently across all scenes to create a coherent narrative."

- 4.2 [CHARACTERS] Section:
This section must clearly define all key characters and their unchanging visual traits (e.g., appearance, core attire). This definition will remain constant across all scenes.
Example1: The Narrator: A pilot in his forties, with a tired but determined expression, wearing worn desert attire.
Example2: The Little Prince: A small boy with golden hair, wide curious eyes, and wearing a distinct green coat and a small yellow scarf.

- 4.3 [OVERALL_STYLE] Section:
This section must define the art direction, overall mood, and visual tone that will be applied consistently to all scenes.
Example: "A consistent Pixar-style animation, with vibrant colors, expressive character designs, and a warm, inviting atmosphere."

- 4.4 [CORE_LIGHTING] Section:
This section must define the core lighting scheme that will be maintained consistently across all scenes.
Example: "Warm, low-angled sunlight of the late afternoon, casting long shadows across the sand."

Part 2: Scene-by-Scene Descriptions:
(Following the Preamble, the specific descriptions for Scene 1, 2, and 3 are to be written sequentially, adhering to the detailed format defined previously.)

scene format:
- sceneId: Sequential numbers starting from 1 (e.g. 1, 2, 3, ...)
- background: Visual Description of Place and Time (English)
- mood: an emotional atmosphere
- style: Visual style (e.g., cinematic, anime-style)
- camera: Camera movement or framing (e.g. tracking shot, zoom-in)
- soundtrack: Explanation of background music and sound effects (English)
- characters: List of 1-2 characters (name, appearance, expression, action in English respectively)
- lines: Dialogue lines for characters (array of objects with speaker, line_en, line_ko)
  - Each line must have: speaker (character name), line_en (English dialogue), line_ko (Korean translation)
  - Include meaningful dialogue that advances the story or reveals character
  - If no dialogue in the scene, use empty array []
- rewriting_prompt: ⚠️⚠️ Very important ⚠️⚠️ Key and rich English sentence.
  - Place and time (e.g.: "in a moonlit forest at midnight")
  - Character's speaking/listening actions and detailed expressions (e.g.: "character speaks with a thoughtful expression, gesturing subtly", "listens intently, nodding slowly")
  - Camera work suggesting conversation flow (e.g.: "medium shot focusing on their faces", "slow pan between speakers", "close-up capturing a nuanced reaction")
  - Mood/background implied by the dialogue (e.g.: "hopeful atmosphere as they discuss future plans", "somber mood reflecting a difficult confession")
  - Add gestures and actions (e.g.: "paces thoughtfully while delivering a monologue", "leans in conspiratorially")
  - 1 background sound (e.g.: "soft wind sounds", "gentle string music")
  - Style: Pixar-style animation, ensuring visual consistency across all scenes.
  - **Dialogue in the prompt should be limited to approximately 6 seconds in length.**
  Important: Focus on visually enriching scenes with dialogue or monologue at their core, maintaining a consistent Pixar-style animation.
  Important: For characters speaking: Ensure mouth movements are natural and precisely synchronized with the implied dialogue. Facial expressions and mouth shapes should accurately reflect the spoken words and emotions.

  

Example of scene format:
{{
  "sceneId": 1,
  "background": "The vast Sahara desert at late afternoon, near the wreckage of a small airplane. The sun is low, casting long shadows on the sand.",
  "mood": "Serious, focused, and filled with a sense of urgency and underlying worry.",
  "style": "A unique blend of realistic, gritty desert textures and a soft, ethereal hand-drawn aesthetic.",
  "camera": "A tight close-up shot focusing on the Narrator's hands and his notepad, then slightly widening to capture his face.",
  "soundtrack": "The sharp, rhythmic scratching of a pencil on paper, accompanied by a faint, low, unsettling desert wind.",
  "characters": [
    {{
      "name": "The Narrator",
      "appearance": "A pilot in his forties, wearing worn and dusty desert attire.",
      "expression": "A brow furrowed with intense concentration and deep-seated worry.",
      "action": "Sketches rapidly and frantically on a notepad, muttering to himself, 'Beware the baobabs. Children must know.'"
    }},
    {{
      "name": "The Little Prince",
      "appearance": "A small boy with brilliant golden hair, wearing a distinct green coat and a small yellow scarf.",
      "expression": "A quiet, neutral, and deeply curious gaze.",
      "action": "Stands nearby, silently observing the Narrator with unwavering attention."
    }}
  ],
  "lines": [
    {{
      "speaker": "The Narrator",
      "line_en": "Beware the baobabs. Children must know.",
      "line_ko": "바오밥나무를 조심해. 아이들이 알아야 해."
    }}
  ],
  "rewriting_prompt": "A close-up shot focuses on the hands of the Narrator, a pilot in his forties, as he sketches frantically in a notepad amidst airplane wreckage in the Sahara. The low afternoon sun casts long shadows. His expression is one of intense worry as he mutters, 'Beware the baobabs. Children must know.' The only sounds are pencil scratching and a faint, unsettling wind. Nearby, the Little Prince, a small boy with golden hair and a green coat, watches him in silence with a curious gaze. The style is a blend of realistic desert textures and a soft, hand-drawn aesthetic."
}}


{{
  "sceneId": 2,
  "background": "The same Sahara desert location, moments after the first scene.",
  "mood": "The mood shifts from urgent to quiet, gentle, and slightly surreal with the Prince's unexpected request.",
  "style": "A unique blend of realistic, gritty desert textures and a soft, ethereal hand-drawn aesthetic.",
  "camera": "A static medium shot that frames both characters, observing their interaction from a neutral distance.",
  "soundtrack": "The pencil scratching stops abruptly. The soft crunch of sand underfoot is heard, and the desert wind becomes calmer.",
  "characters": [
    {{
      "name": "The Narrator",
      "appearance": "A pilot in his forties, wearing worn and dusty desert attire.",
      "expression": "Still focused on his drawing, initially unaware of the boy's approach.",
      "action": "Pauses his sketching for a moment, sensing a presence."
    }},
    {{
      "name": "The Little Prince",
      "appearance": "A small boy with brilliant golden hair, wearing a distinct green coat and a small yellow scarf.",
      "expression": "Calm, innocent, and direct, with a clear sense of purpose.",
      "action": "Takes a cautious step closer and speaks for the first time, his voice clear and gentle, 'If you please... draw me a sheep.'"
    }}
  ],
  "lines": [
    {{
      "speaker": "The Little Prince",
      "line_en": "If you please... draw me a sheep.",
      "line_ko": "부탁이 있어요... 양 한 마리를 그려주세요."
    }}
  ],
  "rewriting_prompt": "A moment later, the camera is a static medium shot. The Little Prince takes a step closer to the Narrator, his boots crunching softly on the sand. The Narrator pauses his sketching. Maintaining the blend of realistic and hand-drawn styles, the Little Prince looks at the Narrator and speaks in a clear, gentle voice, 'If you please... draw me a sheep.' The urgent mood shifts to one of quiet, surreal wonder."
}}

{{
  "sceneId": 3,
  "background": "The same location, focused tightly on the two characters.",
  "mood": "Stunned silence, pure astonishment, and a moment of disbelief that breaks the desert's lonely tension.",
  "style": "A unique blend of realistic, gritty desert textures and a soft, ethereal hand-drawn aesthetic.",
  "camera": "A tight close-up on the Narrator's face to capture his reaction. The camera is perfectly still, with no movement.",
  "soundtrack": "Almost complete silence. The faint sound of the wind dies down entirely to emphasize the stunned moment.",
  "characters": [
    {{
      "name": "The Narrator",
      "appearance": "A pilot in his forties, wearing worn and dusty desert attire.",
      "expression": "Eyes widening in pure astonishment and disbelief. His mouth is slightly agape, completely speechless.",
      "action": "His hand, holding the pencil, freezes mid-air. He looks up from his notepad and truly SEES the Little Prince for the first time."
    }},
    {{
      "name": "The Little Prince",
      "appearance": "A small boy with brilliant golden hair, wearing a distinct green coat and a small yellow scarf.",
      "expression": "A patient, serene, and expectant gaze, as if his request was the most natural thing in the world.",
      "action": "Stands perfectly still, calmly waiting for the Narrator's response."
    }}
  ],
  "lines": [],
  "rewriting_prompt": "The camera cuts to a tight close-up of the Narrator's face. His hand freezes. His eyes widen in pure astonishment as he looks up and truly sees the Little Prince for the first time. A stunned silence falls as even the wind seems to hold its breath. The Narrator is speechless, his expression shifting from frantic worry to utter disbelief, while the Little Prince stands patiently, waiting for his sheep."
}}

Output Rules:
- Return only pure valid JSON. Without explanation or markdown.
- All strings must be enclosed in double quotation marks (").
- JSON structure must be strictly correct.
- Each scene should contain exactly 1-2 characters. Not all supporting roles need to be in every scene.
- All language used in the prompt and generated video content must be English only.

Each scene must be a JSON object with the following keys:
- sceneId: sequential number starting from 1
- background: string
- mood: string
- style: string
- camera: string
- soundtrack: string
- Characters: Character object list (name, application, expression, action)
- lines: Array of dialogue objects with speaker, line_en, line_ko
- rewriting_prompt: English sentence 

Return the scene arrangement in JSON form. Without further comment or markdown.
"""



        # Gemini API 호출
        response = model.generate_content(prompt)
        raw_text = response.text
        print("🧠 대본 생성 Gemini 응답:\n", raw_text)
        print(f"DEBUG: Raw Gemini response text: {raw_text[:1000]}...") # Log first 1000 chars for debugging
        
        # 응답 파싱
        return parse_scene_list(raw_text)
        
    except Exception as e:
        print(f"⚠️ Gemini API 대본 생성 중 오류 발생: {str(e)}")
        raise

def parse_scene_list(raw_text):
    """
    Gemini API 응답을 파싱하여 대본 데이터로 변환
    """
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
            cleaned = clean_gemini_response(raw_text)
            print("🧼 씬 cleaned:", cleaned[:200] + "..." if len(cleaned) > 200 else cleaned)

            parsed = json.loads(cleaned)
            
            # Gemini가 배열을 반환하는지 객체를 반환하는지 확인
            if isinstance(parsed, list):
                # Gemini가 배열을 반환한 경우 (일반적인 경우)
                scenes = parsed
                script_id = f"scpt-{uuid.uuid4().hex[:8]}"
            elif isinstance(parsed, dict):
                # Gemini가 객체를 반환한 경우
                scenes = parsed.get("scenes", [])
                script_id = parsed.get("script_id", f"scpt-{uuid.uuid4().hex[:8]}")
            else:
                raise ValueError(f"Unexpected Gemini response type: {type(parsed)}")

        # sceneId 및 rewriting_id 부여
        for idx, scene in enumerate(scenes):
            scene["sceneId"] = idx + 1
            scene["rewriting_id"] = f"{script_id}-scene-{idx + 1}"
            
            # rewriting_prompt 길이 검증 및 자동 단축
            if "rewriting_prompt" in scene:
                rewriting_prompt = scene["rewriting_prompt"]
                if len(rewriting_prompt) > 3000:
                    print(f"⚠️ 장면 {idx + 1} rewriting_prompt가 너무 깁니다 ({len(rewriting_prompt)}자). 2900자로 단축합니다.")
                    scene["rewriting_prompt"] = rewriting_prompt[:2900].rsplit(' ', 1)[0] + "."
                    print(f"✅ 단축 완료: {len(scene['rewriting_prompt'])}자")
                elif len(rewriting_prompt) < 200:
                    print(f"⚠️ 장면 {idx + 1} rewriting_prompt가 너무 짧습니다 ({len(rewriting_prompt)}자).")

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


# ========================================
# 청킹 기반 캐릭터 생성을 위한 유틸리티 함수들
# (SmartGeminiClient에서 편입)
# ========================================

def extract_characters_from_chunk_with_retry(chunk_text: str, chunk_info: dict, max_retries: int = 3) -> list:
    """
    청크에서 캐릭터 정보를 추출 (재시도 로직 포함)
    
    Args:
        chunk_text: 청크 텍스트
        chunk_info: 청크 메타데이터  
        max_retries: 최대 재시도 횟수
        
    Returns:
        추출된 캐릭터 정보 리스트
    """
    import time
    import random
    
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
다음 텍스트 청크에서 등장인물들의 정보를 추출해주세요.

⚠️ 중요 규칙:
- 반드시 유효한 JSON 배열만 출력하세요. 설명이나 추가 텍스트는 절대 포함하지 마세요.
- 이 청크에서 실제로 등장하는 인물만 추출하세요.
- 불분명하거나 애매한 인물은 제외하세요.

청크 정보:
- 청크 번호: {chunk_info.get('chunk_number')}
- 예상 페이지: {chunk_info.get('estimated_start_page')}-{chunk_info.get('estimated_end_page')}

요청사항:
각 인물은 다음 정보를 포함해야 해:
- characterName: 이름 (문자열)
- isMain: 주인공 가능성 (true 또는 false)
- age: 추정 나이 (정수, 불명확하면 25)
- gender: 성별 ("남성" 또는 "여성" 또는 "불명")
- characterDescription: 인물 설명 (30-50자)
- chunkSource: {chunk_info.get('chunk_number')} (이 청크에서 발견되었음을 표시)

JSON 형식:
[
  {{
    "characterName": "홍길동",
    "isMain": true,
    "age": 25,
    "gender": "남성",
    "characterDescription": "의적으로 활동하며 백성들을 도와주는 정의로운 인물",
    "chunkSource": {chunk_info.get('chunk_number')}
  }}
]

텍스트 청크:
{chunk_text[:8000]}
"""

    for retry_count in range(max_retries + 1):
        try:
            print(f"🤖 청크 {chunk_info.get('chunk_number')} Gemini 요청 시작... (시도 {retry_count + 1}/{max_retries + 1})")
            
            response = model.generate_content(prompt)
            raw_text = response.text.strip()
            
            # JSON 파싱 시도
            characters = parse_character_response_safe(raw_text)
            
            print(f"✅ 청크 {chunk_info.get('chunk_number')} 처리 완료 - {len(characters)}명 발견")
            return characters
            
        except Exception as e:
            print(f"❌ 청크 {chunk_info.get('chunk_number')} 처리 실패: {str(e)}")
            
            if retry_count < max_retries:
                delay = 2 * (2 ** retry_count) + random.uniform(0, 1)
                print(f"🔄 {delay:.1f}초 후 재시도...")
                time.sleep(delay)
            else:
                print(f"💥 청크 {chunk_info.get('chunk_number')} 최대 재시도 초과")
                return []

def merge_and_deduplicate_characters(all_characters: list) -> list:
    """
    여러 청크에서 추출된 캐릭터들을 병합하고 중복 제거
    
    Args:
        all_characters: 청크별 캐릭터 리스트들
        
    Returns:
        병합된 최종 캐릭터 리스트
    """
    # 모든 캐릭터를 하나의 리스트로 합치기
    flattened_characters = []
    for chunk_characters in all_characters:
        flattened_characters.extend(chunk_characters)
    
    if not flattened_characters:
        return []
    
    print(f"🔍 병합 전 총 캐릭터 수: {len(flattened_characters)}")
    
    # 이름 기반 그룹핑 (유사한 이름들도 고려)
    character_groups = {}
    
    for char in flattened_characters:
        name = char['characterName'].strip()
        
        # 기존 그룹과 유사한 이름 찾기
        matched_group = None
        for existing_name in character_groups.keys():
            if are_similar_names(name, existing_name):
                matched_group = existing_name
                break
        
        if matched_group:
            character_groups[matched_group].append(char)
        else:
            character_groups[name] = [char]
    
    # 각 그룹에서 최고의 캐릭터 선택
    final_characters = []
    for name_group, chars in character_groups.items():
        best_char = select_best_character(chars)
        final_characters.append(best_char)
    
    # 주인공 우선, 이름 순으로 정렬
    final_characters.sort(key=lambda x: (not x['isMain'], x['characterName']))
    
    print(f"✅ 중복 제거 완료 - 최종 캐릭터 수: {len(final_characters)}")
    return final_characters

def are_similar_names(name1: str, name2: str) -> bool:
    """
    두 이름이 유사한지 판단 (별명, 축약 등 고려)
    """
    name1, name2 = name1.lower().strip(), name2.lower().strip()
    
    # 완전 일치
    if name1 == name2:
        return True
    
    # 한 이름이 다른 이름에 포함되는 경우
    if name1 in name2 or name2 in name1:
        return True
    
    # 편집 거리 기반 유사도 (간단한 버전)
    if len(name1) >= 2 and len(name2) >= 2:
        common_chars = set(name1) & set(name2)
        if len(common_chars) >= min(len(name1), len(name2)) * 0.7:
            return True
    
    return False

def select_best_character(chars: list) -> dict:
    """
    같은 캐릭터의 여러 버전 중 최고의 것 선택
    """
    # 설명이 가장 자세한 것 우선
    best_char = max(chars, key=lambda x: len(x.get('characterDescription', '')))
    
    # 여러 청크에서 발견된 정보 병합
    all_chunk_sources = []
    for char in chars:
        if 'chunkSource' in char:
            all_chunk_sources.append(char['chunkSource'])
    
    best_char['chunkSources'] = sorted(set(all_chunk_sources))
    best_char['discoveryCount'] = len(all_chunk_sources)
    
    return best_char

def create_character_scenes_with_retry(character: dict, book_content_summary: str, max_retries: int = 3) -> list:
    """
    캐릭터를 위한 장면 정보 생성 (재시도 로직 포함)
    """
    import time
    import random
    
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # 프롬프트 최적화 (길이 단축)
    book_summary = book_content_summary[:500] if book_content_summary else "책 내용 요약 없음"
    
    prompt = f"""
캐릭터 '{character['characterName']}'의 등장 장면을 생성해주세요.

캐릭터 정보:
- 이름: {character['characterName']}
- 설명: {character['characterDescription']}

책 요약: {book_summary}

요청사항:
- 1-2개의 주요 장면만 생성
- 각 장면은 200-300자의 간결한 묘사
- 반드시 JSON 배열만 출력하세요

JSON 형식:
[
  {{
    "scene_content": "간결한 장면 묘사 (200-300자)",
    "start_page": 1,
    "finish_page": 5
  }}
]
"""

    for retry_count in range(max_retries + 1):
        try:
            # API 호출 간격 조절 (Rate Limit 방지) - 병렬 처리에서는 불필요하므로 주석 처리
            # if retry_count == 0:
            #     time.sleep(random.uniform(0.5, 1.5))
            
            print(f"🎬 '{character['characterName']}' 장면 생성 시작... (시도 {retry_count + 1}/{max_retries + 1})")
            
            response = model.generate_content(prompt)
            raw_text = response.text.strip()
            
            # 장면 전용 파싱
            scenes = parse_scene_response_safe(raw_text)
            
            if scenes:
                print(f"✅ '{character['characterName']}' 장면 생성 완료 - {len(scenes)}개")
                return scenes
            else:
                print(f"⚠️ '{character['characterName']}' 장면 파싱 실패")
                if retry_count == max_retries:
                    return create_default_scene(character)
        
        except Exception as e:
            print(f"❌ '{character['characterName']}' 장면 생성 실패: {str(e)}")
            
            if retry_count < max_retries:
                delay = 2 * (2 ** retry_count) + random.uniform(1, 3)
                print(f"🔄 {delay:.1f}초 후 재시도...")
                time.sleep(delay)
            else:
                print(f"💥 '{character['characterName']}' 최대 재시도 초과, 기본 장면 생성")
                return create_default_scene(character)

def parse_character_response_safe(raw_text: str) -> list:
    """
    캐릭터 전용 안전한 JSON 파싱
    """
    try:
        import re
        import json
        
        # JSON 블록 찾기
        json_pattern = r'\[[\s\S]*\]'
        json_match = re.search(json_pattern, raw_text)
        
        if json_match:
            json_text = json_match.group()
            characters = json.loads(json_text)
            
            # 유효성 검사
            if isinstance(characters, list):
                valid_characters = []
                for char in characters:
                    if validate_character_data(char):
                        valid_characters.append(char)
                return valid_characters
        
        print(f"⚠️ 캐릭터 JSON 파싱 실패, 원본 응답: {raw_text[:200]}...")
        return []
        
    except json.JSONDecodeError as e:
        print(f"❌ 캐릭터 JSON 디코딩 실패: {str(e)}")
        return []
    except Exception as e:
        print(f"❌ 캐릭터 응답 파싱 실패: {str(e)}")
        return []

def parse_scene_response_safe(raw_text: str) -> list:
    """
    장면 전용 안전한 JSON 파싱
    """
    try:
        import re
        import json
        
        # JSON 배열 패턴 찾기
        json_pattern = r'\[[\s\S]*?\]'
        json_match = re.search(json_pattern, raw_text)
        
        if json_match:
            json_text = json_match.group()
            scenes = json.loads(json_text)
            
            if isinstance(scenes, list):
                valid_scenes = []
                for scene in scenes:
                    if validate_scene_data(scene):
                        valid_scenes.append(scene)
                return valid_scenes[:2]  # 최대 2개
        
        print(f"⚠️ 장면 JSON 파싱 실패: {raw_text[:150]}...")
        return []
        
    except json.JSONDecodeError as e:
        print(f"❌ 장면 JSON 디코딩 실패: {str(e)}")
        return []
    except Exception as e:
        print(f"❌ 장면 파싱 실패: {str(e)}")
        return []

def validate_character_data(char: dict) -> bool:
    """
    캐릭터 정보 유효성 검사
    """
    required_fields = ['characterName', 'isMain', 'age', 'gender', 'characterDescription']
    
    for field in required_fields:
        if field not in char:
            return False
    
    # 이름 길이 체크
    if not char['characterName'] or len(char['characterName']) > 50:
        return False
        
    # 나이 범위 체크
    if not isinstance(char['age'], int) or char['age'] < 1 or char['age'] > 200:
        return False
        
    return True

def validate_scene_data(scene: dict) -> bool:
    """
    장면 정보 유효성 검사
    """
    required_fields = ['scene_content']
    
    for field in required_fields:
        if field not in scene:
            return False
    
    # 장면 내용 길이 체크
    content = scene.get('scene_content', '')
    if not content or len(content) < 50:  # 최소 50자
        return False
        
    # 페이지 정보가 없으면 기본값 설정
    if 'start_page' not in scene:
        scene['start_page'] = 1
    if 'finish_page' not in scene:
        scene['finish_page'] = scene['start_page'] + 5
        
    return True

def create_default_scene(character: dict) -> list:
    """
    API 실패 시 기본 장면 생성
    """
    return [{
        "scene_content": f"{character['characterName']}이(가) 중요한 역할을 하는 장면입니다. {character.get('characterDescription', '캐릭터의 개성과 행동이 잘 드러나는 상황에서 다른 인물들과 상호작용하며 이야기를 전개해 나갑니다.')}",
        "start_page": 1,
        "finish_page": 10
    }]
