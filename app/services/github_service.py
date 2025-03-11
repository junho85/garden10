import httpx
from datetime import datetime, date



async def get_github_commits(github_id: str, check_date: date):
    """
    GitHub API를 호출하여 특정 날짜의 커밋 내역을 가져옵니다.
    """
    date_str = check_date.isoformat()
    url = f"https://api.github.com/search/commits?q=author:{github_id}+committer-date:{date_str}"

    async with httpx.AsyncClient() as client:
        headers = {"Accept": "application/vnd.github.cloak-preview"}
        response = await client.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            return data.get("items", [])
        else:
            return []
