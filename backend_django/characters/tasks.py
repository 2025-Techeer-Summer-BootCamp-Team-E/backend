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
# from books.eventstream_views import notify_character_progress, notify_character_completed, notify_script_progress, notify_script_completed
import datetime

# Celery 전용 로거 설정
logger = get_task_logger(__name__)


@shared_task(bind=True)
def generate_script_task(self, character_id, scene_count=3, script_id=None):
    """
    대본을 비동기적으로 생성하는 Celery 태스크 (Redis 기반)
    
    Args:
        character_id: Character ID
        scene_count: 생성할 장면 수
        script_id: 미리 생성된 Script ID (없으면 자동 생성)
    """
    task_id = self.request.id
    script_cache = caches['script_cache']
    
    # 🆔 script_id 처리 (미리 제공되지 않으면 생성)
    if not script_id:
        import uuid
        script_id = str(uuid.uuid4())
    
    # Redis에 태스크 상태 저장
    task_key = f"task:{task_id}"
    script_key = f"script:{script_id}"
    
    try:
        # 1. 초기 상태 저장 (script_id 포함)
        init_data = {
            "status": "PROCESSING",
            "character_id": character_id,
            "scene_count": scene_count,
            "script_id": script_id,  # 🔑 즉시 script_id 저장
            "started_at": datetime.datetime.now().isoformat(),
            "message": "대본 생성 중..."
        }
        script_cache.set(task_key, init_data, timeout=3600)  # 1시간
        
        # script:{script_id} 키에도 초기 상태 저장 (EventStream용)
        script_init_data = {
            "character_id": character_id,
            "characterId": character_id,  # 호환성
            "character_name": "",  # 나중에 Character 조회 후 업데이트
            "script_id": script_id,
            "status": "PROCESSING",
            "started_at": datetime.datetime.now().isoformat(),
            "message": "대본 생성 중...",
            "scene_count": scene_count,
            "scenes": []  # 빈 장면 리스트로 시작
        }
        script_cache.set(script_key, script_init_data, timeout=2000)
        
        # 📡 실시간 알림: 대본 생성 시작 (중복 키 제거)
        # init_data_for_notify = {k: v for k, v in init_data.items() if k not in ['status', 'script_id']}
        # notify_script_progress(script_id, "PROCESSING", **init_data_for_notify)
        
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
        gemini_data = {
            "status": "PROCESSING",
            "character_id": character_id,
            "character_name": character.characterName,
            "scene_count": scene_count,
            "started_at": datetime.datetime.now().isoformat(),
            "message": "Gemini API로 대본 생성 중..."
        }
        script_cache.set(task_key, gemini_data, timeout=3600)
        
        # 📡 실시간 알림: AI 대본 생성 중 (중복 키 제거)
        # gemini_data_for_notify = {k: v for k, v in gemini_data.items() if k not in ['status']}
        # notify_script_progress(script_id, "PROCESSING", **gemini_data_for_notify)
        
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
        
        # 🆔 미리 생성된 script_id 사용 (파싱된 것 무시)
        scene_texts = parsed_result.get("scenes", [])
        logger.info(f"🔍 [PARSING] 파싱 완료 - Script ID: {script_id} (미리 생성됨), 장면 수: {len(scene_texts)}")
        
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
        
        # 대본을 Redis에 저장 (상태 정보 포함)
        script_cache_key = f"script:{script_id}"
        script_cache.set(script_cache_key, {
            "characterId": character_id,
            "character_id": character_id,  # 호환성을 위해 두 형태 모두 저장
            "character_name": character.characterName,
            "scenes": generated_scenes,
            "scene_count": len(generated_scenes),
            "script_id": script_id,
            "status": "COMPLETED",
            "started_at": datetime.datetime.now().isoformat(),
            "completed_at": datetime.datetime.now().isoformat(),
            "message": "대본 생성이 완료되었습니다."
        }, timeout=2000)  # 2000초 동안 캐시
        logger.info(f"💾 [CACHE] Redis 대본 캐싱 완료 - Key: {script_cache_key}")
        
        # 4. 완료 상태 저장
        completed_data = {
            "status": "COMPLETED",
            "character_id": character_id,
            "character_name": character.characterName,
            "scene_count": scene_count,
            "script_id": script_id,
            "started_at": datetime.datetime.now().isoformat(),
            "completed_at": datetime.datetime.now().isoformat(),
            "message": "대본 생성이 완료되었습니다."
        }
        script_cache.set(task_key, completed_data, timeout=3600)
        
        # 📡 실시간 알림: 대본 생성 완료 (Redis 데이터 포함)
        # Redis에서 완전한 대본 데이터 가져오기
        full_script_data = script_cache.get(script_cache_key)
        
        # notify_script_completed(script_id, {
        #     "script_id": script_id,
        #     "character_id": character_id,
        #     "character_name": character.characterName,
        #     "scene_count": len(generated_scenes),
        #     "scenes": full_script_data.get("scenes", []) if full_script_data else generated_scenes,
        #     # Redis에서 가져온 완전한 대본 데이터
        #     "redis_data": full_script_data,
        #     "processing_stats": {
        #         "total_scenes": len(generated_scenes),
        #         "generation_time": (datetime.datetime.now() - datetime.datetime.fromisoformat(completed_data["started_at"])).total_seconds()
        #     }
        # })
        
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
        error_data = {
            "status": "FAILED",
            "character_id": character_id,
            "scene_count": scene_count,
            "started_at": datetime.datetime.now().isoformat(),
            "failed_at": datetime.datetime.now().isoformat(),
            "error_message": error_msg
        }
        script_cache.set(task_key, error_data, timeout=3600)
        
        # 📡 실시간 알림: 대본 생성 실패 (중복 키 제거)
        # error_data_for_notify = {k: v for k, v in error_data.items() if k not in ['status']}
        # notify_script_progress(script_id, "FAILED", **error_data_for_notify)
        
        return {"status": "error", "message": error_msg}
    
    except Exception as e:
        error_msg = f"대본 생성 중 오류 발생: {str(e)}"
        logger.error(f"❌ [ERROR] {error_msg}")
        logger.error(f"❌ [ERROR] 오류 타입: {type(e).__name__}")
        
        # 실패 상태 저장
        error_data = {
            "status": "FAILED",
            "character_id": character_id,
            "scene_count": scene_count,
            "started_at": datetime.datetime.now().isoformat(),
            "failed_at": datetime.datetime.now().isoformat(),
            "error_message": error_msg
        }
        script_cache.set(task_key, error_data, timeout=3600)
        
        # 📡 실시간 알림: 대본 생성 실패 (중복 키 제거)
        # error_data_for_notify = {k: v for k, v in error_data.items() if k not in ['status']}
        # notify_script_progress(script_id, "FAILED", **error_data_for_notify)
        
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
        init_data = {
            "status": "PROCESSING",
            "book_id": book_id,
            "step": "initialization",
            "started_at": datetime.datetime.now().isoformat(),
            "message": "캐릭터 생성 초기화 중..."
        }
        script_cache.set(task_key, init_data, timeout=7200)  # 2시간
        
        # 📡 실시간 알림: 초기화 시작
        # notify_character_progress(book_id, task_id, "initialization", init_data)
        
        logger.info(f"🎭 [TASK START] 캐릭터 생성 시작 - Book ID: {book_id}, Task ID: {task_id}")
        
        # Book 조회
        book = Book.objects.get(id=book_id)
        logger.info(f"📚 [BOOK] 책 정보 로드 - 제목: '{book.title}'")
        
        # 2. PDF 다운로드 및 청킹
        pdf_data = {
            "status": "PROCESSING",
            "book_id": book_id,
            "book_title": book.title,
            "step": "pdf_processing",
            "started_at": datetime.datetime.now().isoformat(),
            "message": "PDF 다운로드 및 청킹 중..."
        }
        script_cache.set(task_key, pdf_data, timeout=7200)
        
        # 📡 실시간 알림: PDF 처리 시작
        # notify_character_progress(book_id, task_id, "pdf_processing", pdf_data)
        
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
        
        # 🎭 캐릭터 10명 제한 (주인공 우선순위 유지)
        if len(final_characters) > 10:
            logger.info(f"📊 캐릭터 수 제한: {len(final_characters)}명 → 10명 (주인공 우선)")
            final_characters = final_characters[:10]  # 이미 주인공 우선, 이름순으로 정렬되어 있음
        
        logger.info(f"✅ 최종 선택된 캐릭터 수: {len(final_characters)}명")
        
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
            scene_progress = {
                "status": "PROCESSING",
                "book_id": book_id,
                "book_title": book.title,
                "step": "scene_generation",
                "total_characters": len(final_characters),
                "processed_characters": i,
                "current_character": char_data['characterName'],
                "started_at": datetime.datetime.now().isoformat(),
                "message": f"장면 생성 및 저장 중... ({i+1}/{len(final_characters)}) - {char_data['characterName']}"
            }
            script_cache.set(task_key, scene_progress, timeout=7200)
            
            # 📡 실시간 알림: 장면 생성 진행
            # notify_character_progress(book_id, task_id, "scene_generation", scene_progress)
            
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
                    'characterDescription': character.characterDescription
                    # 'scenes': scene_data,  # EventStream에서는 scenes 제외 (응답 크기 최적화)
                    # 'discoveryCount': char_data.get('discoveryCount', 1),  # 내부 처리 정보 제외
                    # 'chunkSources': char_data.get('chunkSources', [])      # 내부 처리 정보 제외
                })
                
                logger.info(f"✅ 캐릭터 '{character.characterName}' 생성 완료 - {len(scene_data)}개 장면")
                
            except Exception as e:
                logger.error(f"❌ 캐릭터 '{char_data['characterName']}' 생성 실패: {str(e)}")
                continue
        
        # 6. 완료 상태 저장
        completed_data = {
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
        }
        script_cache.set(task_key, completed_data, timeout=7200)
        
        # 📡 실시간 알림: 캐릭터 생성 완료
        # notify_character_completed(book_id, task_id, created_characters)
        
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
        error_data = {
            "status": "FAILED",
            "book_id": book_id,
            "started_at": datetime.datetime.now().isoformat(),
            "failed_at": datetime.datetime.now().isoformat(),
            "error_message": error_msg
        }
        script_cache.set(task_key, error_data, timeout=7200)
        
        # 📡 실시간 알림: 캐릭터 생성 실패
        # notify_character_progress(book_id, task_id, "failed", error_data)
        
        import traceback
        logger.error(f"❌ [ERROR] 상세 스택 트레이스:\n{traceback.format_exc()}")
        
        # Celery에 실패 상태 전달
        self.update_state(
            state='FAILURE',
            meta={'error': error_msg, 'task_id': task_id}
        )
        raise Exception(error_msg) 