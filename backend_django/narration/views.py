# narrations/views.py


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated  # JWT 인증 추가
from characters.models import Character
from narration.service.narration_service import generate_narration_for_character

''' 음성 생성 API 뷰 (테스트용 - narration_service 사용) '''
class GenerateVoiceAPIView(APIView):
    """
    테스트용 나레이션 생성 API (JWT 인증 필요)
    내부적으로 narration_service.generate_narration_for_character() 함수를 사용

    영상 생성시 generate_narration_for_character() 함수를 직접 호출해서 사용
    """
    permission_classes = [IsAuthenticated]  # JWT 인증 필요
    
    def post(self, request):
        """
        POST /narration/voice/
        
        Request Body:
        {
            "characterId": 10,
            "lines": [
                {"sceneId": 1, "speaker": "점순이", "text": "안녕하세요"},
                {"sceneId": 2, "speaker": "점순이", "text": "반갑습니다"}
            ]
        }
        
        Response:
        {
            "status": "ok",
            "results": [
                {"sceneId": 1, "speaker": "점순이", "text": "안녕하세요", "audioUrl": "s3://..."}
            ]
        }
        """
        try:
            print(f"🎤 인증된 사용자 {request.user.username}이 음성 생성 요청")
            
            # 요청 데이터 추출
            character_id = request.data.get("characterId")
            lines = request.data.get("lines", [])
            
            print(f"🧪 [테스트 API] 요청 받음 - Character ID: {character_id}, Lines: {len(lines)}개")
            
            # 기본 입력 검증 (상세 검증은 서비스 함수에서)
            if not character_id:
                return Response({"error": "characterId는 필수입니다."}, status=400)
            
            if not lines:
                return Response({"error": "lines는 필수입니다."}, status=400)
            
            # 나레이션 서비스 함수 호출
            print(f"🔧 [테스트 API] generate_narration_for_character() 호출 시작")
            audio_results = generate_narration_for_character(character_id, lines)
            print(f"✅ [테스트 API] 나레이션 생성 완료: {len(audio_results)}개")
            
            # API 응답 형식에 맞게 변환
            return Response({
                "status": "ok", 
                "results": audio_results
            }, status=200)
            
        except Character.DoesNotExist:
            error_msg = f"캐릭터 ID {character_id}를 찾을 수 없습니다."
            print(f"❌ [테스트 API] {error_msg}")
            return Response({"error": error_msg}, status=404)
            
        except ValueError as ve:
            error_msg = f"입력값 오류: {str(ve)}"
            print(f"❌ [테스트 API] {error_msg}")
            return Response({"error": error_msg}, status=400)
            
        except Exception as e:
            error_msg = f"나레이션 생성 실패: {str(e)}"
            print(f"❌ [테스트 API] {error_msg}")
            return Response({"error": error_msg}, status=500)

