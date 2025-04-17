from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import os
import psutil
import time
import httpx
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.attendance import Attendance
from app.services.attendance_service import check_all_attendances, create_attendance_from_db_commits
from app.utils.auth_utils import get_admin_user

router = APIRouter()

# 출석 상태 수동 업데이트 요청 모델
class AttendanceUpdateRequest(BaseModel):
    github_id: str
    date: str
    is_attended: bool

# 사용자 추가 요청 모델
class AddUserRequest(BaseModel):
    github_id: str

# 로그 항목 모델
class LogEntry(BaseModel):
    timestamp: datetime
    level: str
    message: str

# 관리자 - 출석 데이터 갱신
@router.post("/admin/refresh-attendance", tags=["admin"])
async def refresh_attendance(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """모든 사용자의 출석 데이터를 갱신합니다. (관리자 전용)"""
    try:
        # 전체 출석 체크 함수 호출
        check_date = date.today()  # 오늘 날짜 기준으로 출석 체크
        result = await check_all_attendances(check_date=check_date, db=db)
        
        # 결과 형식 맞추기
        success_count = 0
        error_count = 0
        updated_users = []
        errors = []
        
        for item in result.get("results", []):
            if item.get("status") == "success":
                success_count += 1
                updated_users.append(item.get("github_id"))
            else:
                error_count += 1
                errors.append({
                    "github_id": item.get("github_id"),
                    "error": item.get("message")
                })
        
        results = {
            "success": True,
            "message": "출석 데이터가 갱신되었습니다.",
            "date": check_date.isoformat(),
            "updated_users": updated_users,
            "errors": errors,
            "stats": {
                "total": success_count + error_count,
                "success": success_count,
                "errors": error_count
            }
        }
        
        # 에러가 있으면 부분 성공으로 표시
        if errors:
            results["message"] = "일부 사용자의 출석 데이터가 갱신되지 않았습니다."
        
        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"출석 데이터 갱신 중 오류가 발생했습니다: {str(e)}"
        )

# 관리자 - 출석 상태 수동 변경
@router.post("/admin/update-attendance", tags=["admin"])
async def update_attendance(
    update_data: AttendanceUpdateRequest,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """특정 사용자의 특정 날짜 출석 상태를 수동으로 변경합니다. (관리자 전용)"""
    try:
        # 사용자 확인
        user = db.query(User).filter(User.github_id == update_data.github_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"GitHub ID '{update_data.github_id}'를 가진 사용자를 찾을 수 없습니다."
            )
        
        # 해당 날짜의 출석 기록 확인
        attendance = db.query(Attendance).filter(
            Attendance.github_id == update_data.github_id,
            Attendance.date == update_data.date
        ).first()
        
        if attendance:
            # 기존 출석 기록 업데이트
            attendance.is_attended = update_data.is_attended
            attendance.updated_at = datetime.utcnow()
            db.commit()
            message = "출석 상태가 업데이트되었습니다."
        else:
            # 새로운 출석 기록 생성
            new_attendance = Attendance(
                github_id=update_data.github_id,
                date=update_data.date,
                is_attended=update_data.is_attended,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(new_attendance)
            db.commit()
            message = "출석 상태가 새로 생성되었습니다."
        
        return {
            "success": True,
            "message": message,
            "data": {
                "github_id": update_data.github_id,
                "date": update_data.date,
                "is_attended": update_data.is_attended
            }
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"출석 상태 변경 중 오류가 발생했습니다: {str(e)}"
        )

# 관리자 - 시스템 상태 확인
@router.get("/admin/system-status", tags=["admin"])
async def system_status(current_user: User = Depends(get_admin_user)):
    """시스템 상태 정보를 반환합니다. (관리자 전용)"""
    try:
        # CPU 사용량
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 메모리 사용량
        memory = psutil.virtual_memory()
        memory_used_percent = memory.percent
        memory_used_mb = memory.used / (1024 * 1024)  # MB로 변환
        memory_total_mb = memory.total / (1024 * 1024)  # MB로 변환
        
        # 디스크 사용량
        disk = psutil.disk_usage('/')
        disk_used_percent = disk.percent
        disk_used_gb = disk.used / (1024 * 1024 * 1024)  # GB로 변환
        disk_total_gb = disk.total / (1024 * 1024 * 1024)  # GB로 변환
        
        # 프로세스 정보
        process = psutil.Process(os.getpid())
        process_start_time = datetime.fromtimestamp(process.create_time()).strftime('%Y-%m-%d %H:%M:%S')
        process_memory_mb = process.memory_info().rss / (1024 * 1024)  # MB로 변환
        
        # 시스템 업타임
        boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M:%S')
        
        return {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "system": {
                "cpu_percent": cpu_percent,
                "memory": {
                    "percent": memory_used_percent,
                    "used_mb": round(memory_used_mb, 2),
                    "total_mb": round(memory_total_mb, 2)
                },
                "disk": {
                    "percent": disk_used_percent,
                    "used_gb": round(disk_used_gb, 2),
                    "total_gb": round(disk_total_gb, 2)
                },
                "boot_time": boot_time
            },
            "process": {
                "pid": os.getpid(),
                "start_time": process_start_time,
                "memory_mb": round(process_memory_mb, 2)
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"시스템 상태 확인 중 오류가 발생했습니다: {str(e)}"
        )

# 관리자 - GitHub API 연결 확인
@router.get("/admin/check-github-api", tags=["admin"])
async def check_github_api(current_user: User = Depends(get_admin_user)):
    """GitHub API 연결 상태를 확인합니다. (관리자 전용)"""
    try:
        start_time = time.time()
        
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.github.com/zen")
            
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)  # ms로 변환
        
        return {
            "status": "success",
            "message": "GitHub API 연결이 정상입니다.",
            "response_time_ms": response_time,
            "github_zen": response.text if response.status_code == 200 else None
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub API 연결 확인 중 오류가 발생했습니다: {str(e)}"
        )

# 관리자 - 사용자 추가
@router.post("/admin/add-user", tags=["admin"])
async def add_user(
    user_data: AddUserRequest,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """새로운 사용자를 추가합니다. (관리자 전용)"""
    try:
        # 중복 사용자 확인
        existing_user = db.query(User).filter(User.github_id == user_data.github_id).first()
        if existing_user:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "message": f"GitHub ID '{user_data.github_id}'는 이미 등록된 사용자입니다."
                }
            )
        
        # GitHub API로 사용자 정보 확인
        async with httpx.AsyncClient() as client:
            github_response = await client.get(f"https://api.github.com/users/{user_data.github_id}")
            
            if github_response.status_code != 200:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "success": False,
                        "message": f"GitHub에서 '{user_data.github_id}' 사용자를 찾을 수 없습니다."
                    }
                )
                
            github_user_info = github_response.json()
        
        # 새 사용자 생성
        new_user = User(
            github_id=user_data.github_id,
            github_api_token=None  # 토큰은 로그인 시 설정됨
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return {
            "success": True,
            "message": f"사용자 '{user_data.github_id}'가 성공적으로 추가되었습니다.",
            "user": {
                "id": new_user.id,
                "github_id": new_user.github_id,
                "github_profile_url": f"https://avatars.githubusercontent.com/{new_user.github_id}"
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"사용자 추가 중 오류가 발생했습니다: {str(e)}"
        )

# 관리자 - 로그 조회
@router.get("/admin/logs", response_model=List[LogEntry], tags=["admin"])
async def view_logs(
    limit: Optional[int] = 50,
    current_user: User = Depends(get_admin_user)
):
    """
    애플리케이션 로그를 조회합니다. (관리자 전용)
    
    현재는 가상의 로그 데이터를 반환합니다. 실제 로그 파일을 읽는 코드로 대체해야 합니다.
    """
    try:
        # 여기서는 예시로 가상의 로그 데이터를 반환합니다.
        # 실제 구현에서는 로그 파일을 읽어오거나 로그 DB에서 가져와야 합니다.
        sample_logs = [
            LogEntry(
                timestamp=datetime.now(),
                level="INFO",
                message="애플리케이션이 시작되었습니다."
            ),
            LogEntry(
                timestamp=datetime.now(),
                level="INFO",
                message="출석 체크가 성공적으로 완료되었습니다."
            ),
            LogEntry(
                timestamp=datetime.now(),
                level="WARNING",
                message="GitHub API 응답이 지연되고 있습니다."
            ),
            LogEntry(
                timestamp=datetime.now(),
                level="ERROR",
                message="일부 사용자의 출석 체크 중 오류가 발생했습니다."
            )
        ]
        
        return sample_logs[:limit]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"로그 조회 중 오류가 발생했습니다: {str(e)}"
        )