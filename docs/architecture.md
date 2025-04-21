# 정원사들 시즌10 출석부 시스템 아키텍처

정원사들 시즌10 모임 출석부 설계문서입니다.

시즌10의 시작일은 2025년 3월 10일이고 100일 동안 진행됩니다.

## 프로젝트 개요

정원사들 시즌10 모임은 참여자들이 매일 GitHub에 1회 이상 커밋하는 100일 챌린지입니다. 이 시스템은 참여자들의 GitHub 커밋을 추적하고 출석 현황을 시각화하는 웹 애플리케이션입니다.

- **진행 기간**: 2025년 3월 10일부터 100일 (2025년 6월 17일까지)
- **출석 기준**: 하루 1회 이상 GitHub 커밋
- **주요 기능**: 
  - 자동 커밋 추적
  - 출석 통계 시각화
  - (TODO) 미출석자 알림
  - 관리자 대시보드
  - 개인별 출석 현황

## 시스템 아키텍처

### 기술 스택

- **백엔드**: Python FastAPI
- **데이터베이스**: PostgreSQL
- **프론트엔드**: HTML/CSS/JavaScript (FastAPI의 static files로 제공)
- **스케줄러**: APScheduler (Python)
- **외부 API**: 
  - GitHub API (커밋 데이터 수집)
  - 카카오톡 메시지 API (알림 발송)
- **인증**: JWT 기반 인증 시스템
- **배포**: 
  - 직접 서버에 배포 (Linux)
  - (TODO) Docker, Docker Compose

### 데이터베이스 스키마

#### users 테이블
사용자 정보 및 GitHub 계정 정보를 저장합니다.
```sql
CREATE TABLE users
(
    id                 SERIAL PRIMARY KEY,
    github_id          VARCHAR(255) UNIQUE NOT NULL,
    github_api_token   TEXT,
    is_admin           BOOLEAN DEFAULT FALSE, -- TODO
    created_at         TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### github_commits 테이블
사용자별 GitHub 커밋 기록을 저장합니다. 커밋의 상세 정보를 포함하여 출석 판단의 기초 데이터로 활용합니다.
```sql
CREATE TABLE github_commits
(
    id          SERIAL PRIMARY KEY,
    github_id   VARCHAR(255)             NOT NULL,
    commit_id   VARCHAR(255)             NOT NULL,
    repository  VARCHAR(255)             NOT NULL,
    message     TEXT                     NOT NULL,
    commit_url  TEXT                     NOT NULL,
    commit_date TIMESTAMP WITH TIME ZONE NOT NULL,
    is_private  BOOLEAN                  NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    constraint unique_commit
        unique (commit_id, repository)
);
-- CREATE INDEX idx_github_commits_date ON github_commits(commit_date); TODO
-- CREATE INDEX idx_github_commits_user ON github_commits(github_id); TODO
```

#### attendance 테이블
일별 출석 현황을 저장합니다. github_commits 테이블의 내용을 이용해서 생성합니다.
```sql
CREATE TABLE attendance (
    id SERIAL PRIMARY KEY,
    github_id      VARCHAR(255) NOT NULL,
    attendance_date DATE NOT NULL,
    commit_count INT DEFAULT 0,
    is_attended BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (github_id, attendance_date)
);
-- CREATE INDEX idx_attendance_date ON attendance(attendance_date); TODO
-- CREATE INDEX idx_attendance_user ON attendance(github_id); TODO
```

### 컴포넌트 구조

#### 서비스 계층 (`/app/services/`)
1. **GitHub Service (`github_service.py`)**
   - GitHub API를 통해 사용자별 커밋 내역 조회
   - 커밋 데이터 정제 및 가공
   - 에러 처리 및 재시도 로직
   - API 호출 제한(rate limit) 관리
   - 비공개 저장소 접근 처리

2. **Attendance Service (`attendance_service.py`)**
   - 커밋 내역 기반 출석 여부 판단
   - 출석 데이터 DB 저장 및 조회
   - 출석 통계 데이터 집계
   - 순위 계산 알고리즘

3. **Auth Service (`auth_service.py`)**
   - 사용자 인증 및 권한 관리
   - JWT 토큰 발급 및 검증
   - 관리자 권한 확인

4. ** (TODO) Notification Service (`notification_service.py`)**
   - 미출석자 알림 메시지 생성
   - 카카오톡 API 연동
   - 관리자 알림 전송
    
#### API 엔드포인트 (`/app/routers/`)
- API 엔드포인트는 `/api`로 시작하며, 각 기능별로 그룹화되어 있습니다.
- API 문서는 다음 URL에서 확인할 수 있습니다:
  - http://localhost:8000/docs - FastAPI Swagger UI를 통해 API 문서화
  - http://localhost:8000/redoc - FastAPI ReDoc을 통해 API 문서화

1. **인증 관리 (`/api/auth`)**
   - `GET /api/auth/login`: GitHub ID로 로그인 및 JWT 토큰 발급
   - `GET /api/auth/me`: 현재 로그인한 사용자 정보 조회

2. **사용자 관리 (`/api/users`)**
   - `GET /api/users`: 모든 사용자 목록 조회
   - `GET /api/users/{user_id}`: ID로 사용자 조회
   - `GET /api/users/github/{github_id}`: GitHub ID로 사용자 조회
   - `POST /api/users`: 새 사용자 등록 (관리자 권한 필요)
   - `PUT /api/users/{user_id}`: 사용자 정보 업데이트 (관리자 권한 필요)

3. **출석 데이터 관리 (`/api/attendance`)**
   - `POST /api/attendance/check`: 모든 사용자의 출석 체크를 실행
   - `POST /api/attendance/check/{github_id}`: 특정 사용자의 출석 체크를 실행
   - `GET /api/attendance/history/{github_id}`: 특정 사용자의 출석 기록을 조회
   - `GET /api/attendance/stats`: 출석 통계를 조회
   - `GET /api/attendance/stats/{date_str}`: 특정 날짜의 출석 통계를 조회
   - `GET /api/attendance/ranking`: 출석률 순위를 조회
   - `GET /api/attendance/{date_str}`: 특정 날짜의 출석 현황을 조회
   
4. **GitHub 커밋 관리 (`/api/github-commits`)**
   - `GET /api/github-commits/{github_id}`: 특정 사용자의 GitHub 커밋 목록 조회
   
5. **관리자 기능 (`/api/admin`)**
   - TODO 

#### 스케줄러 (`/app/scheduler.py`)
- 등록된 작업:
  - **출석 데이터 갱신**: 1시간 간격으로 모든 사용자의 GitHub 커밋 데이터 조회 및 출석 상태 업데이트
  - **(TODO) 일일 알림**: 매일 오후 10시에 미출석자 대상 알림 메시지 발송
    - 미출석자 명단 집계
    - 카카오톡 API를 통한 관리자 알림
  - **(TODO) 동기부여 메시지**: 챌린지 참여자들에게 동기부여 메시지 생성 (OpenAI API 활용)
  - **(TODO) 데이터 백업**: 매일 자정에 데이터베이스 백업

- 스케줄러 구현 특징:
  - APScheduler를 활용한 작업 스케줄링
  - 작업 실행 결과 로깅
  - (TODO) 오류 발생 시 재시도 메커니즘
  - (TODO) 작업 중복 실행 방지

## 사용자 인터페이스

### 페이지 구성
1. **메인 페이지 (`/app/static/index.html`)**
   - 일반 사용자 대상 메인 화면
   - 출석 현황 및 요약 통계 제공
   - 개인별 출석 상태 확인 기능

2. **사용자 프로필 페이지 (`/app/static/user_profile.html`)**
   - 개인별 상세 출석 기록 및 통계
   - 커밋 내역 확인
   - 개인 성과 분석 및 시각화
   - (TODO) 개인 목표 설정 및 관리 기능
   - (TOOD) 개인 동기부여 메시지 제공
   - (TOOD) 개인 성과 공유 기능 (소셜 미디어 연동)
   - (TOOD) 개인 성과 리포트 다운로드 기능
   - (TOOD) 개인 성과 피드백 기능

3. **관리자 대시보드 (`/app/static/admin.html`)**
   - 관리자 전용 페이지
   - 전체 시스템 모니터링 및 관리
   - 사용자 관리, 알림 발송 등 관리자 기능 제공

### 레이아웃 구조
1. **GNB (Global Navigation Bar)**
   - 시스템 타이틀 및 로고
   - 출석부 수동 갱신 버튼 (중복 실행 방지 처리)
   - 사용자 메뉴 (로그인/로그아웃)
   - 페이지 내비게이션 링크

2. **대시보드 영역**
   - 전체 참여자 프로필 그리드뷰
   - 챌린지 진행률 표시 (프로그레스 바)
   - 주요 통계 요약 (전체 출석률, 총 출석/미출석 수)
   - 당일 출석 현황 요약 (출석/미출석 인원수)

3. **상세 데이터 영역**
   - **오늘의 출석부**: 현재 날짜 기준 참여자별 출석 현황 (이모지 표시)
   - **전체 출석부**: 전체 기간 출석 현황 테이블
     - 사용자별 출석률, 순위
     - 연속 출석일수, 최장 연속 출석일수
     - 일별 출석 데이터 (열 그래프)
   - **통계 시각화**:
     - 출석률 순위 차트 (막대 그래프)
     - 일별 출석률 추이 그래프 (선 그래프)
     - 요일별 출석률 비교 (막대 그래프)
     - 시간대별 커밋 분포 히스토그램 (24시간)
     - 주간/월간 출석 추이 (히트맵)

## 처리 흐름

### 출석 데이터 수집 프로세스
1. 스케줄러가 1시간 간격으로 출석 체크 작업 실행
2. 데이터베이스에서 모든 사용자 정보 조회
3. 각 사용자별 GitHub API 호출 및 커밋 내역 수집
   - API 요청 제한 고려 (rate limiting)
   - 토큰 인증 처리
   - 비공개 저장소 커밋 데이터 수집 (access token 이용)
4. 수집된 커밋 데이터를 필터링하고 가공
   - 중복 커밋 제외
5. 가공된 커밋 데이터를 github_commits 테이블에 저장
6. 커밋 데이터 기반 출석 여부 판단 및 attendance 테이블 업데이트
7. 통계 데이터 재계산 (출석률, 순위 등)
8. 작업 결과 로깅

### 사용자 인증 프로세스
1. 사용자가 GitHub ID로 로그인 요청
2. 시스템이 데이터베이스에서 사용자 정보 조회
3. 사용자 정보 확인 후 JWT 토큰 생성 및 발급
4. 클라이언트는 이후 API 요청 시 Authorization 헤더에 토큰 포함
5. API 엔드포인트에서 JWT 토큰 검증 및 권한 확인
6. 관리자 권한이 필요한 API는 추가 권한 검증 수행

### (TODO) 알림 프로세스 (오후 10시)
1. 스케줄러가 매일 오후 10시에 알림 작업 실행
2. 당일 미출석자 명단 조회
3. 알림 메시지 템플릿에 미출석자 정보 삽입
4. 카카오톡 API를 통해 관리자에게 알림 메시지 발송
5. 알림 발송 결과 로깅

### 동기부여 메시지 생성 프로세스
1. 스케줄러가 매주 월요일 오전 9시에 작업 실행
2. 현재 진행 상태 및 출석 통계 데이터 수집
3. OpenAI API를 통해 맞춤형 동기부여 메시지 생성
4. 관리자 대시보드에 메시지 저장 및 표시

## 성능 및 확장성 고려사항

### 성능 최적화
- **GitHub API 호출 최적화**
  - API 호출 캐싱 (Redis 활용)
  - 배치 처리를 통한 API 요청 최소화
  - 비동기 처리를 통한 다중 사용자 동시 조회 최적화
  - Rate limiting 고려한 API 호출 제한 및 재시도 로직

- **데이터베이스 최적화**
  - 적절한 인덱싱 전략 (날짜, 사용자명 기준)
  - 빈번한 쿼리에 대한 최적화 (복합 인덱스 활용)
  - 데이터 파티셔닝 (날짜 기준)
  - 정기적인 DB 백업 및 유지보수

- **프론트엔드 성능 최적화**
  - 데이터 캐싱 (localStorage, sessionStorage 활용)
  - 비동기 데이터 로딩 (필요한 데이터만 요청)
  - 이미지 및 리소스 최적화
  - 렌더링 성능 개선 (가상 스크롤링, 지연 로딩)

### 확장성 고려사항
- **수평적 확장**
  - 마이크로서비스 아키텍처 적용 가능성
  - 컨테이너화를 통한 배포 및 관리 (Docker, Kubernetes)
  - 로드 밸런싱을 통한 요청 분산 처리

- **모니터링 및 로깅**
  - 중앙화된 로깅 시스템 구축
  - 실시간 시스템 모니터링 및 알림
  - 성능 지표 수집 및 분석

- **보안 고려사항**
  - JWT 토큰 보안 (만료 시간, 갱신 정책)
  - API 키 및 비밀 정보 관리 (환경 변수 활용)
  - HTTPS 적용 및 SSL 인증서 관리
  - 사용자 권한 관리 및 RBAC 구현

## 향후 개선 계획
- **기능 확장**
  - 모바일 앱 지원 (PWA 또는 네이티브 앱)
  - 소셜 기능 추가 (사용자 간 응원 메시지, 코멘트)
  - GitHub 이외 추가 플랫폼 지원 (GitLab, Bitbucket)

- **데이터 분석 강화**
  - 고급 분석 대시보드 제공
  - 개인화된 추천 시스템 개발
  - 머신러닝 기반 참여 예측 모델 구현

- **UX 개선**
  - 사용자 경험 개선을 위한 인터페이스 리디자인
  - 접근성 강화 (스크린 리더 지원, 키보드 내비게이션)
  - 다국어 지원
