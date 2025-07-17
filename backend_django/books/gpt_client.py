import os
import openai
import json
from django.conf import settings
import re
from openai import OpenAI

# OPENAI_API_KEY는 환경변수로 관리할 것 권장
openai.api_key = os.getenv("OPENAI_API_KEY")

def summarize_with_gpt(text: str) -> str:
    if len(text) > 3000:
        text = text[:3000]  # 너무 길면 자름 (프롬프트 길이 제한)

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  

    system_prompt = "너는 책 내용을 요약해주는 AI야. 핵심 내용과 메시지를 간결하게 정리해줘."
    user_prompt = f"책 내용을 요약해줘:\n\n{text}"

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=500
    )

    return response.choices[0].message.content.strip()
