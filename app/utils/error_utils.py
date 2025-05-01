import logging
from typing import Dict, Any, Optional, Union
from fastapi import HTTPException, status

# 로깅 설정
logger = logging.getLogger(__name__)

def handle_service_error(
    error: Exception, 
    operation: str,
    log_traceback: bool = True
) -> Dict[str, Any]:
    """
    서비스 계층에서 발생한 예외를 처리하고 적절한 응답 형식으로 변환합니다.
    
    Args:
        error: 발생한 예외
        operation: 수행 중이던 작업 설명
        log_traceback: 스택 트레이스를 로그에 기록할지 여부
    
    Returns:
        Dict[str, Any]: 에러 응답 딕셔너리
    """
    logger.error(f"{operation} 중 오류 발생: {str(error)}", exc_info=log_traceback)
    
    return {
        "status": "error",
        "message": str(error)
    }

def create_http_exception(
    status_code: int, 
    detail: str,
    log_error: bool = True
) -> HTTPException:
    """
    HTTP 예외를 생성하고 선택적으로 로깅합니다.
    
    Args:
        status_code: HTTP 상태 코드
        detail: 오류 상세 메시지
        log_error: 오류를 로그에 기록할지 여부
    
    Returns:
        HTTPException: FastAPI HTTP 예외 객체
    """
    if log_error:
        logger.error(f"HTTP 오류 생성: {status_code} - {detail}")
    
    return HTTPException(
        status_code=status_code,
        detail=detail
    )

def service_result_to_response(
    result: Dict[str, Any]
) -> Union[Dict[str, Any], HTTPException]:
    """
    서비스 계층의 결과를 API 응답으로 변환합니다.
    서비스 결과의 상태가 'error'인 경우 HTTP 예외를 발생시킵니다.
    
    Args:
        result: 서비스 계층의 결과 딕셔너리
    
    Returns:
        Union[Dict[str, Any], HTTPException]: 
            상태가 'success'면 결과 그대로 반환, 
            'error'면 HTTPException 발생
    """
    if result.get("status") == "error":
        raise create_http_exception(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("message", "알 수 없는 오류가 발생했습니다.")
        )
    
    return result

def handle_validation_error(
    message: str,
    field: Optional[str] = None
) -> HTTPException:
    """
    입력 유효성 검증 오류를 처리합니다.
    
    Args:
        message: 오류 메시지
        field: 유효성 검증에 실패한 필드 이름 (선택적)
    
    Returns:
        HTTPException: 400 Bad Request 예외
    """
    detail = message
    if field:
        detail = f"{field}: {message}"
    
    logger.warning(f"유효성 검증 오류: {detail}")
    
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail
    )

def handle_not_found_error(
    entity_type: str,
    entity_id: str
) -> HTTPException:
    """
    엔티티를 찾을 수 없는 오류를 처리합니다.
    
    Args:
        entity_type: 엔티티 유형 (예: '사용자', '출석 기록')
        entity_id: 엔티티 식별자
    
    Returns:
        HTTPException: 404 Not Found 예외
    """
    detail = f"{entity_type}(id: {entity_id})를 찾을 수 없습니다."
    logger.warning(f"조회 실패: {detail}")
    
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail
    )