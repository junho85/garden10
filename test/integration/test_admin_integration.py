import asyncio
import os
import sys
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import get_db, SessionLocal
from app.services.openai_service import get_openai_service
from app.services.admin_service import AdminService
from app.config import config


async def test_generate_encouragement_with_direct_prompt():
    """직접 프롬프트를 제공하여 응원 메시지 생성 테스트"""
    print("\n=== Test 1: 직접 프롬프트로 응원 메시지 생성 ===")
    
    openai_service = get_openai_service()
    
    if not openai_service.api_key:
        print("❌ OpenAI API key가 설정되지 않았습니다.")
        return
        
    prompt = "개발자들을 위한 짧고 따뜻한 응원 메시지를 한국어로 작성해주세요."
    
    try:
        result = await openai_service.generate_encouragement_message(prompt)
        
        if result["success"]:
            print(f"✅ 성공!")
            print(f"📝 생성된 메시지:\n{result['message']}")
            print(f"📊 토큰 사용량: {result['usage']}")
        else:
            print(f"❌ 실패: {result['error']}")
            
    except Exception as e:
        print(f"❌ 예외 발생: {str(e)}")


async def test_generate_encouragement_with_auto_prompt():
    """자동 생성 프롬프트를 사용하여 응원 메시지 생성 테스트"""
    print("\n=== Test 2: 자동 프롬프트로 응원 메시지 생성 ===")
    
    db = SessionLocal()
    openai_service = get_openai_service()
    
    if not openai_service.api_key:
        print("❌ OpenAI API key가 설정되지 않았습니다.")
        db.close()
        return
    
    try:
        # 1. 먼저 출석 데이터 기반 프롬프트 생성
        prompt_template = "정원사들의 출석 현황을 보고 따뜻하고 격려적인 응원 메시지를 작성해주세요."
        generated_prompt = await AdminService.generate_motivational_prompt(prompt_template, db)
        
        print(f"📋 생성된 프롬프트:\n{generated_prompt}")
        
        # 2. OpenAI로 응원 메시지 생성
        result = await openai_service.generate_encouragement_message(generated_prompt)
        
        if result["success"]:
            print(f"✅ 성공!")
            print(f"📝 생성된 메시지:\n{result['message']}")
            print(f"📊 토큰 사용량: {result['usage']}")
        else:
            print(f"❌ 실패: {result['error']}")
            
    except Exception as e:
        print(f"❌ 예외 발생: {str(e)}")
    finally:
        db.close()


async def test_generate_with_custom_prompt_template():
    """커스텀 프롬프트 템플릿으로 응원 메시지 생성 테스트"""
    print("\n=== Test 3: 커스텀 프롬프트 템플릿으로 응원 메시지 생성 ===")
    
    db = SessionLocal()
    openai_service = get_openai_service()
    
    if not openai_service.api_key:
        print("❌ OpenAI API key가 설정되지 않았습니다.")
        db.close()
        return
    
    try:
        # 커스텀 프롬프트 템플릿
        custom_template = """
정원사들의 출석 현황을 보고 다음 요소를 포함한 응원 메시지를 작성해주세요:
1. 출석률에 대한 긍정적인 평가
2. 개인별 성취에 대한 구체적인 칭찬
3. 앞으로의 목표나 다짐
4. 이모지를 활용한 친근한 표현
"""
        
        generated_prompt = await AdminService.generate_motivational_prompt(custom_template, db)
        print(f"📋 생성된 프롬프트:\n{generated_prompt}")
        
        result = await openai_service.generate_encouragement_message(generated_prompt)
        
        if result["success"]:
            print(f"✅ 성공!")
            print(f"📝 생성된 메시지:\n{result['message']}")
            print(f"📊 토큰 사용량: {result['usage']}")
        else:
            print(f"❌ 실패: {result['error']}")
            
    except Exception as e:
        print(f"❌ 예외 발생: {str(e)}")
    finally:
        db.close()


async def test_openai_configuration():
    """OpenAI 설정 확인 테스트"""
    print("\n=== OpenAI 설정 확인 ===")
    
    openai_service = get_openai_service()
    
    print(f"🔑 API Key 설정: {'✅' if openai_service.api_key else '❌'}")
    print(f"🤖 모델: {openai_service.model}")

    if hasattr(openai_service.client, 'base_url') and openai_service.client.base_url:
        print(f"🌐 Base URL: {openai_service.client.base_url}")


async def main():
    """모든 테스트 실행"""
    print(f"🚀 응원 메시지 생성 통합 테스트 시작 - {datetime.now()}")
    print("=" * 60)
    
    # OpenAI 설정 확인
    # await test_openai_configuration()
    
    # 테스트 실행
    # await test_generate_encouragement_with_direct_prompt()
    # await test_generate_encouragement_with_auto_prompt()
    # await test_generate_with_custom_prompt_template()
    
    print("\n" + "=" * 60)
    print("✨ 모든 테스트 완료!")


if __name__ == "__main__":
    asyncio.run(main())