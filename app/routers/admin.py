from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import date
from typing import List, Optional

from app.database import get_db
from app.models.user import User
from app.utils.auth_utils import get_admin_user
from app.services.admin_service import AdminService
from app.services.openai_service import get_openai_service
from app.schemas.admin import (
    AttendanceUpdateRequest,
    AddUserRequest,
    LogEntry,
    MotivationalPromptRequest,
    EncouragementMessageRequest,
    SystemStatusResponse,
    GitHubAPIStatusResponse,
    AttendanceRefreshResponse,
    UserAddResponse
)

router = APIRouter()


@router.post("/admin/refresh-attendance", response_model=AttendanceRefreshResponse, tags=["admin"])
async def refresh_attendance(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """모든 사용자의 출석 데이터를 갱신합니다. (관리자 전용)"""
    try:
        check_date = date.today()
        result = await AdminService.refresh_all_attendances(check_date, db)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"출석 데이터 갱신 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/admin/update-attendance", tags=["admin"])
async def update_attendance(
    update_data: AttendanceUpdateRequest,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """특정 사용자의 특정 날짜 출석 상태를 수동으로 변경합니다. (관리자 전용)"""
    try:
        result = AdminService.update_user_attendance(
            update_data.github_id,
            update_data.date,
            update_data.is_attended,
            db
        )
        
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"GitHub ID '{update_data.github_id}'를 가진 사용자를 찾을 수 없습니다."
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"출석 상태 변경 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/admin/system-status", response_model=SystemStatusResponse, tags=["admin"])
async def system_status(current_user: User = Depends(get_admin_user)):
    """시스템 상태 정보를 반환합니다. (관리자 전용)"""
    try:
        return AdminService.get_system_status()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"시스템 상태 확인 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/admin/check-github-api", response_model=GitHubAPIStatusResponse, tags=["admin"])
async def check_github_api(current_user: User = Depends(get_admin_user)):
    """GitHub API 연결 상태를 확인합니다. (관리자 전용)"""
    try:
        return await AdminService.check_github_api_status()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub API 연결 확인 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/admin/add-user", response_model=UserAddResponse, tags=["admin"])
async def add_user(
    user_data: AddUserRequest,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """새로운 사용자를 추가합니다. (관리자 전용)"""
    try:
        result = await AdminService.add_new_user(user_data.github_id, db)
        
        if not result["success"]:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=result
            )
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"사용자 추가 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/admin/logs", response_model=List[LogEntry], tags=["admin"])
async def view_logs(
    limit: Optional[int] = 50,
    date: Optional[str] = None,
    level: Optional[str] = None,
    current_user: User = Depends(get_admin_user)
):
    """
    애플리케이션 로그를 조회합니다. (관리자 전용)
    
    - limit: 반환할 최대 로그 항목 수
    - date: 조회할 로그 날짜 (YYYY-MM-DD 형식, 기본값: 최신 로그 파일)
    - level: 필터링할 로그 레벨 (INFO, WARNING, ERROR)
    """
    try:
        logs = AdminService.get_application_logs(limit, date, level)
        return [LogEntry(**log) for log in logs]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"로그 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/admin/generate-motivational-prompt", tags=["admin"])
async def generate_motivational_prompt(
    prompt_data: MotivationalPromptRequest,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """출석 데이터를 바탕으로 응원메시지 프롬프트를 생성합니다. (관리자 전용)"""
    try:
        prompt = await AdminService.generate_motivational_prompt(prompt_data.prompt_template, db)
        
        return {
            "success": True,
            "message": "응원메시지 프롬프트가 생성되었습니다.",
            "prompt": prompt
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"응원메시지 프롬프트 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/admin/generate-encouragement-message", tags=["admin"])
async def generate_encouragement_message(
    request_data: EncouragementMessageRequest,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """OpenAI를 사용하여 응원메시지를 생성합니다. (관리자 전용)"""
    try:
        openai_service = get_openai_service()
        
        if request_data.prompt:
            prompt = request_data.prompt
        elif request_data.use_auto_prompt:
            prompt = await AdminService.generate_motivational_prompt(request_data.prompt_template, db)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="프롬프트를 제공하거나 자동 생성을 활성화해야 합니다."
            )
        
        result = await openai_service.generate_encouragement_message(prompt)
        
        if result["success"]:
            return {
                "success": True,
                "message": "응원메시지가 성공적으로 생성되었습니다.",
                "encouragement_message": result["message"],
                "usage": result.get("usage"),
                "prompt_used": prompt
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"OpenAI 응원메시지 생성 실패: {result['error']}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"응원메시지 생성 중 오류가 발생했습니다: {str(e)}"
        )