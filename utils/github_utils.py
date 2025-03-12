import os
import requests
from dotenv import load_dotenv
import yaml


def get_commit_history(username, start_date, end_date, page=1, per_page=30, github_token=None):
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
        "Authorization": f"token {github_token}",
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        raise Exception(f"API 요청 실패: {response.status_code} {response.text}")

    data = response.json()
    commits = data.get("items", [])
    return commits


def count_commits_by_date(commits):
    from collections import Counter
    commit_dates = [commit.get("commit", {}).get("author", {}).get("date", "").split("T")[0] for commit in commits]
    return Counter(commit_dates)



import psycopg2
from psycopg2.extras import execute_values
import os
from dotenv import load_dotenv

def save_commits_to_db(username, commits):
    load_dotenv()
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", 5432)
    )
    cursor = conn.cursor()

    commit_data = [
        (
            username,
            commit.get("sha"),
            commit.get("commit", {}).get("message"),
            commit.get("commit", {}).get("author", {}).get("date"),
            commit.get("repository", {}).get("full_name"),
            commit.get("html_url")
        )
        for commit in commits
    ]

    query = """
        INSERT INTO github_commits (username, commit_hash, commit_message, commit_date, repo_name, commit_url)
        VALUES %s
        ON CONFLICT (commit_hash, repo_name) DO NOTHING;
    """

    execute_values(cursor, query, commit_data, template="(%s, %s, %s, %s, %s, %s)")
    conn.commit()
    cursor.close()
    conn.close()


def main():
    with open("config.yaml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    
    # 공통 GitHub API 토큰 가져오기
    common_github_token = os.getenv("GITHUB_TOKEN")
    
    start_date = "2025-03-10"
    end_date = "2025-03-12"
    
    # 사용자 목록 가져오기
    users_config = config.get("users", [])
    
    for user_item in users_config:
        # 사용자 정보 추출
        github_id = None
        user_github_token = None
        
        if isinstance(user_item, str):
            github_id = user_item
        elif isinstance(user_item, dict) and 'github_id' in user_item:
            github_id = user_item['github_id']
            # 사용자별 토큰이 있으면 사용
            if 'github_api_token' in user_item:
                user_github_token = user_item['github_api_token']
        
        if not github_id:
            continue
            
        try:
            # 사용자별 토큰이 있으면 사용, 없으면 공통 토큰 사용
            commits = get_commit_history(github_id, start_date, end_date, github_token=user_github_token or common_github_token)
        except Exception as e:
            print(f"에러 발생 (유저: {github_id}):", e)
            continue

        if not commits:
            print(f"{github_id} 유저의 커밋 이력을 찾을 수 없습니다.")
            continue

        # DB에 저장
        save_commits_to_db(github_id, commits)
        # print(f"{github_id} 유저의 커밋 이력이 DB에 저장되었습니다. (총 {len(commits)}개)")

        # TODO DB에 저장한 내용을 기준으로 통계 정보 출력
        print(f"\n{github_id} 유저의 커밋 이력 (총 {len(commits)}개):")
        commits_by_date = count_commits_by_date(commits)
        for commit_date, count in sorted(commits_by_date.items()):
            print(f"{commit_date}: {count}개")
        print("=" * 60)


if __name__ == "__main__":
    main()
