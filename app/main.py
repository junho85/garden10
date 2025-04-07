from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.routers import users, attendance, auth, github_commits
import os
import argparse
from app.scheduler import init_scheduler
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 앱 라이프스팬 관리 (최신 FastAPI 권장 방식)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 애플리케이션 시작 시 실행
    logger.info("애플리케이션 시작")
    
    # 환경 변수를 통해 스케줄러 활성화 여부 결정
    run_scheduler = os.environ.get("ENABLE_SCHEDULER", "false").lower() == "true"
    
    if run_scheduler:
        logger.info("스케줄러가 활성화되었습니다. 1시간 간격으로 출석 체크가 실행됩니다.")
    else:
        logger.info("스케줄러가 비활성화되었습니다.")
        
    # 스케줄러 초기화
    init_scheduler(run_scheduler=run_scheduler)
    
    yield
    
    # 애플리케이션 종료 시 실행
    logger.info("애플리케이션 종료")

# FastAPI 앱 초기화 (lifespan 매니저 포함)
app = FastAPI(title="정원사들 시즌10", lifespan=lifespan)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(users.router, prefix="/api", tags=["users"])
app.include_router(attendance.router, prefix="/api", tags=["attendance"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(github_commits.router, prefix="/api", tags=["github_commits"])

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/favicon.ico")
async def get_favicon():
    return FileResponse("app/static/favicon.ico")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open(os.path.join("app", "static", "index.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.get("/users/{github_id}", response_class=HTMLResponse)
async def read_user_profile():
    """사용자 프로필 페이지를 제공합니다."""
    with open(os.path.join("app", "static", "user_profile.html"), "r", encoding="utf-8") as f:
        return f.read()

def parse_args():
    """명령행 인수를 파싱합니다."""
    parser = argparse.ArgumentParser(description="정원사들 시즌10 애플리케이션")
    parser.add_argument("--scheduler", action="store_true", help="1시간 간격으로 실행되는 스케줄러를 활성화합니다")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="서버 호스트 (기본값: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="서버 포트 (기본값: 8000)")
    return parser.parse_args()

if __name__ == "__main__":
    import uvicorn
    
    # 명령행 인수 파싱
    args = parse_args()
    
    # 스케줄러 활성화 여부에 따라 환경 변수 설정
    if args.scheduler:
        logger.info("스케줄러가 활성화되었습니다. 1시간 간격으로 출석 체크가 실행됩니다.")
        os.environ["ENABLE_SCHEDULER"] = "true"
    else:
        logger.info("스케줄러가 비활성화되었습니다.")
        os.environ["ENABLE_SCHEDULER"] = "false"
    
    # 서버 실행
    uvicorn.run(
        "app.main:app", 
        host=args.host, 
        port=args.port, 
        reload=False  # 스케줄러 사용 시에는 reload=False로 설정하는 것이 좋습니다.
    )