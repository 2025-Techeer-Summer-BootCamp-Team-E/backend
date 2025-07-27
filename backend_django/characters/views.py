# characters/views.py

from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated  # JWT 인증 추가
from django.core.cache import caches
from .gemini_client import (
    generate_scenes_with_gemini,
    generate_characters_with_gemini,
    parse_scene_list,
    parse_character_list
)
import uuid
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Character, CharacterScene
from books.models import Book
from .serializers import (
    CharacterSerializer,
    CharacterErrorResponseSerializer,
    CharacterDetailedErrorResponseSerializer,
    ScriptGenerateResponseSerializer,
    ScriptAsyncResponseSerializer,
    ScriptTaskStatusResponseSerializer,
    CharacterAsyncResponseSerializer,
    CharacterTaskStatusResponseSerializer
)

''' 캐릭터 생성 혹은 조회 기능 '''
class CharacterConditionalCreateOrListView(APIView):
    """
    POST /characters/books/{bookId}
    캐릭터가 존재하면 목록 조회, 없으면 새로 생성하는 함수
    """
    permission_classes = [IsAuthenticated]  # JWT 인증 필요
    
    @swagger_auto_schema(
        operation_description="""책의 캐릭터들을 조회하거나 생성합니다. (JWT 인증 필요)
        
        - 캐릭터가 이미 존재하면: 기존 캐릭터 목록 반환 (200)
        - 캐릭터가 없으면: Gemini API로 새로 생성 (201)
        
        생성 제한사항:
        - 최대 10명까지 생성 (주인공 우선순위)
        - 중복 캐릭터 자동 병합
        
        가능한 오류:
        - 401: 인증 필요
        - 404: 책을 찾을 수 없음
        - 500: Gemini API 호출 실패, DB 저장 실패
        """,
        responses={
            200: CharacterSerializer(many=True),
            201: CharacterSerializer(many=True),
            401: openapi.Response(description="인증 필요"),
            404: CharacterErrorResponseSerializer,
            500: CharacterDetailedErrorResponseSerializer
        },
        tags=['캐릭터 관리']
    )
    def post(self, request, book_id):
        # print(f"🎭 인증된 사용자 {request.user.username}이 책 ID {book_id}의 캐릭터 조회/생성 요청")
        
        try:
            book = Book.objects.get(id=book_id)
        except Book.DoesNotExist:
            return Response({'error': 'Book not found'}, status=404)

        existing_characters = Character.objects.filter(book=book, is_deleted=False)
        if existing_characters.exists():
            # print(f"✅ 기존 캐릭터 {existing_characters.count()}개 발견, 목록 반환 (scenes 제외)")
            from .serializers import CharacterSimpleSerializer
            serializer = CharacterSimpleSerializer(existing_characters, many=True)
            return Response(serializer.data, status=200)

        # Gemini API 호출로 캐릭터 생성 (새로운 방식)
        # print(f"🤖 캐릭터가 없어서 Gemini API로 새로 생성 시작")
        try:
            character_data_list = generate_characters_with_gemini(book_id)
        except Exception as e:
            return Response({
                'status': 'error',
                'error_code': 500,
                'message': f'Gemini API 호출 실패: {str(e)}'
            }, status=500)

        # 캐릭터 및 장면 저장
        created_characters = []
        for data in character_data_list:
            try:
                # 캐릭터 생성
                character = Character.objects.create(
                    characterName=data.get('characterName'),
                    isMain=data.get('isMain', False),
                    age=data.get('age'),
                    gender=data.get('gender'),
                    characterDescription=data.get('characterDescription'),
                    book=book
                )
                
                # 캐릭터 장면 생성
                scene_data = []
                scenes = data.get('scenes', [])
                for scene_info in scenes:
                    scene = CharacterScene.objects.create(
                        character=character,
                        scene_content=scene_info.get('scene_content'),
                        start_page=scene_info.get('start_page'),
                        finish_page=scene_info.get('finish_page')
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
                    'scenes': scene_data
                })
            except Exception as e:
                print(f"⚠️ 캐릭터 또는 장면 저장 실패: {e}")
                continue

        # print(f"✅ 새로운 캐릭터 {len(created_characters)}개 생성 완료")
        return Response(created_characters, status=201)


''' 대본 생성 기능 '''
class ScriptGenerateView(APIView):
    permission_classes = [IsAuthenticated]  # JWT 인증 필요
    
    @swagger_auto_schema(
        operation_description="""캐릭터의 대본을 생성합니다. (JWT 인증 필요)
        
        처리 과정:
        1. 캐릭터 정보 조회
        2. 조연 캐릭터 정보 수집
        3. Gemini API로 대본 생성
        4. Redis에 대본 캐싱
        
        생성되는 대본:
        - 3개의 연속된 장면
        - 각 장면은 background, mood, style, camera, soundtrack 등 포함
        - 각 장면은 1-2명의 캐릭터와 대화 포함
        
        가능한 오류:
        - 401: 인증 필요
        - 404: 캐릭터를 찾을 수 없음
        - 500: Gemini API 호출 실패, Redis 캐싱 실패
        """,
        responses={
            201: ScriptGenerateResponseSerializer,
            401: openapi.Response(description="인증 필요"),
            404: CharacterErrorResponseSerializer,
            500: CharacterDetailedErrorResponseSerializer
        },
        tags=['대본 생성']
    )
    def post(self, request, character_id):
        # print(f"📝 인증된 사용자 {request.user.username}이 캐릭터 ID {character_id}의 대본 생성 요청")
        
        try:
            character = Character.objects.get(id=character_id, is_deleted=False)
        except Character.DoesNotExist:
            return Response({'error': 'Character not found'}, status=404)

        # 장면 개수 결정
        # desc_length = len(character.characterDescription)
        scene_count = 3

        # 조연 캐릭터 정보 수집
        sub_characters = Character.objects.filter(
            book=character.book, isMain=False, is_deleted=False
        ).exclude(id=character.id)

        # Gemini 호출
        # print(f"🤖 Gemini API로 대본 생성 시작 - 주인공: {character.characterName}")
        try:
            raw_text = generate_scenes_with_gemini(
                main_character=character,
                sub_characters=sub_characters,
                scene_count=scene_count,
            )
        except Exception as e:
            return Response({
                'status': 'error',
                'error_code': 500,
                'message': f'Gemini 호출 실패: {str(e)}'
            }, status=500)

        # 파싱 및 Redis 캐시 저장
        try:
            parsed_result = parse_scene_list(raw_text)
            
            # parse_scene_list는 이제 {script_id: "...", scenes: [...]} 형태로 반환
            script_id = parsed_result.get("script_id")
            scene_texts = parsed_result.get("scenes", [])

            # ✅ scene 구조 생성
            generated_scenes = []
            for scene in scene_texts:
                scene_id = scene.get("sceneId")  # "scene" → "sceneId"로 수정
                generated_scenes.append({
                    "sceneId": scene_id,
                    "background": scene.get("background"),
                    "mood": scene.get("mood"),
                    "style": scene.get("style"),
                    "camera": scene.get("camera"),
                    "soundtrack": scene.get("soundtrack"),
                    "characters": scene.get("characters"),
                    # "lines": scene.get("lines"),
                    "rewriting_prompt": scene.get("rewriting_prompt"),
                    "rewriting_id": scene.get("rewriting_id")  # 이미 파싱 함수에서 생성됨
                })

            # ✅ Redis에 script_id 기준으로 저장
            cache_key = f"script:{script_id}"
            script_cache = caches['script_cache']
            script_cache.set(cache_key, {
                "characterId": character_id,
                "scenes": generated_scenes
            }, timeout=2000) # 2000초 동안 캐시

            # print(f"✅ 대본 생성 및 캐싱 완료 - Script ID: {script_id}")

            return Response({
                "script_id": script_id,
                "characterId": character_id,
                "scenes": generated_scenes
            }, status=201)

        except Exception as e:
            return Response({
                'status': 'error',
                'error_code': 500,
                'message': f'응답 파싱 또는 캐싱 실패: {str(e)}'
            }, status=500)



''' 대본 생성 기능 (비동기 버전) '''
class ScriptGenerateAsyncView(APIView):
    permission_classes = [IsAuthenticated]  # JWT 인증 필요
    
    @swagger_auto_schema(
        operation_description="""캐릭터의 대본을 비동기적으로 생성합니다. (JWT 인증 필요)
        
        처리 과정:
        1. 즉시 ScriptTask 레코드 생성 및 응답 반환
        2. 백그라운드에서 대본 처리:
           - 캐릭터 정보 조회
           - 조연 캐릭터 정보 수집
           - Gemini API로 대본 생성
           - Redis에 대본 캐싱
           - DB에 최종 정보 업데이트
        
        가능한 오류:
        - 401: 인증 필요
        - 404: 캐릭터를 찾을 수 없음
        - 500: 초기 처리 실패
        """,
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'scene_count': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="생성할 장면 수 (기본값: 3)",
                    default=3
                )
            }
        ),
        responses={
            202: ScriptAsyncResponseSerializer,
            401: openapi.Response(description="인증 필요"),
            404: CharacterErrorResponseSerializer,
            500: CharacterDetailedErrorResponseSerializer
        },
        tags=['대본 생성']
    )
    def post(self, request, character_id):
        print("📝 비동기 대본 생성 요청 시작")
        print("👤 요청 사용자:", request.user.username if request.user.is_authenticated else "익명")
        
        try:
            character = Character.objects.get(id=character_id, is_deleted=False)
        except Character.DoesNotExist:
            return Response({'error': 'Character not found'}, status=404)

        # 장면 수 파라미터 (기본값: 3)
        scene_count = int(request.data.get('scene_count', 3))
        
        print(f"✅ 검증 완료 - 캐릭터: {character.characterName}, 장면 수: {scene_count}")

        try:
            # 🆔 script_id 미리 생성 (클라이언트가 즉시 받을 수 있도록)
            import uuid
            script_id = str(uuid.uuid4())
            
            # 1. Celery 태스크 시작 (script_id 전달)
            from .tasks import generate_script_task
            task = generate_script_task.delay(
                character_id=character_id,
                scene_count=scene_count,
                script_id=script_id  # 미리 생성된 script_id 전달
            )
            
            print(f"🚀 비동기 처리 시작 - Task ID: {task.id}, Script ID: {script_id}")

            # 2. 즉시 응답 반환 (script_id 포함)
            return Response({
                "task_id": task.id,
                "script_id": script_id,  # 🔑 클라이언트가 즉시 받을 script_id
                "character_id": character_id,
                "character_name": character.characterName,
                # "scene_count": scene_count,
                "message": f"대본 생성이 시작되었습니다. Script ID: {script_id} (영상 생성에 사용 가능)"
            }, status=202)  # 202 Accepted

        except Exception as e:
            print(f"[ERROR] 초기 처리 중 오류 발생: {str(e)}")
            print(f"[ERROR] 오류 타입: {type(e).__name__}")
            import traceback
            print(f"[ERROR] 상세 스택 트레이스:\n{traceback.format_exc()}")

            return Response({
                'status': 'error',
                'error_code': 500,
                'message': f'초기 처리 중 오류가 발생했습니다: {str(e)}'
            }, status=500)


# ''' 대본 생성 상태 확인 기능 (Polling 방식 - 더 이상 사용 안함) '''
# class ScriptTaskStatusView(APIView):
#     """
#     대본 생성 작업 상태를 확인하는 API (Redis 기반)
#     """
#     permission_classes = [IsAuthenticated]

#     @swagger_auto_schema(
#         operation_description="""대본 생성 작업 상태를 확인합니다. (JWT 인증 필요)
        
#         처리 상태:
#         - PROCESSING: 처리 진행 중  
#         - COMPLETED: 처리 완료 (script_id로 Redis에서 대본 조회 가능)
#         - FAILED: 처리 실패
#         """,
#         responses={
#             200: ScriptTaskStatusResponseSerializer,
#             404: CharacterErrorResponseSerializer,
#             401: openapi.Response(description="인증 필요")
#         },
#         tags=['대본 생성']
#     )
#     def get(self, request, task_id):
#         script_cache = caches['script_cache']
#         task_key = f"task:{task_id}"
        
#         try:
#             # Redis에서 태스크 상태 조회
#             task_data = script_cache.get(task_key)
            
#             if not task_data:
#                 return Response({
#                     "error": "태스크를 찾을 수 없습니다. 태스크가 만료되었거나 존재하지 않습니다."
#                 }, status=404)
            
#             # 응답 데이터 구성
#             response_data = {
#                 "task_id": task_id,
#                 "character_id": task_data.get("character_id"),
#                 "character_name": task_data.get("character_name"),
#                 "status": task_data.get("status"),
#                 "script_id": task_data.get("script_id"),
#                 "scene_count": task_data.get("scene_count"),
#                 "error_message": task_data.get("error_message"),
#                 "message": task_data.get("message"),
#                 "started_at": task_data.get("started_at"),
#                 "completed_at": task_data.get("completed_at"),
#                 "failed_at": task_data.get("failed_at")
#             }
            
#             # 🎬 완료된 경우 대본 내용도 함께 반환
#             if task_data.get("status") == "COMPLETED" and task_data.get("script_id"):
#                 script_id = task_data.get("script_id")
#                 script_key = f"script:{script_id}"
#                 script_data = script_cache.get(script_key)
                
#                 if script_data:
#                     response_data["scenes"] = script_data.get("scenes", [])
#                     print(f"📋 대본 내용도 함께 반환 - Script ID: {script_id}, 장면 수: {len(script_data.get('scenes', []))}")
#                 else:
#                     print(f"⚠️ 대본 데이터를 찾을 수 없음 - Script ID: {script_id}")
#                     response_data["error_message"] = "대본 데이터가 만료되었거나 찾을 수 없습니다."
            
#             print(f"📊 대본 작업 상태 조회 - Task ID: {task_id}, 상태: {task_data.get('status')}")
#             return Response(response_data, status=200)
            
#         except Exception as e:
#             print(f"[ERROR] 상태 조회 중 오류: {str(e)}")
#             return Response({
#                 "error": f"상태 조회 중 오류가 발생했습니다: {str(e)}"
#             }, status=500)


''' 캐릭터 생성 기능 (비동기 버전) '''
class CharacterGenerateAsyncView(APIView):
    permission_classes = [IsAuthenticated]  # JWT 인증 필요
    
    @swagger_auto_schema(
        operation_description="""책의 캐릭터들을 비동기적으로 생성합니다. (JWT 인증 필요)
        
        조건부 생성 로직:
        - 캐릭터가 이미 존재하면: 기존 캐릭터 목록 반환 (200)
        - 캐릭터가 없으면: 백그라운드에서 비동기 생성 (202)
        
        고급 처리 과정 (생성 시):
        1. 즉시 Task ID 반환
        2. 백그라운드에서 스마트 처리:
           - PDF 다운로드 및 스마트 청킹 (페이지 크기에 따른 적응적 분할)
           - 캐릭터 우선순위 기반 청크 선별
           - 청크별 병렬 캐릭터 추출 (에러 재시도 포함)
           - 중복 제거 및 스마트 병합
           - 캐릭터 수 제한 (최대 10명, 주인공 우선)
           - 캐릭터별 장면 생성 및 DB 저장
        
        대형 PDF 대응 기능:
        - 600페이지+ 파일 지원
        - 컨텍스트 한계 회피를 위한 청킹
        - Gemini API 500 에러 자동 재시도
        - 메모리 효율적 처리
        
        가능한 오류:
        - 401: 인증 필요
        - 404: 책을 찾을 수 없음
        - 409: 이미 캐릭터가 존재함
        - 500: 초기 처리 실패
        """,
        responses={
            200: openapi.Response(
                description="기존 캐릭터 목록 반환",
                examples={
                    "application/json": {
                        "message": "이미 5개의 캐릭터가 존재합니다.",
                        "book_id": 1,
                        "book_title": "카라마조프가의 형제들",
                        "total_characters": 5,
                        "characters": "캐릭터 목록"
                    }
                }
            ),
            202: CharacterAsyncResponseSerializer,
            401: openapi.Response(description="인증 필요"),
            404: CharacterErrorResponseSerializer,
            409: openapi.Response(description="이미 캐릭터가 존재함"),
            500: CharacterDetailedErrorResponseSerializer
        },
        tags=['캐릭터 관리']
    )
    def post(self, request, book_id):
        print("🎭 비동기 캐릭터 생성 요청 시작")
        print("👤 요청 사용자:", request.user.username if request.user.is_authenticated else "익명")
        
        try:
            book = Book.objects.get(id=book_id)
        except Book.DoesNotExist:
            return Response({'error': 'Book not found'}, status=404)

        # 🔄 조건부 생성: 기존 캐릭터 존재 여부 확인
        existing_characters = Character.objects.filter(book=book, is_deleted=False)
        if existing_characters.exists():
            print(f"✅ 기존 캐릭터 {existing_characters.count()}개 발견, 목록 반환 (scenes 제외)")
            from .serializers import CharacterSimpleSerializer
            serializer = CharacterSimpleSerializer(existing_characters, many=True)
            return Response({
                "message": f"이미 {existing_characters.count()}개의 캐릭터가 존재합니다.",
                "book_id": book_id,
                "book_title": book.title,
                "total_characters": existing_characters.count(),
                "characters": serializer.data
            }, status=200)  # 409 대신 200으로 기존 데이터 반환

        print(f"✅ 검증 완료 - 책: {book.title}")

        try:
            # 1. Celery 태스크 시작
            from .tasks import generate_characters_task
            task = generate_characters_task.delay(book_id=book_id)
            
            print(f"🚀 비동기 처리 시작 - Task ID: {task.id}")

            # 2. 즉시 응답 반환
            return Response({
                "task_id": task.id,
                "book_id": book_id,
                "book_title": book.title,
                "message": "캐릭터 생성이 시작되었습니다. 실시간 처리 상태는 EventStream을 통해 확인 가능합니다: GET /books/{book_id}/eventstream/characters"
            }, status=202)  # 202 Accepted

        except Exception as e:
            print(f"[ERROR] 초기 처리 중 오류 발생: {str(e)}")
            print(f"[ERROR] 오류 타입: {type(e).__name__}")
            import traceback
            print(f"[ERROR] 상세 스택 트레이스:\n{traceback.format_exc()}")

            return Response({
                'status': 'error',
                'error_code': 500,
                'message': f'초기 처리 중 오류가 발생했습니다: {str(e)}'
            }, status=500)


# ''' 캐릭터 생성 상태 확인 기능 (Polling 방식 - 더 이상 사용 안함) '''
# class CharacterTaskStatusView(APIView):
#     """
#     캐릭터 생성 작업 상태를 확인하는 API (Redis 기반)
#     """
#     permission_classes = [IsAuthenticated]

#     @swagger_auto_schema(
#         operation_description="""캐릭터 생성 작업 상태를 확인합니다. (JWT 인증 필요)
        
#         처리 상태 및 단계:
#         - PROCESSING: 처리 진행 중
#           - initialization: 초기화
#           - pdf_processing: PDF 다운로드 및 청킹
#           - character_extraction: 청크별 캐릭터 추출
#           - character_merging: 캐릭터 병합 및 중복 제거
#           - scene_generation: 장면 생성 및 DB 저장
#         - COMPLETED: 처리 완료 (생성된 캐릭터 목록 포함)
#         - FAILED: 처리 실패
        
#         진행률 정보:
#         - 각 단계별 진행 상황 (청크 처리, 캐릭터 생성 등)
#         - 현재 처리 중인 항목 정보
#         - 예상 완료 시간 추정 가능
#         """,
#         responses={
#             200: CharacterTaskStatusResponseSerializer,
#             404: CharacterErrorResponseSerializer,
#             401: openapi.Response(description="인증 필요")
#         },
#         tags=['캐릭터 관리']
#     )
#     def get(self, request, task_id):
#         script_cache = caches['script_cache']
#         task_key = f"character_task:{task_id}"
        
#         try:
#             # Redis에서 태스크 상태 조회
#             task_data = script_cache.get(task_key)
            
#             if not task_data:
#                 return Response({
#                     "error": "태스크를 찾을 수 없습니다. 태스크가 만료되었거나 존재하지 않습니다."
#                 }, status=404)
            
#             # 응답 데이터 구성
#             response_data = {
#                 "task_id": task_id,
#                 "book_id": task_data.get("book_id"),
#                 "book_title": task_data.get("book_title"),
#                 "status": task_data.get("status"),
#                 "step": task_data.get("step"),
#                 "message": task_data.get("message"),
                
#                 # 진행률 정보
#                 "total_chunks": task_data.get("total_chunks"),
#                 "processed_chunks": task_data.get("processed_chunks"),
#                 "current_chunk": task_data.get("current_chunk"),
#                 "total_characters": task_data.get("total_characters"),
#                 "processed_characters": task_data.get("processed_characters"),
#                 "current_character": task_data.get("current_character"),
                
#                 # 시간 정보
#                 "started_at": task_data.get("started_at"),
#                 "completed_at": task_data.get("completed_at"),
#                 "failed_at": task_data.get("failed_at"),
#                 "error_message": task_data.get("error_message")
#             }
            
#             # 🎭 완료된 경우 캐릭터 목록과 통계도 함께 반환
#             if task_data.get("status") == "COMPLETED":
#                 response_data["characters"] = task_data.get("characters", [])
#                 response_data["processing_stats"] = task_data.get("processing_stats", {})
#                 print(f"🎭 캐릭터 목록도 함께 반환 - Task ID: {task_id}, 캐릭터 수: {len(task_data.get('characters', []))}")
            
#             print(f"📊 캐릭터 작업 상태 조회 - Task ID: {task_id}, 상태: {task_data.get('status')}, 단계: {task_data.get('step')}")
#             return Response(response_data, status=200)
            
#         except Exception as e:
#             print(f"[ERROR] 상태 조회 중 오류: {str(e)}")
#             return Response({
#                 "error": f"상태 조회 중 오류가 발생했습니다: {str(e)}"
#             }, status=500)

