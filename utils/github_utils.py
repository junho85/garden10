import os
import requests
from dotenv import load_dotenv
import yaml


def get_commit_history(username, start_date, end_date, page=1, per_page=30):
    # .env 파일에서 환경변수를 로드
    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise Exception("GITHUB_TOKEN 이 설정되어 있지 않습니다. .env 파일을 확인하세요.")

    # GitHub Commit Search API 엔드포인트
    # @see https://docs.github.com/ko/rest/search/search#search-commits
    url = "https://api.github.com/search/commits"

    # 'author:username' 형식의 검색 쿼리 작성, 날짜 범위 필터 추가
    query = f"author:{username} committer-date:{start_date}..{end_date}"
    params = {
        "q": query,
        "sort": "author-date",
        "order": "desc",
        "page": page,
        "per_page": per_page,
    }

    headers = {
        # Commit 검색을 위한 미리보기 헤더
        "Accept": "application/vnd.github.cloak-preview",
        "Authorization": f"token {token}",
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        raise Exception(f"API 요청 실패: {response.status_code} {response.text}")

    data = response.json()
    commits = data.get("items", [])
    return commits


def main():
    with open("config.yaml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    usernames = config.get("usernames", [])
    start_date = "2025-03-04"
    end_date = "2025-03-05"

    for username in usernames:
        try:
            commits = get_commit_history(username, start_date, end_date)
        except Exception as e:
            print(f"에러 발생 (유저: {username}):", e)
            continue

        if not commits:
            print(f"{username} 유저의 커밋 이력을 찾을 수 없습니다.")
            continue

        print(f"\n{username} 유저의 최근 커밋 이력 ({len(commits)}개):")
        for commit in commits:
            commit_sha = commit.get("sha")
            commit_message = commit.get("commit", {}).get("message")
            commit_date = commit.get("commit", {}).get("author", {}).get("date")
            repo_name = commit.get("repository", {}).get("full_name")

            print("=" * 60)
            print(f"Repository : {repo_name}")
            print(f"Commit SHA : {commit_sha}")
            print(f"Date       : {commit_date}")
            print("Message    :")
            print(commit_message)
        print("=" * 60)


if __name__ == "__main__":
    main()
