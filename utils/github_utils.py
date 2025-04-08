import datetime
import os

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values


def get_db_attendance_data(github_id, start_date, end_date):
    """
    DB에서 특정 사용자의 출석 정보를 조회합니다.
    
    Args:
        github_id: GitHub 사용자 ID
        start_date: 시작 날짜 (YYYY-MM-DD 형식)
        end_date: 종료 날짜 (YYYY-MM-DD 형식)
        
    Returns:
        list: 출석 데이터 리스트
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT attendance_date, commit_count, is_attended
        FROM attendances
        WHERE github_id = %s AND attendance_date BETWEEN %s AND %s
        ORDER BY attendance_date
    """
    
    cursor.execute(query, (github_id, start_date, end_date))
    attendance_data = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return attendance_data


def get_user_attendance_stats(github_id, start_date, end_date):
    """
    특정 사용자의 출석 통계를 계산합니다.
    
    Args:
        github_id: GitHub 사용자 ID
        start_date: 시작 날짜 (YYYY-MM-DD 형식)
        end_date: 종료 날짜 (YYYY-MM-DD 형식)
        
    Returns:
        dict: 출석 통계 정보
    """
    attendance_data = get_db_attendance_data(github_id, start_date, end_date)
    
    if not attendance_data:
        return {
            "github_id": github_id,
            "total_days": 0,
            "attended_days": 0,
            "attendance_rate": 0,
            "total_commits": 0,
            "attendance_by_date": {}
        }
    
    total_days = len(attendance_data)
    attended_days = sum(1 for _, _, is_attended in attendance_data if is_attended)
    total_commits = sum(commit_count for _, commit_count, _ in attendance_data)
    attendance_rate = round(attended_days / total_days * 100, 1) if total_days > 0 else 0
    
    # 날짜별 출석 정보
    attendance_by_date = {}
    for date_obj, commit_count, is_attended in attendance_data:
        date_str = date_obj.isoformat()
        attendance_by_date[date_str] = {
            "commit_count": commit_count,
            "is_attended": is_attended
        }
    
    return {
        "github_id": github_id,
        "total_days": total_days,
        "attended_days": attended_days,
        "attendance_rate": attendance_rate,
        "total_commits": total_commits,
        "attendance_by_date": attendance_by_date
    }


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

    github_commits = [
        (
            github_id,
            commit_data.get("sha"),
            commit_data.get("repository", {}).get("full_name"),
            commit_data.get("commit", {}).get("message"),
            commit_data.get("html_url"),
            commit_data.get("commit", {}).get("author", {}).get("date"),
            commit_data.get("repository", {}).get("private", False),
        )
        for commit_data in commits
    ]

    query = """
        INSERT INTO github_commits (github_id, commit_id, repository, message, commit_url, commit_date, is_private)
        VALUES %s
        ON CONFLICT (commit_id, repository) DO NOTHING;
    """

    execute_values(cursor, query, github_commits, template="(%s, %s, %s, %s, %s, %s, %s)")
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
    load_dotenv()

    start_date = "2025-03-10"
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date_obj = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    # Add 99 days to start_date
    end_date_obj = start_date_obj + datetime.timedelta(days=99)
    # Convert back to string format
    end_date = end_date_obj.strftime("%Y-%m-%d")

    # 현재 날짜가 시작일 기준 몇일째인지 계산
    current_date_obj = datetime.datetime.strptime(current_date, "%Y-%m-%d")
    days_since_start = (current_date_obj - start_date_obj).days + 1

    # 사용자 목록 DB에서 조회
    users = get_users_from_db()

    print("출석 응원 메시지 작성해줘. 오늘이 몇일째인지도 알려줘. 마크다운을 사용하지 말아줘.")
    print(f"현재 정원사들 시즌10 {days_since_start}일째입니다!")
    print("시작일 :", start_date)
    print("오늘 날짜 :", current_date)
    print("종료일 :", end_date)

    for user in users:
        github_id = user[0]

        try:
            # 사용자 출석 통계 조회
            stats = get_user_attendance_stats(github_id, start_date, current_date)
            
            if stats["total_days"] == 0:
                print(f"{github_id} 유저의 출석 정보를 찾을 수 없습니다.")
                continue
            
            print(f"\n{github_id} 유저 출석 현황:")
            print(f"총 출석 일수: {stats['attended_days']}/{stats['total_days']}일 (출석률: {stats['attendance_rate']}%)")
            print(f"총 커밋 수: {stats['total_commits']}개")
            
            # 날짜별 출석 정보 출력
            for date_str, info in sorted(stats["attendance_by_date"].items()):
                status = "✅ 출석" if info["is_attended"] else "❌ 미출석"
                print(f"{date_str}: {status} (커밋 {info['commit_count']}개)")
                
        except Exception as e:
            print(f"에러 발생 (유저: {github_id}):", e)
            continue
            
        print("=" * 60)


if __name__ == "__main__":
    main()
