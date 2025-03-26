import httpx
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func
import logging

from app.models.github_commit import GitHubCommit
from app.config import config

# 로깅 설정
logger = logging.getLogger(__name__)


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
        "Accept": "application/vnd.github.cloak-preview",
        "Authorization": f"token {api_token}"
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
