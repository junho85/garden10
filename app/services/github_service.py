import httpx
from datetime import datetime, date
from typing import Optional, List, Dict, Any


async def get_github_commits(github_id: str, check_date: date, api_token: str) -> List[Dict[str, Any]]:
    """
    GitHub API를 호출하여 특정 사용자의 특정 날짜의 커밋 내역을 조회합니다.
    
    Args:
        github_id: GitHub 사용자 ID
        check_date: 조회할 날짜
        api_token: GitHub API 토큰
    
    Returns:
        List[Dict[str, Any]]: 커밋 목록
    """
    date_str = check_date.isoformat()
    url = f"https://api.github.com/search/commits?q=author:{github_id}+committer-date:{date_str}"
    
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
            print(f"GitHub API 오류: {response.status_code}, {response.text}")
            return []
