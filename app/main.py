from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from app.routers import users, attendance, auth, github_commits
import os
# from app.scheduler import init_scheduler
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="정원사들 시즌10")

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

# 앱 시작 이벤트
# @app.on_event("startup")
# async def startup_event():
#     logger.info("애플리케이션 시작")
#     # 스케줄러 초기화
#     init_scheduler()

# 앱 종료 이벤트
# @app.on_event("shutdown")
# async def shutdown_event():
#     logger.info("애플리케이션 종료")

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open(os.path.join("app", "static", "index.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.get("/users/{github_id}", response_class=HTMLResponse)
async def read_user_profile():
    """사용자 프로필 페이지를 제공합니다."""
    with open(os.path.join("app", "static", "user_profile.html"), "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)