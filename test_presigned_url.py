#!/usr/bin/env python3
"""
Presigned URL 기능 테스트 스크립트
실제 AWS 환경에서 실행해야 정상 작동합니다.
"""

import sys
import os
sys.path.append('/Users/mac/Desktop/2025-summer-bootcamp/epilog-backend/backend_django')

# Django 설정 초기화
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_dev')

def test_presigned_url_functions():
    """Presigned URL 관련 함수들 테스트"""
    
    print("🧪 Presigned URL 기능 테스트 시작")
    print("=" * 50)
    
    try:
        # Django 앱 초기화
        import django
        django.setup()
        
        from books.s3_client import extract_s3_key_from_url, generate_presigned_download_url, get_secure_pdf_url
        
        # 1. URL 파싱 테스트
        print("\n1️⃣ URL 파싱 테스트")
        test_urls = [
            "https://my-bucket.s3.ap-northeast-2.amazonaws.com/books/123/sample.pdf",
            "https://my-bucket.s3.us-west-2.amazonaws.com/books/456.pdf",
            "https://another-bucket.s3.eu-west-1.amazonaws.com/documents/test.pdf"
        ]
        
        for url in test_urls:
            try:
                s3_key = extract_s3_key_from_url(url)
                print(f"✅ URL: {url}")
                print(f"   📁 추출된 S3 키: {s3_key}")
            except Exception as e:
                print(f"❌ URL 파싱 실패: {url}")
                print(f"   오류: {str(e)}")
        
        # 2. 에러 케이스 테스트
        print("\n2️⃣ 에러 케이스 테스트")
        error_cases = [
            "",  # 빈 문자열
            None,  # None
            "invalid-url",  # 잘못된 URL
            "https://example.com/",  # S3가 아닌 URL
        ]
        
        for case in error_cases:
            try:
                s3_key = extract_s3_key_from_url(case)
                print(f"❌ 예상치 못한 성공: {case} -> {s3_key}")
            except Exception as e:
                print(f"✅ 예상된 에러 처리: {case} -> {type(e).__name__}: {str(e)}")
        
        # 3. Presigned URL 생성 시뮬레이션 (실제 AWS 없이는 실행 불가)
        print("\n3️⃣ Presigned URL 생성 시뮬레이션")
        print("📝 참고: 실제 AWS 환경에서만 정상 작동합니다.")
        
        sample_s3_key = "books/123/sample.pdf"
        print(f"   S3 키: {sample_s3_key}")
        print(f"   만료 시간: 3600초 (1시간)")
        print("   실행 결과: AWS 환경에서 실행 시 Presigned URL이 생성됩니다.")
        
        print("\n🎉 테스트 완료!")
        print("=" * 50)
        
    except ImportError as e:
        print(f"❌ Django 설정 오류: {str(e)}")
        print("💡 Django 프로젝트 루트에서 실행해주세요.")
    except Exception as e:
        print(f"❌ 테스트 실행 오류: {str(e)}")

def test_serializer_integration():
    """Serializer 통합 테스트"""
    
    print("\n📋 Serializer 통합 테스트")
    print("=" * 30)
    
    try:
        import django
        django.setup()
        
        from books.models import Book
        from books.serializers import BookOfficialResponseSerializer
        
        # 테스트용 Book 객체 생성 (실제 DB에 저장하지 않음)
        test_book = Book(
            id=999,
            title="테스트 책",
            content="테스트 내용입니다.",
            pdf_url="https://test-bucket.s3.ap-northeast-2.amazonaws.com/books/999/test.pdf",
            cover_url="https://example.com/cover.jpg"
        )
        
        # Serializer 테스트
        serializer = BookOfficialResponseSerializer(test_book)
        data = serializer.data
        
        print("✅ Serializer 데이터:")
        for key, value in data.items():
            print(f"   {key}: {value}")
        
        # PDF URL이 처리되었는지 확인
        if 'pdf_url' in data:
            if data['pdf_url'] != test_book.pdf_url:
                print("✅ PDF URL이 Presigned URL로 변환됨 (또는 처리됨)")
            else:
                print("ℹ️ PDF URL이 원본 그대로 반환됨 (AWS 환경 아님)")
        
    except Exception as e:
        print(f"❌ Serializer 테스트 오류: {str(e)}")

if __name__ == "__main__":
    test_presigned_url_functions()
    test_serializer_integration()
