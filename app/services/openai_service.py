from openai import OpenAI
from app.config import config
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self):
        self.api_key = config.openai.get("api_key") if config.openai else None
        self.client = None
        
        if self.api_key:
            # base_url 설정 가져오기 (없으면 None으로 기본값 사용)
            base_url = config.openai.get("base_url") if config.openai else None
            
            # OpenAI 클라이언트 생성
            if base_url:
                self.client = OpenAI(api_key=self.api_key, base_url=base_url)
                logger.info(f"OpenAI client initialized with custom base_url: {base_url}")
            else:
                self.client = OpenAI(api_key=self.api_key)
                logger.info("OpenAI client initialized with default base_url")
            
            self.model = config.openai.get("model", "gpt-4o-mini") if config.openai else "gpt-4o-mini"
        else:
            logger.warning("OpenAI API key not configured")

    async def generate_encouragement_message(self, prompt: str) -> Dict[str, any]:
        """
        OpenAI API를 사용하여 응원 메시지를 생성합니다.
        
        Args:
            prompt: 응원 메시지 생성을 위한 프롬프트
            
        Returns:
            성공 시: {"success": True, "message": "생성된 메시지"}
            실패 시: {"success": False, "error": "에러 메시지"}
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return {
                "success": False,
                "error": "OpenAI API key not configured"
            }
            
        try:
            logger.info(f"Generating encouragement message with OpenAI (model: {self.model})")
            logger.debug(f"Prompt length: {len(prompt)} characters")

            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "당신은 개발자들의 꾸준한 출석과 커밋 활동을 응원하는 따뜻하고 격려적인 메시지를 작성하는 도우미입니다."},
                    {"role": "user", "content": prompt}
                ],
                stream=False  # 명시적으로 non-streaming 모드 설정
            )
            
            # 응답 확인
            if not response.choices or len(response.choices) == 0:
                logger.error("No choices in OpenAI response")
                return {
                    "success": False,
                    "error": "OpenAI API returned no choices"
                }
            
            generated_message = response.choices[0].message.content
            
            # 메시지 내용 확인
            if not generated_message:
                logger.error("Empty message content from OpenAI")
                return {
                    "success": False,
                    "error": "OpenAI API returned empty message"
                }
            
            logger.info(f"Successfully generated encouragement message (length: {len(generated_message)})")
            
            return {
                "success": True,
                "message": generated_message,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating encouragement message: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


# 싱글톤 인스턴스 - 나중에 lazy loading으로 생성
_openai_service_instance = None

def get_openai_service():
    global _openai_service_instance
    if _openai_service_instance is None:
        _openai_service_instance = OpenAIService()
    return _openai_service_instance