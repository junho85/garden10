from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
from app.database import get_db
from app.models.user import User
from app.models.attendance import Attendance
from app.services.attendance_service import (
    check_all_attendances,
    check_user_commit_and_save,
    get_user_attendance_history,
    get_daily_attendance_stats,
    create_attendance_from_commits
)
from app.config import config
from app.utils.error_utils import (
    create_http_exception,
    handle_validation_error,
    handle_not_found_error,
    service_result_to_response
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["attendance"])


@router.post("/attendance/check")
async def check_attendance_api(check_date: Optional[str] = None, db: Session = Depends(get_db)):
    """모든 사용자의 출석 체크를 실행합니다."""
    date_to_check = None
    if check_date:
        try:
            date_to_check = date.fromisoformat(check_date)
        except ValueError:
            raise handle_validation_error("Invalid date format. Use YYYY-MM-DD", "check_date")

    result = await check_all_attendances(date_to_check, db)
    return service_result_to_response(result)


@router.post("/attendance/check/{github_id}")
async def check_user_attendance_api(
        github_id: str,
        check_date: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """특정 사용자의 출석 체크를 실행합니다."""
    date_to_check = None
    if check_date:
        try:
            date_to_check = date.fromisoformat(check_date)
        except ValueError:
            raise handle_validation_error("Invalid date format. Use YYYY-MM-DD", "check_date")
    else:
        date_to_check = date.today()

    # 사용자 확인
    user = db.query(User).filter(User.github_id == github_id).first()
    if not user:
        raise handle_not_found_error("사용자", github_id)

    # 사용자별 토큰이 있으면 사용, 없으면 공통 토큰 사용
    api_token = user.github_api_token or config.github.get("api_token", "")
    if not api_token:
        raise create_http_exception(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub API token not configured"
        )

    result = await check_user_commit_and_save(github_id, date_to_check, api_token, db)
    return service_result_to_response(result)


@router.get("/attendance/history/{github_id}")
async def get_attendance_history(
        github_id: str,
        start_date: str,
        end_date: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """특정 사용자의 출석 기록을 조회합니다."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date) if end_date else date.today()
    except ValueError:
        raise handle_validation_error("Invalid date format. Use YYYY-MM-DD", "start_date or end_date")

    user = db.query(User).filter(User.github_id == github_id).first()
    if not user:
        raise handle_not_found_error("사용자", github_id)

    history = await get_user_attendance_history(github_id, start, end, db)
    return history


def _parse_date_range(start_date: Optional[str], end_date: Optional[str]):
    """시작일과 종료일을 파싱합니다."""
    # 시작일 설정
    if start_date:
        try:
            start = date.fromisoformat(start_date)
        except ValueError as e:
            logger.error(f"Invalid start_date format: {e}")
            raise handle_validation_error("Invalid date format. Use YYYY-MM-DD", "start_date")
    else:
        # 기본 시작일 (프로젝트 설정값 사용)
        try:
            project_config = config.project
            if project_config and hasattr(project_config, 'start_date'):
                start = date.fromisoformat(project_config.start_date)
            else:
                logger.warning("Project start_date not configured, using default")
                start = date(2025, 3, 10)  # 기본값
        except (ValueError, KeyError) as e:
            logger.error(f"Error parsing project start_date: {e}")
            start = date(2025, 3, 10)  # 기본값

    # 프로젝트 종료일 계산
    project_end_date = None
    try:
        project_config = config.project
        if project_config and hasattr(project_config, 'total_days') and hasattr(project_config, 'start_date'):
            project_start = date.fromisoformat(project_config.start_date)
            total_days = int(project_config.total_days)
            project_end_date = project_start + timedelta(days=total_days - 1)
    except (ValueError, KeyError) as e:
        logger.error(f"Error calculating project end date: {e}")
    
    # 종료일 설정
    if end_date:
        try:
            end = date.fromisoformat(end_date)
        except ValueError as e:
            logger.error(f"Invalid end_date format: {e}")
            raise handle_validation_error("Invalid date format. Use YYYY-MM-DD", "end_date")
    else:
        # 프로젝트가 종료되었으면 종료일로, 아니면 오늘 날짜로 설정
        if project_end_date and date.today() > project_end_date:
            end = project_end_date
        else:
            end = date.today()
    
    # 프로젝트가 종료되었는데 end가 프로젝트 종료일보다 뒤면 조정
    if project_end_date and end > project_end_date:
        end = project_end_date
        
    return start, end


def _get_total_project_days():
    """프로젝트 총 일수를 가져옵니다."""
    total_project_days = 100  # 기본값
    try:
        project_config = config.project
        if project_config and hasattr(project_config, 'total_days'):
            total_project_days = int(project_config.total_days)
    except (ValueError, KeyError) as e:
        logger.error(f"Error parsing project total_days: {e}")
    
    return total_project_days


def _calculate_user_stats(users, date_list, start, end, db):
    """사용자별 출석 데이터를 계산합니다."""
    user_stats = []

    for user in users:
        attendances = db.query(Attendance).filter(
            Attendance.github_id == user.github_id,
            Attendance.attendance_date >= start,
            Attendance.attendance_date <= end
        ).all()

        # 출석 여부 맵 생성
        attendance_map = {att.attendance_date.isoformat(): att.is_attended for att in attendances}

        # 날짜별 출석 여부 리스트
        attendance_list = [attendance_map.get(d, False) for d in date_list]

        # 출석률 계산
        attended_count = sum(1 for a in attendance_list if a)
        attendance_rate = round(attended_count / len(date_list) * 100) if date_list else 0

        user_stats.append({
            "github_id": user.github_id,
            "attendance_rate": attendance_rate,
            "attended_count": attended_count,
            "total_days": len(date_list),
            "attendance": attendance_list
        })

    # 출석률 기준으로 정렬하고 순위 부여
    user_stats.sort(key=lambda x: x["attendance_rate"], reverse=True)
    for i, user in enumerate(user_stats):
        user["rank"] = i + 1
        
    return user_stats


def _calculate_daily_rates(date_list, user_stats, users):
    """날짜별 출석률을 계산합니다."""
    daily_rates = []
    for i, d in enumerate(date_list):
        attended_count = sum(1 for user in user_stats if user["attendance"][i])
        daily_rate = round(attended_count / len(users) * 100) if users else 0
        daily_rates.append({
            "date": d,
            "rate": daily_rate
        })
    return daily_rates


def _calculate_attendance_summary(user_stats, users, date_list):
    """전체 출석 통계를 계산합니다."""
    total_present = sum(user["attended_count"] for user in user_stats)
    total_possible = len(users) * len(date_list)
    total_absent = total_possible - total_present
    overall_attendance_rate = round(total_present / total_possible * 100) if total_possible else 0
    
    return {
        "total_present": total_present,
        "total_absent": total_absent,
        "overall_attendance_rate": overall_attendance_rate
    }


@router.get("/attendance/stats")
async def get_attendance_stats(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """출석 통계를 조회합니다."""
    logger.info("get_attendance_stats")
    logger.debug(f"start_date: {start_date}")
    logger.debug(f"end_date: {end_date}")

    # 시작일과 종료일 설정
    start, end = _parse_date_range(start_date, end_date)
    
    # 날짜 범위 생성
    days_completed = (end - start).days + 1
    
    # 총 프로젝트 일수 설정
    total_project_days = _get_total_project_days()
    
    # 프로젝트 종료 여부 확인
    project_config = config.project
    is_completed = False
    if project_config and hasattr(project_config, 'start_date'):
        project_start = date.fromisoformat(project_config.start_date)
        project_end_date = project_start + timedelta(days=total_project_days - 1)
        is_completed = date.today() > project_end_date
        
        # 프로젝트가 종료되었으면 days_completed를 total_days로 제한
        if is_completed:
            days_completed = min(days_completed, total_project_days)
    
    date_list = [(start + timedelta(days=i)).isoformat() for i in range(days_completed)]

    # 사용자별 출석 데이터 조회
    users = db.query(User).all()
    user_stats = _calculate_user_stats(users, date_list, start, end, db)

    # 날짜별 출석률 계산
    daily_rates = _calculate_daily_rates(date_list, user_stats, users)

    # 총 출석 통계 계산
    attendance_summary = _calculate_attendance_summary(user_stats, users, date_list)
    
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days_completed": days_completed,
        "total_days": total_project_days,  # 총 프로젝트 일수
        "is_completed": is_completed,  # 프로젝트 완료 여부
        "dates": date_list,
        "users": user_stats,
        "daily_rates": daily_rates,
        **attendance_summary
    }


@router.get("/attendance/stats/{date_str}")
async def get_attendance_stats_for_date(date_str: str, db: Session = Depends(get_db)):
    """특정 날짜의 출석 통계를 조회합니다."""
    logger.info("get_attendance_stats_for_date")
    try:
        check_date = date.fromisoformat(date_str)
    except ValueError:
        raise handle_validation_error("Invalid date format. Use YYYY-MM-DD", "date_str")

    stats = await get_daily_attendance_stats(check_date, db)
    return stats


@router.get("/attendance/ranking")
async def get_attendance_ranking(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """출석률 순위를 조회합니다."""
    logger.debug(f"start_date: {start_date}")
    logger.debug(f"end_date: {end_date}")

    stats = await get_attendance_stats(start_date, end_date, db)
    return stats["users"]


@router.post("/attendance/create-from-commits")
async def create_attendance_from_commits_api(check_date: Optional[str] = None, db: Session = Depends(get_db)):
    """GitHub 커밋 내역을 조회하여 출석 기록을 생성합니다."""
    date_to_check = None
    if check_date:
        try:
            date_to_check = date.fromisoformat(check_date)
        except ValueError:
            raise handle_validation_error("Invalid date format. Use YYYY-MM-DD", "check_date")
    else:
        date_to_check = date.today()

    result = await create_attendance_from_commits(db, date_to_check)
    return service_result_to_response(result)


@router.get("/attendance/hourly-commits")
async def get_hourly_commits(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """시간대별 커밋 수 분포를 조회합니다."""
    from sqlalchemy.sql import extract, func
    from app.models.github_commit import GitHubCommit
    
    # 시작일과 종료일 설정
    start, end = _parse_date_range(start_date, end_date)
    
    # 시간대별 커밋 수를 가져오는 쿼리 (한국 시간 기준)
    # 날짜 범위를 적용하여 프로젝트 기간 내의 커밋만 조회
    query = db.query(
        extract('hour', func.timezone('Asia/Seoul', GitHubCommit.commit_date)).label('hour'),
        func.count().label('count')
    )
    
    # 날짜 범위 필터 추가
    start_datetime = datetime.combine(start, datetime.min.time())
    end_datetime = datetime.combine(end, datetime.max.time())
    query = query.filter(
        GitHubCommit.commit_date >= start_datetime,
        GitHubCommit.commit_date <= end_datetime
    )
    
    hourly_commits = query.group_by('hour').order_by('hour').all()
    
    # 0-23시까지 비어있는 시간대를 0으로 채우기 위한 기본 데이터 구성
    hourly_data = {hour: 0 for hour in range(24)}
    
    # 실제 데이터 채우기
    for hour, count in hourly_commits:
        hourly_data[hour] = count
    
    # 리스트 형태로 데이터 반환
    result = [{"hour": hour, "count": count} for hour, count in hourly_data.items()]
    
    return result


@router.get("/attendance/{date_str}")
async def get_attendance(date_str: str, db: Session = Depends(get_db)):
    """특정 날짜의 출석 현황을 조회합니다."""
    try:
        check_date = date.fromisoformat(date_str)
    except ValueError:
        raise handle_validation_error("Invalid date format. Use YYYY-MM-DD", "date_str")

    attendance_data = db.query(
        Attendance.github_id,
        Attendance.attendance_date,
        Attendance.is_attended,
        Attendance.updated_at
    ).filter(
        Attendance.attendance_date == check_date
    ).all()

    result = [
        {
            "github_id": github_id,
            "attendance_date": attendance_date,
            "is_attended": is_attended,
            "updated_at": updated_at
        }
        for github_id, attendance_date, is_attended, updated_at in attendance_data
    ]

    return result
