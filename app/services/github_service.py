import httpx
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func
import logging

from app.models.github_commit import GitHubCommit
from app.config import config

# 로깅 설정
logger = logging.getLogger(__name__)


async def get_user_commits(
    db: Session, 
    github_id: str, 
    skip: int = 0, 
    limit: int = 50,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None
) -> List[GitHubCommit]:
    """
    특정 사용자의 GitHub 커밋 내역을 데이터베이스에서 조회합니다.
    
    Args:
        db: 데이터베이스 세션
        github_id: GitHub 사용자 ID
        skip: 건너뛸 레코드 수
        limit: 가져올 최대 레코드 수
        from_date: 시작 날짜 (이 날짜 이후의 커밋만 조회)
        to_date: 종료 날짜 (이 날짜 이전의 커밋만 조회)
    
    Returns:
        List[GitHubCommit]: 커밋 목록
    """
    query = db.query(GitHubCommit).filter(GitHubCommit.github_id == github_id)
    
    # 날짜 범위 필터 적용
    if from_date:
        # 시작 시간과 종료 시간 설정 (KST 기준)
        kst_offset = timedelta(hours=9)  # UTC+9
        start_datetime = datetime.combine(from_date, datetime.min.time()) - kst_offset
        query = query.filter(GitHubCommit.commit_date >= start_datetime)
    
    if to_date:
        # 시작 시간과 종료 시간 설정 (KST 기준)
        kst_offset = timedelta(hours=9)  # UTC+9
        end_datetime = datetime.combine(to_date, datetime.max.time()) - kst_offset
        query = query.filter(GitHubCommit.commit_date <= end_datetime)
    
    return query.order_by(GitHubCommit.commit_date.desc()) \
        .offset(skip) \
        .limit(limit) \
        .all()


async def get_user_commits_stats(
    db: Session, 
    github_id: str,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    특정 사용자의 GitHub 커밋 통계를 데이터베이스에서 조회합니다.
    
    Args:
        db: 데이터베이스 세션
        github_id: GitHub 사용자 ID
        from_date: 시작 날짜 (이 날짜 이후의 커밋만 조회)
        to_date: 종료 날짜 (이 날짜 이전의 커밋만 조회)
    
    Returns:
        Dict: 커밋 통계 정보 (총 커밋 수, 저장소 수, 가장 최근 커밋 날짜)
    """
    # 쿼리 생성
    query = db.query(GitHubCommit).filter(GitHubCommit.github_id == github_id)
    
    # 날짜 범위 필터 적용
    if from_date:
        # 시작 시간과 종료 시간 설정 (KST 기준)
        kst_offset = timedelta(hours=9)  # UTC+9
        start_datetime = datetime.combine(from_date, datetime.min.time()) - kst_offset
        query = query.filter(GitHubCommit.commit_date >= start_datetime)
    
    if to_date:
        # 시작 시간과 종료 시간 설정 (KST 기준)
        kst_offset = timedelta(hours=9)  # UTC+9
        end_datetime = datetime.combine(to_date, datetime.max.time()) - kst_offset
        query = query.filter(GitHubCommit.commit_date <= end_datetime)
    
    # 총 커밋 수 조회
    total_commits = query.count()
    
    # 저장소 수 조회 (중복 제거)
    repos_query = db.query(GitHubCommit.repository).filter(GitHubCommit.github_id == github_id)
    if from_date:
        kst_offset = timedelta(hours=9)  # UTC+9
        start_datetime = datetime.combine(from_date, datetime.min.time()) - kst_offset
        repos_query = repos_query.filter(GitHubCommit.commit_date >= start_datetime)
    if to_date:
        kst_offset = timedelta(hours=9)  # UTC+9
        end_datetime = datetime.combine(to_date, datetime.max.time()) - kst_offset
        repos_query = repos_query.filter(GitHubCommit.commit_date <= end_datetime)
    
    repositories = repos_query.distinct().all()
    total_repos = len(repositories)
    
    # 가장 최근 커밋 날짜 조회
    latest_commit = query.order_by(GitHubCommit.commit_date.desc()).first()
    
    latest_commit_date = None
    if latest_commit:
        latest_commit_date = latest_commit.commit_date
    
    return {
        "total_commits": total_commits,
        "total_repos": total_repos,
        "latest_commit_date": latest_commit_date
    }



async def get_github_commits(github_id: str, check_date: date, api_token: str) -> List[Dict[str, Any]]:
    """
    GitHub API를 호출하여 특정 사용자의 특정 날짜의 커밋 내역을 조회합니다.
    
    Args:
        github_id: GitHub 사용자 ID
        check_date: 조회할 날짜
        api_token: GitHub API 토큰. None이면 설정 파일에서 가져옵니다.
    
    Returns:
        List[Dict[str, Any]]: 커밋 목록
    """
    date_str = check_date.isoformat()
    url = f"https://api.github.com/search/commits?q=author:{github_id}+committer-date:{date_str}"
    
    # API 토큰이 제공되지 않으면 설정 파일에서 가져옴
    if not api_token:
        api_token = config.github.get("api_token", "")

    # 헤더 설정
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {api_token}"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            return data.get("items", [])
        else:
            logger.error(f"GitHub API 오류: {response.status_code}, {response.text}")
            return []


async def save_github_commits(db: Session, commits: List[Dict[str, Any]], github_id: str) -> int:
    """
    GitHub API에서 가져온 커밋 내역을 데이터베이스에 저장합니다.
    
    Args:
        db: 데이터베이스 세션
        commits: GitHub API에서 가져온 커밋 목록
        github_id: GitHub 사용자 ID
    
    Returns:
        int: 성공적으로 저장된 커밋 수
    """
    saved_count = 0
    
    for commit_data in commits:
        try:
            # 필요한 데이터 추출
            commit_node = commit_data.get("commit", {})
            repository = commit_data.get("repository", {}).get("full_name", "Unknown")
            commit_id = commit_data.get("sha", "")
            message = commit_node.get("message", "")
            commit_url = commit_data.get("html_url", "")
            
            # 저장소가 private인지 확인
            is_private = commit_data.get("repository", {}).get("private", False)
            
            # 커밋 날짜 파싱
            commit_date_str = commit_node.get("committer", {}).get("date", "")
            commit_date = datetime.fromisoformat(commit_date_str.replace("Z", "+00:00"))
            
            # 데이터베이스에 저장할 객체 생성
            db_commit = GitHubCommit(
                github_id=github_id,
                commit_id=commit_id,
                repository=repository,
                message=message,
                commit_url=commit_url,
                commit_date=commit_date,
                is_private=is_private
            )
            
            # 중복 체크: commit_id와 repository로 기존 커밋 레코드가 있는지 확인
            existing_commit = db.query(GitHubCommit).filter(
                GitHubCommit.commit_id == commit_id, 
                GitHubCommit.repository == repository
            ).first()
            
            if existing_commit:
                # 기존 레코드 업데이트
                existing_commit.repository = repository
                existing_commit.message = message
                existing_commit.commit_url = commit_url
                existing_commit.commit_date = commit_date
                existing_commit.is_private = is_private
                existing_commit.updated_at = func.now()
                logger.info(f"기존 커밋 업데이트: {commit_id} in {repository}")
            else:
                # 새 레코드 추가
                db.add(db_commit)
                
            db.commit()
            saved_count += 1
            
        except Exception as e:
            # 기타 오류 처리
            db.rollback()
            logger.error(f"커밋 저장 중 오류: {str(e)}")
            continue
    
    return saved_count


async def fetch_and_save_commits(db: Session, github_id: str, check_date: date, api_token: str = None) -> Dict[str, Any]:
    """
    특정 사용자의 GitHub 커밋을 조회하고 데이터베이스에 저장합니다.
    
    Args:
        db: 데이터베이스 세션
        github_id: GitHub 사용자 ID
        check_date: 조회할 날짜
        api_token: GitHub API 토큰 (선택적)
    
    Returns:
        Dict[str, Any]: 결과 정보 (총 커밋 수, 저장된 커밋 수)
    """
    # GitHub API에서 커밋 데이터 조회
    commits = await get_github_commits(github_id, check_date, api_token)
    
    # 조회된 커밋이 없는 경우
    if not commits:
        return {
            "github_id": github_id,
            "date": check_date.isoformat(),
            "total_commits": 0,
            "saved_commits": 0,
            "status": "no_commits"
        }
    
    # 커밋 데이터 저장
    saved_count = await save_github_commits(db, commits, github_id)
    
    return {
        "github_id": github_id,
        "date": check_date.isoformat(),
        "total_commits": len(commits),
        "saved_commits": saved_count,
        "status": "success"
    }
    
    
async def get_all_users_attendance_stats(db: Session, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    모든 사용자의 출석 통계 정보를 조회합니다.
    
    Args:
        db: 데이터베이스 세션
        start_date: 시작 날짜 (YYYY-MM-DD 형식)
        end_date: 종료 날짜 (YYYY-MM-DD 형식)
        
    Returns:
        List[Dict[str, Any]]: 사용자별 출석 통계 목록
    """
    from app.models.user import User
    from app.models.attendance import Attendance
    
    # 모든 사용자 조회
    users = db.query(User).all()
    
    # 결과를 저장할 리스트
    results = []
    
    for user in users:
        github_id = user.github_id
        
        # 해당 사용자의 출석 데이터 조회
        attendances = db.query(Attendance).filter(
            Attendance.github_id == github_id,
            Attendance.attendance_date >= start_date,
            Attendance.attendance_date <= end_date
        ).order_by(Attendance.attendance_date).all()
        
        # 출석 데이터가 없으면 기본 정보만 포함
        if not attendances:
            results.append({
                "github_id": github_id,
                "total_days": 0,
                "attended_days": 0,
                "attendance_rate": 0,
                "total_commits": 0,
                "attendance_by_date": {}
            })
            continue
        
        # 통계 계산
        total_days = len(attendances)
        attended_days = sum(1 for a in attendances if a.is_attended)
        total_commits = sum(a.commit_count for a in attendances)
        attendance_rate = round(attended_days / total_days * 100, 1) if total_days > 0 else 0
        
        # 날짜별 출석 정보
        attendance_by_date = {}
        for a in attendances:
            date_str = a.attendance_date.isoformat()
            attendance_by_date[date_str] = {
                "commit_count": a.commit_count,
                "is_attended": a.is_attended
            }
        
        # 결과에 추가
        results.append({
            "github_id": github_id,
            "total_days": total_days,
            "attended_days": attended_days,
            "attendance_rate": attendance_rate,
            "total_commits": total_commits,
            "attendance_by_date": attendance_by_date
        })
    
    return results
