import os
import tempfile
from typing import List, Dict, Any
from books.pdf_utils import extract_text_from_pdf
from django.core.files.base import ContentFile
import boto3
from django.conf import settings

def chunk_pdf_content(pdf_content: bytes, pdf_filename: str, chunk_size_pages: int = 50) -> List[Dict[str, Any]]:
    """
    PDF 내용을 페이지 단위로 청킹
    
    Args:
        pdf_content: PDF 바이너리 데이터
        pdf_filename: PDF 파일명
        chunk_size_pages: 청크당 페이지 수
        
    Returns:
        List of chunks with metadata
    """
    chunks = []
    
    try:
        # Django ContentFile로 변환
        pdf_file = ContentFile(pdf_content, name=pdf_filename)
        
        # 전체 텍스트 추출 (페이지별 처리를 위해)
        full_text = extract_text_from_pdf(pdf_file)
        
        # 텍스트를 대략적인 페이지로 나누기 (실제 PDF 페이지와 다를 수 있음)
        # 평균적으로 한 페이지당 약 2000-3000 문자 추정
        chars_per_page = 2500
        chunk_size_chars = chunk_size_pages * chars_per_page
        
        text_length = len(full_text)
        start_idx = 0
        chunk_num = 1
        
        while start_idx < text_length:
            end_idx = min(start_idx + chunk_size_chars, text_length)
            
            # 단어 경계에서 자르기 (문장 중간에서 자르지 않도록)
            if end_idx < text_length:
                # 마지막 완전한 문장까지만 포함
                last_period = full_text.rfind('.', start_idx, end_idx)
                last_newline = full_text.rfind('\n', start_idx, end_idx)
                boundary = max(last_period, last_newline)
                
                if boundary > start_idx:
                    end_idx = boundary + 1
            
            chunk_text = full_text[start_idx:end_idx].strip()
            
            if chunk_text:  # 빈 청크는 제외
                estimated_start_page = (start_idx // chars_per_page) + 1
                estimated_end_page = (end_idx // chars_per_page) + 1
                
                chunks.append({
                    'chunk_number': chunk_num,
                    'text': chunk_text,
                    'estimated_start_page': estimated_start_page,
                    'estimated_end_page': estimated_end_page,
                    'character_count': len(chunk_text),
                    'word_count': len(chunk_text.split())
                })
                chunk_num += 1
            
            start_idx = end_idx
        
        print(f"📄 PDF 청킹 완료 - 총 {len(chunks)}개 청크, 파일: {pdf_filename}")
        return chunks
        
    except Exception as e:
        print(f"❌ PDF 청킹 실패: {str(e)}")
        raise

def smart_chunk_sizing(text_length: int, base_chunk_size: int = 100) -> int:
    """
    텍스트 길이에 따라 스마트하게 청크 크기 조정
    
    Args:
        text_length: 전체 텍스트 길이
        base_chunk_size: 기본 청크 크기 (페이지) - 100페이지로 확대
        
    Returns:
        최적화된 청크 크기
    """
    # 더 큰 청크 단위로 처리하여 문맥 보존
    if text_length > 1000000:  # 1MB 이상 (매우 큰 파일)
        return 80   # 80페이지씩
    elif text_length > 500000:  # 500KB 이상
        return 100  # 100페이지씩 (기본값)
    else:
        return base_chunk_size  # 100페이지씩

def extract_character_keywords(text: str) -> List[str]:
    """
    텍스트에서 캐릭터 관련 키워드 추출 (전처리용)
    
    Args:
        text: 분석할 텍스트
        
    Returns:
        캐릭터 관련 키워드 리스트
    """
    import re
    
    # 인명 패턴 추출 (한글, 영문 이름 패턴)
    korean_name_pattern = r'[가-힣]{2,4}(?=[이가은는을를께서와과]|\s|$)'
    english_name_pattern = r'[A-Z][a-z]+(?:\s[A-Z][a-z]+)*'
    
    korean_names = re.findall(korean_name_pattern, text)
    english_names = re.findall(english_name_pattern, text)
    
    # 빈도 기반 필터링
    from collections import Counter
    all_names = korean_names + english_names
    name_counts = Counter(all_names)
    
    # 2번 이상 등장하는 이름만 캐릭터로 간주
    character_keywords = [name for name, count in name_counts.items() if count >= 2]
    
    return character_keywords[:20]  # 최대 20개까지만

def prioritize_character_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    캐릭터 정보가 많이 포함된 청크를 우선순위로 정렬
    
    Args:
        chunks: PDF 청크 리스트
        
    Returns:
        우선순위가 적용된 청크 리스트
    """
    for chunk in chunks:
        text = chunk['text']
        
        # 캐릭터 관련 키워드 개수 계산
        character_keywords = extract_character_keywords(text)
        chunk['character_keyword_count'] = len(character_keywords)
        chunk['character_keywords'] = character_keywords
        
        # 대화 비율 계산 (따옴표 또는 대화체 패턴)
        dialogue_patterns = ['"', "'", "말했다", "물었다", "답했다", "외쳤다"]
        dialogue_count = sum(text.count(pattern) for pattern in dialogue_patterns)
        chunk['dialogue_score'] = dialogue_count
        
        # 캐릭터 우선순위 점수 계산
        chunk['character_priority_score'] = (
            chunk['character_keyword_count'] * 2 +  # 캐릭터 키워드 가중치
            chunk['dialogue_score'] * 0.5  # 대화 가중치
        )
    
    # 우선순위 점수 기준으로 정렬
    sorted_chunks = sorted(chunks, key=lambda x: x['character_priority_score'], reverse=True)
    
    print(f"📊 청크 우선순위 정렬 완료 - Top 3 청크 점수: {[c['character_priority_score'] for c in sorted_chunks[:3]]}")
    return sorted_chunks 