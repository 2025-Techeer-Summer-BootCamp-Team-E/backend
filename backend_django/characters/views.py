from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
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
    ScriptGenerateResponseSerializer
)

''' 캐릭터 생성 혹은 조회 기능 '''
class CharacterConditionalCreateOrListView(APIView):
    """
    POST /characters/books/{bookId}
    캐릭터가 존재하면 목록 조회, 없으면 새로 생성하는 함수
    """
    @swagger_auto_schema(
        operation_description="""책의 캐릭터들을 조회하거나 생성합니다.
        
        - 캐릭터가 이미 존재하면: 기존 캐릭터 목록 반환 (200)
        - 캐릭터가 없으면: Gemini API로 새로 생성 (201)
        
        가능한 오류:
        - 404: 책을 찾을 수 없음
        - 500: Gemini API 호출 실패, DB 저장 실패
        """,
        responses={
            200: CharacterSerializer(many=True),
            201: CharacterSerializer(many=True),
            404: CharacterErrorResponseSerializer,
            500: CharacterDetailedErrorResponseSerializer
        },
        tags=['캐릭터 관리']
    )
    def post(self, request, book_id):
        try:
            book = Book.objects.get(id=book_id)
        except Book.DoesNotExist:
            return Response({'error': 'Book not found'}, status=404)

        existing_characters = Character.objects.filter(book=book, is_deleted=False)
        if existing_characters.exists():
            data = []
            for character in existing_characters:
                # 기존 캐릭터의 장면 정보도 함께 조회
                scenes = CharacterScene.objects.filter(character=character, is_deleted=False)
                scene_data = [
                    {
                        'id': scene.id,
                        'scene_content': scene.scene_content,
                        'start_page': scene.start_page,
                        'finish_page': scene.finish_page,
                    }
                    for scene in scenes
                ]
                
                data.append({
                    'id': character.id,
                    'characterName': character.characterName,
                    'isMain': character.isMain,
                    'age': character.age,
                    'gender': character.gender,
                    'characterDescription': character.characterDescription,
                    'scenes': scene_data
                })
            return Response(data, status=200)

        # Gemini API 호출로 캐릭터 생성 (새로운 방식)
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

        return Response(created_characters, status=201)


''' 대본 생성 기능 '''
class ScriptGenerateView(APIView):
    @swagger_auto_schema(
        operation_description="""캐릭터의 대본을 생성합니다.
        
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
        - 404: 캐릭터를 찾을 수 없음
        - 500: Gemini API 호출 실패, Redis 캐싱 실패
        """,
        responses={
            201: ScriptGenerateResponseSerializer,
            404: CharacterErrorResponseSerializer,
            500: CharacterDetailedErrorResponseSerializer
        },
        tags=['대본 생성']
    )
    def post(self, request, character_id):
        try:
            character = Character.objects.get(id=character_id, is_deleted=False)
        except Character.DoesNotExist:
            return Response({'error': 'Character not found'}, status=404)

        # 장면 개수 결정
        desc_length = len(character.characterDescription)
        scene_count = 3

        # 조연 캐릭터 정보 수집
        sub_characters = Character.objects.filter(
            book=character.book, isMain=False, is_deleted=False
        ).exclude(id=character.id)

        # Gemini 호출
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
                    "lines": scene.get("lines"),
                    "rewriting_prompt": scene.get("rewriting_prompt"),
                    "rewriting_id": scene.get("rewriting_id")  # 이미 파싱 함수에서 생성됨
                })

            # ✅ Redis에 script_id 기준으로 저장
            cache_key = f"script:{script_id}"
            script_cache = caches['script_cache']
            script_cache.set(cache_key, {
                "characterId": character_id,
                "scenes": generated_scenes
            }, timeout=1000)

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
