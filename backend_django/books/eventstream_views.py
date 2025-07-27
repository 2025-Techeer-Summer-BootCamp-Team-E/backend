"""
Django EventStream 기반 SSE 구현

기존 자체 구현(580줄) → EventStream(간단한 구조)로 전환
- 실시간 Push 알림 (폴링 제거)
- 자동 연결 관리
- Redis Pub/Sub 최적화
"""

import logging
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django_eventstream import send_event
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@swagger_auto_schema(
    operation_description="""책 PDF 처리 상태를 실시간으로 받습니다. (EventStream 방식)
    
    EventStream 장점:
    - 즉시 Push 알림 (폴링 없음)
    - 자동 연결 관리
    - Redis Pub/Sub 최적화
    - 메모리 효율적
    
    사용법:
    1. 이 API로 채널 연결
    2. EventSource로 /events/?channel=book-{book_id} 접속
    3. 실시간 알림 수신
    
    이벤트 타입:
    - status: 상태 업데이트
    - completed: 처리 완료
    - error: 오류 발생
    """,
    responses={
        200: openapi.Response(description="채널 연결 성공"),
        404: openapi.Response(description="책을 찾을 수 없음"),
        401: openapi.Response(description="인증 필요")
    },
    tags=['EventStream SSE (신규)']
)
def book_processing_eventstream(request, book_id):
    """책 처리 상태를 EventStream으로 모니터링 시작"""
    try:
        from .models import Book
        book = Book.objects.get(id=book_id, is_deleted=False)
        
        # 즉시 현재 상태 전송
        send_event(f'book-{book_id}', 'status', {
            'book_id': book.id,
            'title': book.title,
            'processing_status': book.processing_status,
            'content': book.content,
            'pdf_url': book.pdf_url,
            'error_message': book.error_message,
            'timestamp': book.updated_at.isoformat() if book.updated_at else None
        })
        
        return JsonResponse({
            'message': f'책 "{book.title}" 실시간 모니터링 시작',
            'channel': f'book-{book_id}',
            'eventstream_url': f'/events/?channel=book-{book_id}',
            'current_status': book.processing_status
        })
        
    except Book.DoesNotExist:
        return JsonResponse({
            'error': f'책 ID {book_id}를 찾을 수 없습니다.'
        }, status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@swagger_auto_schema(
    operation_description="""캐릭터 생성 상태를 실시간으로 받습니다. (EventStream 방식)
    
    book_id로 활성 캐릭터 생성 작업을 찾아 실시간 모니터링합니다.
    
    EventStream 개선사항:
    - 진행률 실시간 업데이트
    - 단계별 상세 정보
    - 자동 완료 감지
    
    사용법:
    1. 이 API로 채널 연결
    2. EventSource로 /events/?channel=character-{book_id} 접속
    3. 단계별 진행 상황 실시간 수신
    """,
    responses={
        200: openapi.Response(description="채널 연결 성공"),
        404: openapi.Response(description="활성 작업 없음"),
        401: openapi.Response(description="인증 필요")
    },
    tags=['EventStream SSE (신규)']
)
def character_generation_eventstream(request, book_id):
    """캐릭터 생성 상태를 EventStream으로 모니터링 시작"""
    try:
        from django.core.cache import caches
        from django_redis import get_redis_connection
        
        script_cache = caches['script_cache']
        redis_client = get_redis_connection("script_cache")
        
        # 활성 캐릭터 작업 찾기 (진행 중 + 완료된 작업 모두 포함)
        active_task = None
        completed_task = None
        pattern = f"*:character_task:*"
        
        for key in redis_client.scan_iter(match=pattern):
            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
            if ':character_task:' in key_str:
                task_id = key_str.split(':character_task:')[-1]
                task_data = script_cache.get(f'character_task:{task_id}')
                
                if task_data:
                    stored_book_id = task_data.get('book_id')
                    
                    # 🔍 타입 호환성 체크 (int vs str)
                    book_ids_match = False
                    try:
                        book_ids_match = (
                            stored_book_id == book_id or 
                            str(stored_book_id) == str(book_id) or
                            int(stored_book_id) == int(book_id)
                        )
                    except (ValueError, TypeError):
                        book_ids_match = str(stored_book_id) == str(book_id)
                    
                    if book_ids_match:
                        task_status = task_data.get('status')
                        if task_status in ['PENDING', 'PROCESSING']:
                            active_task = {'task_id': task_id, 'data': task_data}
                            break  # 진행 중인 작업이 우선
                        elif task_status == 'COMPLETED':
                            completed_task = {'task_id': task_id, 'data': task_data}
                            # 완료된 작업은 저장하되 계속 찾기 (진행 중인 작업이 있을 수 있음)
        
        # 진행 중인 작업이 없으면 완료된 작업 사용
        target_task = active_task or completed_task
        
        if not target_task:
            return JsonResponse({
                'error': f'책 ID {book_id}에 대한 캐릭터 생성 작업을 찾을 수 없습니다.',
                'suggestion': '먼저 /books/{book_id}/characters/async API로 캐릭터 생성을 시작하세요.',
                'note': 'Redis에서 해당 작업 데이터를 찾을 수 없습니다. 작업이 만료되었을 수 있습니다.'
            }, status=404)
        
        # 현재 상태 전송
        task_data = target_task['data']
        task_status = task_data.get('status')
        
        if task_status == 'COMPLETED':
            # ✅ 완료된 작업: 즉시 완료 데이터 반환
            # 캐릭터 데이터에서 불필요한 내부 처리 정보 제거
            raw_characters = task_data.get('characters', [])
            cleaned_characters = []
            for char in raw_characters:
                cleaned_char = {
                    'id': char.get('id'),
                    'characterName': char.get('characterName'),
                    'isMain': char.get('isMain'),
                    'age': char.get('age'),
                    'gender': char.get('gender'),
                    'characterDescription': char.get('characterDescription')
                    # discoveryCount, chunkSources, scenes 제외
                }
                cleaned_characters.append(cleaned_char)
            
            return JsonResponse({
                'success': True,
                'status': 'COMPLETED',
                'message': f'캐릭터 생성이 이미 완료되었습니다!',
                'task_id': target_task['task_id'],
                'book_id': book_id,
                'book_title': task_data.get('book_title'),
                'total_characters': task_data.get('total_characters', 0),
                'characters': cleaned_characters,
                'completed_at': task_data.get('completed_at'),
                'processing_stats': task_data.get('processing_stats', {}),
                'note': '캐릭터 생성이 완료되어 실시간 스트림이 아닌 완료 데이터를 반환합니다.'
            })
        else:
            # 🔄 진행 중인 작업: 실시간 스트림 시작
            send_event(f'character-{book_id}', 'status', {
                'task_id': target_task['task_id'],
                'book_id': book_id,
                'book_title': task_data.get('book_title'),
                'status': task_data.get('status'),
                'step': task_data.get('step'),
                'message': task_data.get('message'),
                'progress_percentage': calculate_progress(task_data),
                'total_chunks': task_data.get('total_chunks'),
                'processed_chunks': task_data.get('processed_chunks'),
                'total_characters': task_data.get('total_characters'),
                'processed_characters': task_data.get('processed_characters')
            })
            
            return JsonResponse({
                'success': True,
                'message': f'캐릭터 생성 실시간 모니터링 시작',
                'channel': f'character-{book_id}',
                'eventstream_url': f'/events/?channel=character-{book_id}',
                'task_id': target_task['task_id'],
                'current_status': task_data.get('status')
            })
        
    except Exception as e:
        logger.error(f'캐릭터 생성 EventStream 오류: {str(e)}')
        return JsonResponse({
            'error': f'캐릭터 생성 모니터링 시작 실패: {str(e)}'
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@swagger_auto_schema(
    operation_description="""대본 생성 상태를 실시간으로 받습니다. (EventStream 방식)
    
    script_id로 대본 생성 상태를 직접 모니터링합니다.
    
    EventStream 특징:
    - script_id 기반 직접 조회 (더 효율적)
    - 즉시 상태 전송
    - 완료 시 대본 내용 포함
    - 자동 에러 감지
    """,
    responses={
        200: openapi.Response(description="채널 연결 성공"),
        404: openapi.Response(description="스크립트를 찾을 수 없음"),
        401: openapi.Response(description="인증 필요")
    },
    tags=['EventStream SSE (신규)']
)
def script_generation_eventstream(request, script_id):
    """대본 생성 상태를 EventStream으로 모니터링 시작 (script_id 기반)"""
    try:
        from django.core.cache import caches
        
        script_cache = caches['script_cache']
        
        # script_id로 직접 스크립트 데이터 조회
        script_key = f"script:{script_id}"
        script_data = script_cache.get(script_key)
        
        if not script_data:
            return JsonResponse({
                'error': f'스크립트 ID {script_id}를 찾을 수 없습니다.',
                'suggestion': '올바른 script_id를 확인하거나 먼저 /characters/{character_id}/scripts/async API로 대본 생성을 시작하세요.'
            }, status=404)
        
        # 스크립트 상태 확인
        current_status = script_data.get('status', 'UNKNOWN')
        
        if current_status == 'COMPLETED':
            # ✅ 완료된 스크립트: 즉시 완료 데이터 반환
            return JsonResponse({
                'success': True,
                'status': 'COMPLETED',
                'message': f'대본 생성이 이미 완료되었습니다!',
                'script_id': script_id,
                'character_id': script_data.get('character_id') or script_data.get('characterId'),
                'character_name': script_data.get('character_name'),
                'scene_count': len(script_data.get('scenes', [])),
                'completed_at': script_data.get('completed_at'),
                'scenes': script_data.get('scenes', []),
                'note': '대본 생성이 완료되어 실시간 스트림이 아닌 완료 데이터를 반환합니다.'
            })
        else:
            # 🔄 진행 중인 스크립트: 실시간 스트림 시작
            character_id = script_data.get('character_id') or script_data.get('characterId')
            
            send_event(f'script-{script_id}', 'status', {
                'script_id': script_id,
                'character_id': character_id,
                'character_name': script_data.get('character_name'),
                'status': current_status,
                'scene_count': script_data.get('scene_count'),
                'message': script_data.get('message'),
                'started_at': script_data.get('started_at'),
                'error_message': script_data.get('error_message')
            })
            
            return JsonResponse({
                'success': True,
                'message': f'대본 생성 실시간 모니터링 시작',
                'channel': f'script-{script_id}',
                'eventstream_url': f'/events/?channel=script-{script_id}',
                'script_id': script_id,
                'current_status': current_status
            })
        
    except Exception as e:
        logger.error(f'대본 생성 EventStream 오류: {str(e)}')
        return JsonResponse({
            'error': f'대본 생성 모니터링 시작 실패: {str(e)}'
        }, status=500)


def calculate_progress(task_data):
    """진행률 계산 (0-100%)"""
    if task_data.get('step') == 'pdf_chunking':
        return 10
    elif task_data.get('step') == 'character_extraction':
        total = task_data.get('total_chunks', 1)
        processed = task_data.get('processed_chunks', 0)
        return 10 + (processed / total) * 50  # 10-60%
    elif task_data.get('step') == 'scene_generation':
        total = task_data.get('total_characters', 1)
        processed = task_data.get('processed_characters', 0)
        return 60 + (processed / total) * 35  # 60-95%
    elif task_data.get('step') == 'saving':
        return 95
    elif task_data.get('status') == 'COMPLETED':
        return 100
    return 0


# ========================
# 이벤트 발송 헬퍼 함수들
# ========================

def notify_book_progress(book_id, status, **extra_data):
    """책 처리 진행 상황 실시간 알림"""
    event_data = {
        'book_id': book_id,
        'status': status,
        'timestamp': extra_data.get('timestamp'),
        **extra_data
    }
    
    send_event(f'book-{book_id}', 'status', event_data)
    logger.info(f'📡 책 {book_id} 상태 알림: {status}')


def notify_character_progress(book_id, task_id, step, progress_data):
    """캐릭터 생성 진행 상황 실시간 알림"""
    event_data = {
        'task_id': task_id,
        'book_id': book_id,
        'step': step,
        'progress_percentage': calculate_progress(progress_data),
        **progress_data
    }
    
    send_event(f'character-{book_id}', 'progress', event_data)
    logger.info(f'📡 캐릭터 생성 {task_id} 진행: {step}')


def notify_character_completed(book_id, task_id, characters):
    """캐릭터 생성 완료 알림"""
    # 캐릭터 데이터에서 불필요한 내부 처리 정보 제거
    cleaned_characters = []
    for char in characters:
        cleaned_char = {
            'id': char.get('id'),
            'characterName': char.get('characterName'),
            'isMain': char.get('isMain'),
            'age': char.get('age'),
            'gender': char.get('gender'),
            'characterDescription': char.get('characterDescription')
            # discoveryCount, chunkSources, scenes 제외
        }
        cleaned_characters.append(cleaned_char)
    
    event_data = {
        'task_id': task_id,
        'book_id': book_id,
        'status': 'COMPLETED',
        'progress_percentage': 100,
        'characters': cleaned_characters,
        'message': '캐릭터 생성이 완료되었습니다!'
    }
    
    send_event(f'character-{book_id}', 'completed', event_data)
    logger.info(f'🎉 캐릭터 생성 완료: {task_id}')


def notify_script_progress(script_id, status, **extra_data):
    """대본 생성 진행 상황 실시간 알림 (script_id 기반)"""
    event_data = {
        'script_id': script_id,
        'status': status,
        **extra_data
    }
    
    send_event(f'script-{script_id}', 'progress', event_data)
    logger.info(f'📡 대본 생성 {script_id} 상태: {status}')


def notify_script_completed(script_id, script_data):
    """대본 생성 완료 알림 (script_id 기반)"""
    event_data = {
        'script_id': script_id,
        'status': 'COMPLETED',
        'script_data': script_data,
        'timestamp': script_data.get('completed_at', ''),
        'message': f'대본 생성이 완료되었습니다! (장면 수: {script_data.get("scene_count", 0)}개)'
    }
    
    send_event(f'script-{script_id}', 'completed', event_data)
    logger.info(f'🎉 대본 생성 완료: {script_id} - 장면 수: {script_data.get("scene_count", 0)}') 