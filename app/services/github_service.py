import httpx
from datetime import datetime, date
from app.config import settings
from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User


async def get_github_commits(github_id: str, check_date: date, db: Optional[Session] = None):
    """
    GitHub API를 호출하여 특정 날짜의 커밋 내역을 가져옵니다.
    사용자별 GitHub API 토큰이 있으면 그것을 사용하고, 없으면 공통 토큰을 사용합니다.
    """
    date_str = check_date.isoformat()
    url = f"https://api.github.com/search/commits?q=author:{github_id}+committer-date:{date_str}"
    
    # 헤더 기본 설정
    headers = {"Accept": "application/vnd.github.cloak-preview"}
    
    # 사용자별 토큰을 찾아서 사용
    api_token = None
    
    # 1. DB에서 사용자의 토큰을 찾음
    if db:
        user = db.query(User).filter(User.github_id == github_id).first()
        if user and user.github_api_token:
            api_token = user.github_api_token
    
    # 2. 설정 파일에서 사용자의 토큰을 찾음 (DB에 없는 경우)
    if not api_token:
        for user_config in settings.USERS:
            if user_config.github_id == github_id and user_config.github_api_token:
                api_token = user_config.github_api_token
                break
    
    # 3. 공통 토큰 사용 (개별 토큰이 없는 경우)
    if not api_token:
        api_token = settings.GITHUB_API_TOKEN
    
    # 토큰이 있으면 Authorization 헤더 추가
    if api_token:
        headers["Authorization"] = f"token {api_token}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            return data.get("items", [])
        else:
            return []
