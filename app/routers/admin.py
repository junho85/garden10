from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import os
import psutil
import time
import httpx
from datetime import datetime, date, timedelta
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models.github_commit import GitHubCommit
from app.models.user import User
from app.models.attendance import Attendance
from app.services.attendance_service import check_all_attendances, create_attendance_from_db_commits
from app.utils.auth_utils import get_admin_user
from app.services.github_service import get_all_users_attendance_stats
from app.utils.date_utils import get_kst_datetime_range

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

# 응원메시지 프롬프트 요청 모델
class MotivationalPromptRequest(BaseModel):
    prompt_template: str

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
        detailed_results = []

        for item in result.get("results", []):
            if item.get("status") == "success":
                success_count += 1
                github_id = item.get("github_id")
                updated_users.append(github_id)

                # 해당 사용자의 커밋 정보 조회
                start_datetime, end_datetime = get_kst_datetime_range(check_date)

                commits = db.query(GitHubCommit).filter(
                    GitHubCommit.github_id == github_id,
                    GitHubCommit.commit_date >= start_datetime,
                    GitHubCommit.commit_date <= end_datetime
                ).all()

                commit_details = []
                for commit in commits:
                    commit_details.append({
                        "commit_id": commit.commit_id,
                        "repository": commit.repository,
                        "commit_date": commit.commit_date.isoformat(),
                        "message": commit.message
                    })

                # 출석 정보 조회
                attendance = db.query(Attendance).filter(
                    Attendance.github_id == github_id,
                    Attendance.attendance_date == check_date
                ).first()

                detailed_results.append({
                    "github_id": github_id,
                    "is_attended": item.get("is_attended", False),
                    "commit_count": item.get("commit_count", 0),
                    "action_performed": "updated" if attendance and attendance.updated_at else "created",
                    "commits": commit_details
                })
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
            "detailed_results": detailed_results,
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
            Attendance.attendance_date == update_data.date
        ).first()

        # 해당 날짜의 커밋 정보 조회
        check_date = datetime.strptime(update_data.date, "%Y-%m-%d").date()
        start_datetime, end_datetime = get_kst_datetime_range(check_date)

        commits = db.query(GitHubCommit).filter(
            GitHubCommit.github_id == update_data.github_id,
            GitHubCommit.commit_date >= start_datetime,
            GitHubCommit.commit_date <= end_datetime
        ).all()

        commit_count = len(commits)

        if attendance:
            # 기존 출석 기록 업데이트
            attendance.is_attended = update_data.is_attended
            attendance.commit_count = commit_count  # 커밋 수 업데이트
            attendance.updated_at = datetime.utcnow()
            db.commit()
            message = "출석 상태가 업데이트되었습니다."
        else:
            # 새로운 출석 기록 생성
            new_attendance = Attendance(
                github_id=update_data.github_id,
                attendance_date=update_data.date,
                is_attended=update_data.is_attended,
                commit_count=commit_count,  # 커밋 수 설정
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(new_attendance)
            db.commit()
            message = "출석 상태가 새로 생성되었습니다."

        # 커밋 상세 정보 생성
        commit_details = []
        for commit in commits:
            commit_details.append({
                "commit_id": commit.commit_id,
                "repository": commit.repository,
                "commit_date": commit.commit_date.isoformat(),
                "message": commit.message
            })

        return {
            "success": True,
            "message": message,
            "data": {
                "github_id": update_data.github_id,
                "date": update_data.date,
                "is_attended": update_data.is_attended,
                "commit_count": commit_count,
                "action_performed": "created" if not attendance else "updated",
                "commits": commit_details
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
        # 로그 디렉토리 경로
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")

        # 로그 파일 목록 가져오기
        log_files = []
        if os.path.exists(log_dir):
            for file in os.listdir(log_dir):
                if file.startswith("garden10_") and file.endswith(".log"):
                    log_files.append(file)

        if not log_files:
            return []

        # 날짜별로 정렬 (최신 날짜가 먼저 오도록)
        log_files.sort(reverse=True)

        # 특정 날짜가 지정된 경우 해당 로그 파일 찾기
        log_file = None
        if date:
            target_file = f"garden10_{date}.log"
            if target_file in log_files:
                log_file = os.path.join(log_dir, target_file)

        # 날짜가 지정되지 않았거나 해당 날짜의 로그 파일이 없는 경우 최신 로그 파일 사용
        if not log_file:
            log_file = os.path.join(log_dir, log_files[0])

        # 로그 파일 읽기
        logs = []
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        # 로그 형식: 2025-05-07 23:38:07,105 - app.main - INFO - Test info message
                        parts = line.strip().split(' - ', 3)
                        if len(parts) >= 4:
                            timestamp_str, module, log_level, message = parts

                            # 레벨 필터링
                            if level and log_level.upper() != level.upper():
                                continue

                            # 타임스탬프 파싱
                            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')

                            logs.append(LogEntry(
                                timestamp=timestamp,
                                level=log_level,
                                message=message
                            ))
                    except Exception as parse_error:
                        # 파싱 오류가 있는 라인은 건너뛰기
                        continue

        # 최신 로그가 먼저 오도록 정렬
        logs.sort(key=lambda x: x.timestamp, reverse=True)

        # 제한된 수의 로그만 반환
        return logs[:limit]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"로그 조회 중 오류가 발생했습니다: {str(e)}"
        )

# 관리자 - 응원메시지 프롬프트 생성
@router.post("/admin/generate-motivational-prompt", tags=["admin"])
async def generate_motivational_prompt(
    prompt_data: MotivationalPromptRequest,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """출석 데이터를 바탕으로 응원메시지 프롬프트를 생성합니다. (관리자 전용)"""
    try:
        # 시작일 계산 (정원사들 시즌10 시작일)
        start_date = "2025-03-10"
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()

        # 현재 날짜
        current_date = datetime.now().date()

        # 마감일 계산 (시작일로부터 99일)
        total_days = 100  # 총 100일 과정
        end_date_obj = start_date_obj + timedelta(days=99)
        end_date = end_date_obj.strftime("%Y-%m-%d")

        # 현재 날짜가 시작일 기준 몇일째인지 계산
        days_since_start = (current_date - start_date_obj).days + 1
        days_remaining = total_days - days_since_start

        # 모든 사용자의 출석 통계 가져오기
        users_stats = await get_all_users_attendance_stats(db, start_date, current_date.strftime("%Y-%m-%d"))

        # 프롬프트 기본 정보 구성
        prompt_base = prompt_data.prompt_template + f"\n현재 정원사들 시즌10 {days_since_start}일째입니다! (총 {total_days}일 중)\n"
        prompt_base += f"시작일: {start_date}\n"
        prompt_base += f"오늘 날짜: {current_date.strftime('%Y-%m-%d')}\n"
        prompt_base += f"종료일: {end_date}\n"
        prompt_base += f"남은 기간: {days_remaining}일\n\n"

        # 오늘의 공개된 커밋 내역 가져오기
        today_commits = {}
        for user_stat in users_stats:
            github_id = user_stat.get("github_id")

            # KST 기준으로 오늘 날짜 설정
            start_datetime, end_datetime = get_kst_datetime_range(current_date)

            # 오늘 커밋 조회
            user_commits = db.query(GitHubCommit).filter(
                GitHubCommit.github_id == github_id,
                GitHubCommit.commit_date >= start_datetime,
                GitHubCommit.commit_date <= end_datetime,
                GitHubCommit.is_private == False  # 공개 커밋만 가져오기
            ).all()

            if user_commits:
                today_commits[github_id] = user_commits

        # 각 사용자별 출석 정보 추가
        for user_stat in users_stats:
            github_id = user_stat.get("github_id")

            if user_stat.get("total_days") == 0:
                prompt_base += f"{github_id} 유저의 출석 정보를 찾을 수 없습니다.\n"
                continue

            prompt_base += f"\n{github_id} 유저 출석 현황:\n"
            prompt_base += f"총 출석 일수: {user_stat.get('attended_days')}/{user_stat.get('total_days')}일 (전체 {total_days}일 중, 출석률: {user_stat.get('attendance_rate')}%)\n"

            # 진행률 계산 - 전체 100일 기준
            progress_rate = (user_stat.get('attended_days') / total_days) * 100
            prompt_base += f"현재 진행률: {progress_rate:.1f}% (전체 {total_days}일 기준)\n"
            prompt_base += f"총 커밋 수: {user_stat.get('total_commits')}개\n"

            # 오늘의 공개된 커밋 내역 추가
            if github_id in today_commits and today_commits[github_id]:
                prompt_base += f"\n오늘의 공개 커밋 내역:\n"
                for commit in today_commits[github_id]:
                    prompt_base += f"- {commit.repository}: {commit.message.splitlines()[0]}\n"
                prompt_base += "\n"

            # 날짜별 출석 정보 추가 (최근 1주일만)
            attendance_by_date = user_stat.get("attendance_by_date", {})
            # 최근 7일 날짜 계산
            one_week_ago = current_date - timedelta(days=6)
            recent_dates = [one_week_ago + timedelta(days=i) for i in range(7)]
            recent_dates_str = [d.strftime("%Y-%m-%d") for d in recent_dates]

            prompt_base += f"\n최근 1주일 출석 기록:\n"
            # 날짜순으로 정렬하여 최근 1주일 데이터만 출력
            today_str = current_date.strftime("%Y-%m-%d")
            for date_str in sorted(attendance_by_date.keys()):
                if date_str in recent_dates_str:
                    info = attendance_by_date[date_str]
                    status = "✅ 출석" if info.get("is_attended") else "❌ 미출석"
                    date_display = f"{date_str} (오늘)" if date_str == today_str else date_str
                    prompt_base += f"{date_display}: {status} (커밋 {info.get('commit_count')}개)\n"

            prompt_base += "=" * 60 + "\n"

        return {
            "success": True,
            "message": "응원메시지 프롬프트가 생성되었습니다.",
            "prompt": prompt_base
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"응원메시지 프롬프트 생성 중 오류가 발생했습니다: {str(e)}"
        )
