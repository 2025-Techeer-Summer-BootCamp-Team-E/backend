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
            # URL에서 S3 키 추출
            s3_key = pdf_url.split('.com/')[-1]
            
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
  - characterDescription: 인물 설명 (최대 500자, 문자열)
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
  {
    "characterName": "홍길동",
    "isMain": true,
    "age": 25,
    "gender": "남성",
    "characterDescription": "의적으로 활동하며 백성들을 도와주는 정의로운 인물",
    "scenes": [
      {
        "scene_content": "홍길동이 어둠 속에서 탐관오리의 저택에 침입하는 장면이다. 달빛이 희미하게 비치는 가운데, 그는 검은 의복을 입고 담장을 넘어든다. 저택 안에서는 탐관오리가 백성들의 세금을 횡령하며 호화로운 잔치를 벌이고 있다. 홍길동은 조용히 기와지붕 위를 이동하며 창문 너머로 그 광경을 지켜본다. 그의 눈빛에는 분노와 정의감이 타오르고 있다. 마침내 적절한 순간을 포착한 그는 창문을 열고 방 안으로 뛰어든다. '탐관오리여, 네 죄를 알겠느냐!' 홍길동의 외침이 저택 전체에 울려 퍼지며, 놀란 탐관오리와 하인들이 벌벌 떨기 시작한다.",
        "start_page": 15,
        "finish_page": 18
      }
    ]
  }
]

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
            print(f"❌ JSON 파싱 실패! 오류 위치: line {json_error.lineno}, column {json_error.colno}")
            print(f"❌ 오류 메시지: {json_error.msg}")
            print(f"❌ 문제가 있는 부분 (오류 위치 ±50자):")
            
            error_pos = json_error.pos if hasattr(json_error, 'pos') else 0
            start_pos = max(0, error_pos - 50)
            end_pos = min(len(cleaned), error_pos + 50)
            problem_section = cleaned[start_pos:end_pos]
            print(f"   '{problem_section}'")
            
            # 수정 시도 - 일반적인 JSON 오류들 자동 수정
            print("🔧 JSON 자동 수정 시도...")
            fixed_json = auto_fix_json(cleaned)
            if fixed_json != cleaned:
                print("✅ JSON 수정 완료, 재시도...")
                parsed = json.loads(fixed_json)
            else:
                raise json_error
        
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
        # 1. 따옴표 문제 수정
        fixed = json_str.replace("'", '"')  # 홑따옴표를 쌍따옴표로
        
        # 2. 마지막 쉼표 제거
        import re
        fixed = re.sub(r',\s*}', '}', fixed)  # 객체 마지막 쉼표 제거
        fixed = re.sub(r',\s*]', ']', fixed)  # 배열 마지막 쉼표 제거
        
        # 3. 줄바꿈 문자 이스케이프
        fixed = fixed.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        
        # 4. 제어 문자 제거
        fixed = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', fixed)
        
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
다음 소설 정보를 바탕으로 {scene_count}개의 연속적이고 일관된 스토리 장면을 생성해주세요.

[소설 정보]
제목: {book_title}
내용: {book_content}

[주인공]
이름: {main_name}
나이: {age}
성별: {gender}
설명: {description}

[조연 캐릭터들]
{sub_info}

{scene_context}

요구사항:
- {scene_count}개의 장면은 연속적이고 일관된 스토리를 형성해야 합니다 (시작 → 중간 → 끝).
    - 각 장면은 8초 영상으로 만들어지며, 총 3개 만들어집니다. 세 영상을 이어붙였을때 스토리텔링이 되어야합니다.
- 위에 제공된 주인공 등장 장면들의 맥락과 분위기를 반영해주세요.
- 주인공의 성격, 행동 양식, 말투 등이 기존 장면과 일치하도록 해주세요.
- 독립적이거나 연결되지 않은 장면을 생성하지 마세요.
- 각 장면은 이전 장면을 논리적으로 이어받아야 합니다.
- 캐릭터의 감정과 행동이 장면 간에 자연스럽게 발전해야 합니다.
- 대화와 캐릭터 행동은 이전 사건과 감정 상태를 반영해야 합니다.

장면 형식:
- sceneId: 1부터 시작하는 순차 번호 (예: 1, 2, 3, ...)
- background: 장소와 시간에 대한 시각적 설명 (영어)
- mood: 감정적 분위기 (영어)
- style: 시각적 스타일 (예: cinematic, anime-style)
- camera: 카메라 움직임이나 프레이밍 (예: tracking shot, zoom-in)
- soundtrack: 배경음악과 음향효과 설명 (영어)
- characters: 1-2명의 캐릭터 리스트 (각각 name, appearance, expression, action을 영어로)
- lines: 대화 리스트. 각 라인은 다음을 포함:
  - speaker: 화자 이름
  - line_en: 영어 대사
  - line_ko: 한국어 번역 대사
  - ⚠️중요! 화자는 단 한 명뿐입니다! line_en과 line_ko는 모두 화자의 대사입니다.
- 장면당 한 명의 캐릭터만 말해야 합니다.
- 한국어 대사(line_ko)는 3-4초 안에 말할 수 있도록 짧게 (10-15글자 정도).
- 자연스럽고 간단한 표현을 사용하세요. 길고 복잡한 문장은 피하세요.
- 실제 사람이 말하는 것처럼 구어체로 만드세요.
- rewriting_prompt: ⚠️⚠️ 매우 중요 ⚠️⚠️간결하고 핵심적이며 풍부한 영어 문장 (⚠️ 반드시 500~900자 사이).
  다음 요소들을 포함하되 간결하게 작성:
  - 장소와 시간 (예: "in a moonlit forest at midnight")
  - 주인공의 핵심 행동 (예: "character walks cautiously")
  - 기본 분위기 (예: "tense, mysterious atmosphere")
  - 카메라 움직임 1개 (예: "close-up shot" 또는 "wide angle")
  - 배경음 1개 (예: "soft wind sounds")
  ⚠️ 중요: 긴 설명보다는 핵심 키워드들을 연결한 간결한 문장으로 작성하세요.

rewriting_prompt 좋은 예시:
"A young warrior stands in a moonlit forest clearing at midnight, gripping his sword with determination as shadows dance around ancient trees, while soft wind whispers through leaves and an owl hoots in the distance, creating a tense yet mystical atmosphere with a close-up shot capturing his focused expression and the gleaming blade reflecting moonlight."

출력 규칙:
- 순수한 유효한 JSON만 반환하세요. 설명이나 마크다운은 없이.
- 모든 문자열은 큰따옴표(")로 감싸야 합니다.
- JSON 구조가 엄격하게 올바라야 합니다.
- 각 장면은 정확히 1-2명의 캐릭터를 포함해야 합니다. 모든 조연이 모든 장면에 나올 필요는 없습니다.

각 장면은 다음 키를 가진 JSON 객체여야 합니다:
- sceneId: 1부터 시작하는 순차 번호
- background: 문자열
- mood: 문자열
- style: 문자열
- camera: 문자열
- soundtrack: 문자열
- characters: 캐릭터 객체 리스트 (name, appearance, expression, action)
- lines: 대화 객체 리스트 (speaker, line_en, line_ko)
- rewriting_prompt: 간결하지만 묘사가 풍부한 영어 문장 (500~900자를 엄격하게 준수하세요!)

장면 배열을 JSON 형태로 반환하세요. 추가 설명이나 마크다운 없이.
"""

        # Gemini API 호출
        response = model.generate_content(prompt)
        raw_text = response.text
        print("🧠 대본 생성 Gemini 응답:\n", raw_text)
        
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
                if len(rewriting_prompt) > 1000:
                    print(f"⚠️ 장면 {idx + 1} rewriting_prompt가 너무 깁니다 ({len(rewriting_prompt)}자). 900자로 단축합니다.")
                    scene["rewriting_prompt"] = rewriting_prompt[:900].rsplit(' ', 1)[0] + "."
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
