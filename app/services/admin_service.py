import os
import psutil
import time
import httpx
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.github_commit import GitHubCommit
from app.models.user import User
from app.models.attendance import Attendance
from app.services.attendance_service import check_all_attendances
from app.services.github_service import get_all_users_attendance_stats
from app.utils.date_utils import get_kst_datetime_range
from app.config import config
from app.services.openai_service import get_openai_service


class AdminService:
    @staticmethod
    async def refresh_all_attendances(check_date: date, db: Session) -> Dict[str, Any]:
        result = await check_all_attendances(check_date=check_date, db=db)
        
        success_count = 0
        error_count = 0
        updated_users = []
        errors = []
        detailed_results = []
        
        for item in result.get("results", []):
            if item.get("status") == "success":
                success_count += 1
                github_id = item.get("github_id")
                updated_users.append(github_id)
                
                start_datetime, end_datetime = get_kst_datetime_range(check_date)
                
                commits = db.query(GitHubCommit).filter(
                    GitHubCommit.github_id == github_id,
                    GitHubCommit.commit_date >= start_datetime,
                    GitHubCommit.commit_date <= end_datetime
                ).all()
                
                commit_details = []
                for commit in commits:
                    commit_details.append({
                        "commit_id": commit.commit_id,
                        "repository": commit.repository,
                        "commit_date": commit.commit_date.isoformat(),
                        "message": commit.message
                    })
                
                attendance = db.query(Attendance).filter(
                    Attendance.github_id == github_id,
                    Attendance.attendance_date == check_date
                ).first()
                
                detailed_results.append({
                    "github_id": github_id,
                    "is_attended": item.get("is_attended", False),
                    "commit_count": item.get("commit_count", 0),
                    "action_performed": "updated" if attendance and attendance.updated_at else "created",
                    "commits": commit_details
                })
            else:
                error_count += 1
                errors.append({
                    "github_id": item.get("github_id"),
                    "error": item.get("message")
                })
        
        results = {
            "success": True,
            "message": "출석 데이터가 갱신되었습니다.",
            "date": check_date.isoformat(),
            "updated_users": updated_users,
            "detailed_results": detailed_results,
            "errors": errors,
            "stats": {
                "total": success_count + error_count,
                "success": success_count,
                "errors": error_count
            }
        }
        
        if errors:
            results["message"] = "일부 사용자의 출석 데이터가 갱신되지 않았습니다."
        
        return results
    
    @staticmethod
    def update_user_attendance(github_id: str, date_str: str, is_attended: bool, db: Session) -> Dict[str, Any]:
        user = db.query(User).filter(User.github_id == github_id).first()
        if not user:
            return None
        
        attendance = db.query(Attendance).filter(
            Attendance.github_id == github_id,
            Attendance.attendance_date == date_str
        ).first()
        
        check_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        start_datetime, end_datetime = get_kst_datetime_range(check_date)
        
        commits = db.query(GitHubCommit).filter(
            GitHubCommit.github_id == github_id,
            GitHubCommit.commit_date >= start_datetime,
            GitHubCommit.commit_date <= end_datetime
        ).all()
        
        commit_count = len(commits)
        
        if attendance:
            attendance.is_attended = is_attended
            attendance.commit_count = commit_count
            attendance.updated_at = datetime.utcnow()
            db.commit()
            message = "출석 상태가 업데이트되었습니다."
            action = "updated"
        else:
            new_attendance = Attendance(
                github_id=github_id,
                attendance_date=date_str,
                is_attended=is_attended,
                commit_count=commit_count,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(new_attendance)
            db.commit()
            message = "출석 상태가 새로 생성되었습니다."
            action = "created"
        
        commit_details = []
        for commit in commits:
            commit_details.append({
                "commit_id": commit.commit_id,
                "repository": commit.repository,
                "commit_date": commit.commit_date.isoformat(),
                "message": commit.message
            })
        
        return {
            "success": True,
            "message": message,
            "data": {
                "github_id": github_id,
                "date": date_str,
                "is_attended": is_attended,
                "commit_count": commit_count,
                "action_performed": action,
                "commits": commit_details
            }
        }
    
    @staticmethod
    def get_system_status() -> Dict[str, Any]:
        cpu_percent = psutil.cpu_percent(interval=1)
        
        memory = psutil.virtual_memory()
        memory_used_percent = memory.percent
        memory_used_mb = memory.used / (1024 * 1024)
        memory_total_mb = memory.total / (1024 * 1024)
        
        disk = psutil.disk_usage('/')
        disk_used_percent = disk.percent
        disk_used_gb = disk.used / (1024 * 1024 * 1024)
        disk_total_gb = disk.total / (1024 * 1024 * 1024)
        
        process = psutil.Process(os.getpid())
        process_start_time = datetime.fromtimestamp(process.create_time()).strftime('%Y-%m-%d %H:%M:%S')
        process_memory_mb = process.memory_info().rss / (1024 * 1024)
        
        boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M:%S')
        
        return {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "system": {
                "cpu_percent": cpu_percent,
                "memory": {
                    "percent": memory_used_percent,
                    "used_mb": round(memory_used_mb, 2),
                    "total_mb": round(memory_total_mb, 2)
                },
                "disk": {
                    "percent": disk_used_percent,
                    "used_gb": round(disk_used_gb, 2),
                    "total_gb": round(disk_total_gb, 2)
                },
                "boot_time": boot_time
            },
            "process": {
                "pid": os.getpid(),
                "start_time": process_start_time,
                "memory_mb": round(process_memory_mb, 2)
            }
        }
    
    @staticmethod
    async def check_github_api_status() -> Dict[str, Any]:
        start_time = time.time()
        
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.github.com/zen")
        
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)
        
        return {
            "status": "success",
            "message": "GitHub API 연결이 정상입니다.",
            "response_time_ms": response_time,
            "github_zen": response.text if response.status_code == 200 else None
        }
    
    @staticmethod
    async def add_new_user(github_id: str, db: Session) -> Dict[str, Any]:
        existing_user = db.query(User).filter(User.github_id == github_id).first()
        if existing_user:
            return {
                "success": False,
                "message": f"GitHub ID '{github_id}'는 이미 등록된 사용자입니다."
            }
        
        async with httpx.AsyncClient() as client:
            github_response = await client.get(f"https://api.github.com/users/{github_id}")
            
            if github_response.status_code != 200:
                return {
                    "success": False,
                    "message": f"GitHub에서 '{github_id}' 사용자를 찾을 수 없습니다."
                }
            
            github_user_info = github_response.json()
        
        new_user = User(
            github_id=github_id,
            github_api_token=None
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return {
            "success": True,
            "message": f"사용자 '{github_id}'가 성공적으로 추가되었습니다.",
            "user": {
                "id": new_user.id,
                "github_id": new_user.github_id,
                "github_profile_url": f"https://avatars.githubusercontent.com/{new_user.github_id}"
            }
        }
    
    @staticmethod
    def get_application_logs(limit: int = 50, date_filter: Optional[str] = None, 
                           level_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
        
        log_files = []
        if os.path.exists(log_dir):
            for file in os.listdir(log_dir):
                if file.startswith("garden10_") and file.endswith(".log"):
                    log_files.append(file)
        
        if not log_files:
            return []
        
        log_files.sort(reverse=True)
        
        log_file = None
        if date_filter:
            target_file = f"garden10_{date_filter}.log"
            if target_file in log_files:
                log_file = os.path.join(log_dir, target_file)
        
        if not log_file:
            log_file = os.path.join(log_dir, log_files[0])
        
        logs = []
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        parts = line.strip().split(' - ', 3)
                        if len(parts) >= 4:
                            timestamp_str, module, log_level, message = parts
                            
                            if level_filter and log_level.upper() != level_filter.upper():
                                continue
                            
                            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                            
                            logs.append({
                                "timestamp": timestamp,
                                "level": log_level,
                                "message": message
                            })
                    except Exception:
                        continue
        
        logs.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return logs[:limit]
    
    @staticmethod
    async def generate_motivational_prompt(prompt_template: str, db: Session) -> str:
        if config.project:
            start_date = config.project.start_date
            total_days = config.project.total_days
        else:
            start_date = "2025-03-10"
            total_days = 100
        
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        current_date = datetime.now().date()
        end_date_obj = start_date_obj + timedelta(days=total_days-1)
        end_date = end_date_obj.strftime("%Y-%m-%d")
        
        days_since_start = (current_date - start_date_obj).days + 1
        days_remaining = total_days - days_since_start
        
        users_stats = await get_all_users_attendance_stats(db, start_date, current_date.strftime("%Y-%m-%d"))
        
        prompt_base = prompt_template + f"\n현재 정원사들 시즌10 {days_since_start}일째입니다! (총 {total_days}일 중)\n"
        prompt_base += f"시작일: {start_date}\n"
        prompt_base += f"오늘 날짜: {current_date.strftime('%Y-%m-%d')}\n"
        prompt_base += f"종료일: {end_date}\n"
        prompt_base += f"남은 기간: {days_remaining}일\n\n"
        
        today_commits = {}
        for user_stat in users_stats:
            github_id = user_stat.get("github_id")
            
            start_datetime, end_datetime = get_kst_datetime_range(current_date)
            
            user_commits = db.query(GitHubCommit).filter(
                GitHubCommit.github_id == github_id,
                GitHubCommit.commit_date >= start_datetime,
                GitHubCommit.commit_date <= end_datetime,
                GitHubCommit.is_private == False
            ).all()
            
            if user_commits:
                today_commits[github_id] = user_commits
        
        for user_stat in users_stats:
            github_id = user_stat.get("github_id")
            
            if user_stat.get("total_days") == 0:
                prompt_base += f"{github_id} 유저의 출석 정보를 찾을 수 없습니다.\n"
                continue
            
            prompt_base += f"\n{github_id} 유저 출석 현황:\n"
            prompt_base += f"총 출석 일수: {user_stat.get('attended_days')}/{user_stat.get('total_days')}일 (전체 {total_days}일 중, 출석률: {user_stat.get('attendance_rate')}%)\n"
            
            progress_rate = (user_stat.get('attended_days') / total_days) * 100
            prompt_base += f"현재 진행률: {progress_rate:.1f}% (전체 {total_days}일 기준)\n"
            prompt_base += f"총 커밋 수: {user_stat.get('total_commits')}개\n"
            
            if github_id in today_commits and today_commits[github_id]:
                prompt_base += f"\n오늘의 공개 커밋 내역:\n"
                for commit in today_commits[github_id]:
                    prompt_base += f"- {commit.repository}: {commit.message.splitlines()[0]}\n"
                prompt_base += "\n"
            
            attendance_by_date = user_stat.get("attendance_by_date", {})
            one_week_ago = current_date - timedelta(days=6)
            recent_dates = [one_week_ago + timedelta(days=i) for i in range(7)]
            recent_dates_str = [d.strftime("%Y-%m-%d") for d in recent_dates]
            
            prompt_base += f"\n최근 1주일 출석 기록:\n"
            today_str = current_date.strftime("%Y-%m-%d")
            for date_str in sorted(attendance_by_date.keys()):
                if date_str in recent_dates_str:
                    info = attendance_by_date[date_str]
                    status = "✅ 출석" if info.get("is_attended") else "❌ 미출석"
                    date_display = f"{date_str} (오늘)" if date_str == today_str else date_str
                    prompt_base += f"{date_display}: {status} (커밋 {info.get('commit_count')}개)\n"
            
            prompt_base += "=" * 60 + "\n"
        
        return prompt_base