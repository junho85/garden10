import os

import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2.extras import execute_values


def get_commit_history(username, start_date, end_date, page=1, per_page=100, github_token=None):
    # TODO API 로 확인되고 나면 여기 코드는 제거
    # .env 파일에서 환경변수를 로드
    # load_dotenv()
    # github_token = os.getenv("GITHUB_TOKEN")
    # if not github_token:
    #     raise Exception("GITHUB_TOKEN 이 설정되어 있지 않습니다. .env 파일을 확인하세요.")

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


def get_db_connection():
    """Returns a database connection object from environment variables."""
    load_dotenv()
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", 5432),
        sslmode="require",
        gssencmode="disable",
    )


def save_commits_to_db(github_id, commits):
    conn = get_db_connection()
    cursor = conn.cursor()

    commit_data = [
        (
            github_id,
            commit.get("sha"),
            commit.get("repository", {}).get("full_name"),
            commit.get("commit", {}).get("message"),
            commit.get("html_url"),
            commit.get("commit", {}).get("author", {}).get("date"),
        )
        for commit in commits
    ]

    query = """
        INSERT INTO github_commits (github_id, commit_id, repository, message, commit_url, commit_date)
        VALUES %s
        ON CONFLICT (commit_id, repository) DO NOTHING;
    """

    execute_values(cursor, query, commit_data, template="(%s, %s, %s, %s, %s, %s)")
    conn.commit()
    cursor.close()
    conn.close()


def get_users_from_db():
    """
    데이터베이스에서 사용자 정보를 조회하는 함수
    
    Returns:
        list: (github_id, github_api_token) 튜플 목록
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT github_id, github_api_token FROM users")
    users = cursor.fetchall()

    cursor.close()
    conn.close()

    return users


def main():
    # 공통 GitHub API 토큰 가져오기
    load_dotenv()
    common_github_token = os.getenv("GITHUB_TOKEN")

    start_date = "2025-03-10"
    end_date = "2025-03-21"

    # 사용자 목록 DB에서 조회
    users = get_users_from_db()

    print("출석 응원 메시지 작성해줘. 오늘이 몇일째인지도 알려줘.")
    print("시작일 :", start_date)
    print("오늘 날짜 :", end_date)

    for user in users:
        github_id = user[0]
        user_github_token = user[1]

        # 토큰이 없으면 기본 토큰 사용
        if not user_github_token:
            user_github_token = common_github_token

        try:
            # GitHub API 호출에 사용할 토큰 결정
            github_token = user_github_token

            # print(f"\n{github_id} 유저의 커밋 이력을 조회합니다. (토큰: {github_token})")
            commits = get_commit_history(github_id, start_date, end_date, github_token=github_token)
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
