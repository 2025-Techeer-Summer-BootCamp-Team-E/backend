import os
import json
from django.conf import settings
import re
import google.generativeai as genai

# Gemini API 설정
genai.configure(api_key=settings.GEMINI_API_KEY)

def summarize_with_gemini(text: str) -> str:
    """
    Gemini API를 사용하여 책 내용 요약
    """
    try:
        # 텍스트가 너무 길면 자름 (Gemini의 입력 제한 고려)
        if len(text) > 10000:  # Gemini는 더 긴 텍스트 처리 가능
            text = text[:3000]

        # Gemini 모델 설정
        model = genai.GenerativeModel('gemini-2.5-flash')

        # 프롬프트 구성
        prompt = f"""
다음 책 내용을 요약해주세요.

요구사항:
- 핵심 내용과 메시지를 간결하게 정리해주세요
- 주요 등장인물과 줄거리를 포함해주세요
- 500자 이내로 요약해주세요
- 한국어로 작성해주세요

책 내용:
{text}

요약:
"""

        # Gemini API 호출
        response = model.generate_content(prompt)
        
        summary = response.text.strip()
        print("📚 책 요약 Gemini 응답:\n", summary)
        
        return summary
        
    except Exception as e:
        print(f"⚠️ Gemini API 요약 중 오류 발생: {str(e)}")
        # 오류 발생 시 원본 텍스트의 일부라도 반환
        fallback_summary = text[:500] + "..." if len(text) > 500 else text
        return f"요약 생성 중 오류가 발생했습니다. 원본 내용 일부: {fallback_summary}"
