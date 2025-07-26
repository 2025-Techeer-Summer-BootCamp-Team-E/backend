from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.cache import caches
from .models import Character, CharacterScene
from .gemini_client import (
    generate_scenes_with_gemini,
    parse_scene_list,
    fetch_pdf_from_s3,
    extract_characters_from_chunk_with_retry,
    merge_and_deduplicate_characters,
    create_character_scenes_with_retry
)
from .pdf_chunker import (
    chunk_pdf_content,
    smart_chunk_sizing,
    prioritize_character_chunks
)
from books.models import Book
import datetime

# Celery 전용 로거 설정
logger = get_task_logger(__name__)

@shared_task(bind=True)
def generate_script_task(self, character_id, scene_count=3):
    """
    대본을 비동기적으로 생성하는 Celery 태스크 (Redis 기반)
    
    Args:
        character_id: Character ID
        scene_count: 생성할 장면 수
    """
    task_id = self.request.id
    script_cache = caches['script_cache']
    
    # Redis에 태스크 상태 저장
    task_key = f"task:{task_id}"
    
    try:
        # 1. 초기 상태 저장
        script_cache.set(task_key, {
            "status": "PROCESSING",
            "character_id": character_id,
            "scene_count": scene_count,
            "started_at": datetime.datetime.now().isoformat(),
            "message": "대본 생성 중..."
        }, timeout=3600)  # 1시간
        
        logger.info(f"📝 [TASK START] 대본 생성 시작 - Character ID: {character_id}, Task ID: {task_id}")
        
        # Character 조회
        character = Character.objects.get(id=character_id, is_deleted=False)
        logger.info(f"🎭 [CHARACTER] 캐릭터 정보 로드 - 이름: '{character.characterName}', 주인공: {character.isMain}")
        
        # 조연 캐릭터 정보 수집
        sub_characters = Character.objects.filter(
            book=character.book, isMain=False, is_deleted=False
        ).exclude(id=character.id)
        logger.info(f"👥 [SUB CHARACTERS] 조연 캐릭터 {sub_characters.count()}명 수집")
        
        # 2. Gemini API로 대본 생성
        logger.info("🤖 [STEP 1/2] Gemini API 대본 생성 시작...")
        
        # 진행 상태 업데이트
        script_cache.set(task_key, {
            "status": "PROCESSING",
            "character_id": character_id,
            "character_name": character.characterName,
            "scene_count": scene_count,
            "started_at": datetime.datetime.now().isoformat(),
            "message": "Gemini API로 대본 생성 중..."
        }, timeout=3600)
        
        raw_text = generate_scenes_with_gemini(
            main_character=character,
            sub_characters=sub_characters,
            scene_count=scene_count,
        )
        logger.info(f"📄 [STEP 1/2] Gemini API 응답 완료 - 응답 길이: {len(raw_text)} 문자")
        
        # 3. 파싱 및 Redis 캐시 저장
        logger.info("📋 [STEP 2/2] 대본 파싱 및 캐싱 시작...")
        
        # 진행 상태 업데이트
        script_cache.set(task_key, {
            "status": "PROCESSING",
            "character_id": character_id,
            "character_name": character.characterName,
            "scene_count": scene_count,
            "started_at": datetime.datetime.now().isoformat(),
            "message": "대본 파싱 및 저장 중..."
        }, timeout=3600)
        
        parsed_result = parse_scene_list(raw_text)
        
        script_id = parsed_result.get("script_id")
        scene_texts = parsed_result.get("scenes", [])
        logger.info(f"🔍 [PARSING] 파싱 완료 - Script ID: {script_id}, 장면 수: {len(scene_texts)}")
        
        # scene 구조 생성
        generated_scenes = []
        for scene in scene_texts:
            scene_id = scene.get("sceneId")
            generated_scenes.append({
                "sceneId": scene_id,
                "background": scene.get("background"),
                "mood": scene.get("mood"),
                "style": scene.get("style"),
                "camera": scene.get("camera"),
                "soundtrack": scene.get("soundtrack"),
                "characters": scene.get("characters"),
                "rewriting_prompt": scene.get("rewriting_prompt"),
                "rewriting_id": scene.get("rewriting_id")
            })
        
        # 대본을 Redis에 저장
        script_cache_key = f"script:{script_id}"
        script_cache.set(script_cache_key, {
            "characterId": character_id,
            "scenes": generated_scenes
        }, timeout=2000)  # 2000초 동안 캐시
        logger.info(f"💾 [CACHE] Redis 대본 캐싱 완료 - Key: {script_cache_key}")
        
        # 4. 완료 상태 저장
        script_cache.set(task_key, {
            "status": "COMPLETED",
            "character_id": character_id,
            "character_name": character.characterName,
            "scene_count": scene_count,
            "script_id": script_id,
            "started_at": datetime.datetime.now().isoformat(),
            "completed_at": datetime.datetime.now().isoformat(),
            "message": "대본 생성이 완료되었습니다."
        }, timeout=3600)
        
        logger.info(f"✅ [TASK COMPLETE] 대본 생성 완료 - Task ID: {task_id}, Script ID: {script_id}")
        
        return {
            "status": "success",
            "task_id": task_id,
            "character_id": character_id,
            "script_id": script_id,
            "scene_count": len(generated_scenes)
        }
        
    except Character.DoesNotExist:
        error_msg = f"캐릭터를 찾을 수 없습니다 - ID: {character_id}"
        logger.error(f"❌ [ERROR] {error_msg}")
        
        # 실패 상태 저장
        script_cache.set(task_key, {
            "status": "FAILED",
            "character_id": character_id,
            "scene_count": scene_count,
            "started_at": datetime.datetime.now().isoformat(),
            "failed_at": datetime.datetime.now().isoformat(),
            "error_message": error_msg
        }, timeout=3600)
        
        return {"status": "error", "message": error_msg}
    
    except Exception as e:
        error_msg = f"대본 생성 중 오류 발생: {str(e)}"
        logger.error(f"❌ [ERROR] {error_msg}")
        logger.error(f"❌ [ERROR] 오류 타입: {type(e).__name__}")
        
        # 실패 상태 저장
        script_cache.set(task_key, {
            "status": "FAILED",
            "character_id": character_id,
            "scene_count": scene_count,
            "started_at": datetime.datetime.now().isoformat(),
            "failed_at": datetime.datetime.now().isoformat(),
            "error_message": error_msg
        }, timeout=3600)
        
        import traceback
        logger.error(f"❌ [ERROR] 상세 스택 트레이스:\n{traceback.format_exc()}")
        
        # Celery에 실패 상태 전달
        self.update_state(
            state='FAILURE',
            meta={'error': error_msg, 'task_id': task_id}
        )
        raise Exception(error_msg)


@shared_task(bind=True)
def generate_characters_task(self, book_id):
    """
    PDF에서 캐릭터를 비동기적으로 생성하는 Celery 태스크 (고급 처리)
    
    Args:
        book_id: Book 인스턴스 ID
    """
    task_id = self.request.id
    script_cache = caches['script_cache']
    
    # Redis에 태스크 상태 저장
    task_key = f"character_task:{task_id}"
    
    try:
        # 1. 초기 상태 저장
        script_cache.set(task_key, {
            "status": "PROCESSING",
            "book_id": book_id,
            "step": "initialization",
            "started_at": datetime.datetime.now().isoformat(),
            "message": "캐릭터 생성 초기화 중..."
        }, timeout=7200)  # 2시간
        
        logger.info(f"🎭 [TASK START] 캐릭터 생성 시작 - Book ID: {book_id}, Task ID: {task_id}")
        
        # Book 조회
        book = Book.objects.get(id=book_id)
        logger.info(f"📚 [BOOK] 책 정보 로드 - 제목: '{book.title}'")
        
        # 2. PDF 다운로드 및 청킹
        script_cache.set(task_key, {
            "status": "PROCESSING",
            "book_id": book_id,
            "book_title": book.title,
            "step": "pdf_processing",
            "started_at": datetime.datetime.now().isoformat(),
            "message": "PDF 다운로드 및 청킹 중..."
        }, timeout=7200)
        
        logger.info("📄 [STEP 1/4] PDF 다운로드 시작...")
        pdf_content = fetch_pdf_from_s3(book_id)
        logger.info(f"📄 [STEP 1/4] PDF 다운로드 완료 - 크기: {len(pdf_content)} bytes")
        
        # 스마트 청킹
        optimal_chunk_size = smart_chunk_sizing(len(pdf_content))
        chunks = chunk_pdf_content(pdf_content, f"book_{book_id}.pdf", optimal_chunk_size)
        
        if not chunks:
            raise Exception("PDF 청킹 실패: 유효한 청크가 생성되지 않았습니다.")
        
        # 캐릭터 우선순위 적용
        prioritized_chunks = prioritize_character_chunks(chunks)
        
        # 처리할 청크 수 제한 (너무 많으면 시간이 오래 걸림)
        max_chunks = 8 if len(prioritized_chunks) > 8 else len(prioritized_chunks)
        selected_chunks = prioritized_chunks[:max_chunks]
        
        logger.info(f"📊 [CHUNKING] 청킹 완료 - 총 {len(chunks)}개 중 상위 {len(selected_chunks)}개 선택")
        
        # 3. 청크별 캐릭터 추출
        script_cache.set(task_key, {
            "status": "PROCESSING",
            "book_id": book_id,
            "book_title": book.title,
            "step": "character_extraction",
            "total_chunks": len(selected_chunks),
            "processed_chunks": 0,
            "started_at": datetime.datetime.now().isoformat(),
            "message": f"캐릭터 추출 중... (0/{len(selected_chunks)})"
        }, timeout=7200)
        
        logger.info("🤖 [STEP 2/4] 청크별 캐릭터 추출 시작...")
        
        all_chunk_characters = []
        
        for i, chunk in enumerate(selected_chunks):
            # 진행 상황 업데이트
            script_cache.set(task_key, {
                "status": "PROCESSING",
                "book_id": book_id,
                "book_title": book.title,
                "step": "character_extraction",
                "total_chunks": len(selected_chunks),
                "processed_chunks": i,
                "current_chunk": chunk['chunk_number'],
                "started_at": datetime.datetime.now().isoformat(),
                "message": f"캐릭터 추출 중... ({i}/{len(selected_chunks)}) - 청크 {chunk['chunk_number']}"
            }, timeout=7200)
            
            chunk_characters = extract_characters_from_chunk_with_retry(
                chunk['text'], 
                chunk
            )
            all_chunk_characters.append(chunk_characters)
            
            logger.info(f"🎭 청크 {chunk['chunk_number']} 처리 완료 - {len(chunk_characters)}명 발견")
        
        # 4. 캐릭터 병합 및 중복 제거
        script_cache.set(task_key, {
            "status": "PROCESSING",
            "book_id": book_id,
            "book_title": book.title,
            "step": "character_merging",
            "started_at": datetime.datetime.now().isoformat(),
            "message": "캐릭터 병합 및 중복 제거 중..."
        }, timeout=7200)
        
        logger.info("🔄 [STEP 3/4] 캐릭터 병합 및 중복 제거 시작...")
        final_characters = merge_and_deduplicate_characters(all_chunk_characters)
        
        if not final_characters:
            raise Exception("캐릭터 추출 실패: 유효한 캐릭터가 발견되지 않았습니다.")
        
        # 5. 장면 생성 및 DB 저장
        script_cache.set(task_key, {
            "status": "PROCESSING",
            "book_id": book_id,
            "book_title": book.title,
            "step": "scene_generation",
            "total_characters": len(final_characters),
            "processed_characters": 0,
            "started_at": datetime.datetime.now().isoformat(),
            "message": f"장면 생성 및 저장 중... (0/{len(final_characters)})"
        }, timeout=7200)
        
        logger.info("📝 [STEP 4/4] 장면 생성 및 DB 저장 시작...")
        
        created_characters = []
        for i, char_data in enumerate(final_characters):
            # 진행 상황 업데이트
            script_cache.set(task_key, {
                "status": "PROCESSING",
                "book_id": book_id,
                "book_title": book.title,
                "step": "scene_generation",
                "total_characters": len(final_characters),
                "processed_characters": i,
                "current_character": char_data['characterName'],
                "started_at": datetime.datetime.now().isoformat(),
                "message": f"장면 생성 및 저장 중... ({i}/{len(final_characters)}) - {char_data['characterName']}"
            }, timeout=7200)
            
            try:
                # 캐릭터 생성
                character = Character.objects.create(
                    characterName=char_data['characterName'],
                    isMain=char_data['isMain'],
                    age=char_data['age'],
                    gender=char_data['gender'],
                    characterDescription=char_data['characterDescription'],
                    book=book
                )
                
                # 장면 생성 (API 호출 간격 조절로 Rate Limit 방지)
                import time
                if i > 0:  # 첫 번째 캐릭터가 아닌 경우
                    print(f"⏱️ API 호출 간격 조절 - 3초 대기... ({i+1}/{len(final_characters)})")
                    time.sleep(1)
                
                scenes = create_character_scenes_with_retry(char_data, book.content)
                scene_data = []
                
                for scene_info in scenes:
                    scene = CharacterScene.objects.create(
                        character=character,
                        scene_content=scene_info.get('scene_content', ''),
                        start_page=scene_info.get('start_page', 1),
                        finish_page=scene_info.get('finish_page', 10)
                    )
                    scene_data.append({
                        'id': scene.id,
                        'scene_content': scene.scene_content,
                        'start_page': scene.start_page,
                        'finish_page': scene.finish_page,
                    })
                
                created_characters.append({
                    'id': character.id,
                    'characterName': character.characterName,
                    'isMain': character.isMain,
                    'age': character.age,
                    'gender': character.gender,
                    'characterDescription': character.characterDescription,
                    'scenes': scene_data,
                    'discoveryCount': char_data.get('discoveryCount', 1),
                    'chunkSources': char_data.get('chunkSources', [])
                })
                
                logger.info(f"✅ 캐릭터 '{character.characterName}' 생성 완료 - {len(scene_data)}개 장면")
                
            except Exception as e:
                logger.error(f"❌ 캐릭터 '{char_data['characterName']}' 생성 실패: {str(e)}")
                continue
        
        # 6. 완료 상태 저장
        script_cache.set(task_key, {
            "status": "COMPLETED",
            "book_id": book_id,
            "book_title": book.title,
            "total_characters": len(created_characters),
            "characters": created_characters,
            "processing_stats": {
                "total_chunks_processed": len(selected_chunks),
                "total_chunks_available": len(chunks),
                "characters_found": len(final_characters),
                "characters_saved": len(created_characters),
                "optimal_chunk_size": optimal_chunk_size
            },
            "started_at": datetime.datetime.now().isoformat(),
            "completed_at": datetime.datetime.now().isoformat(),
            "message": f"캐릭터 생성이 완료되었습니다. 총 {len(created_characters)}명의 캐릭터가 생성되었습니다."
        }, timeout=7200)
        
        logger.info(f"✅ [TASK COMPLETE] 캐릭터 생성 완료 - Task ID: {task_id}, 캐릭터 수: {len(created_characters)}")
        
        return {
            "status": "success",
            "task_id": task_id,
            "book_id": book_id,
            "characters_created": len(created_characters),
            "total_chunks_processed": len(selected_chunks)
        }
        
    except Book.DoesNotExist:
        error_msg = f"책을 찾을 수 없습니다 - ID: {book_id}"
        logger.error(f"❌ [ERROR] {error_msg}")
        
        # 실패 상태 저장
        script_cache.set(task_key, {
            "status": "FAILED",
            "book_id": book_id,
            "started_at": datetime.datetime.now().isoformat(),
            "failed_at": datetime.datetime.now().isoformat(),
            "error_message": error_msg
        }, timeout=7200)
        
        return {"status": "error", "message": error_msg}
    
    except Exception as e:
        error_msg = f"캐릭터 생성 중 오류 발생: {str(e)}"
        logger.error(f"❌ [ERROR] {error_msg}")
        logger.error(f"❌ [ERROR] 오류 타입: {type(e).__name__}")
        
        # 실패 상태 저장
        script_cache.set(task_key, {
            "status": "FAILED",
            "book_id": book_id,
            "started_at": datetime.datetime.now().isoformat(),
            "failed_at": datetime.datetime.now().isoformat(),
            "error_message": error_msg
        }, timeout=7200)
        
        import traceback
        logger.error(f"❌ [ERROR] 상세 스택 트레이스:\n{traceback.format_exc()}")
        
        # Celery에 실패 상태 전달
        self.update_state(
            state='FAILURE',
            meta={'error': error_msg, 'task_id': task_id}
        )
        raise Exception(error_msg) 