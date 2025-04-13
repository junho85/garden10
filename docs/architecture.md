# 정원사들 시즌10 출석부 시스템 아키텍처
정원사들 시즌10 모임 출석부 설계문서입니다.

시즌10의 시작일은 2025년 3월 10일이고 100일 동안 진행됩니다.

## 프로젝트 개요
정원사들 시즌10 모임은 참여자들이 매일 GitHub에 1회 이상 커밋하는 100일 챌린지입니다. 이 시스템은 참여자들의 GitHub 커밋을 추적하고 출석 현황을 시각화하는 웹 애플리케이션입니다.

- **진행 기간**: 2025년 3월 10일부터 100일 (2025년 6월 17일까지)
- **출석 기준**: 하루 1회 이상 GitHub 커밋
- **주요 기능**: 자동 커밋 추적, (TODO) 출석 통계 시각화, (TODO) 미출석자 알림

## 시스템 아키텍처

### 기술 스택
- **백엔드**: Python FastAPI
- **데이터베이스**: PostgreSQL
- **프론트엔드**: HTML/CSS/JavaScript (FastAPI의 static files로 제공)
- **스케줄러**: APScheduler (Python)
- **외부 API**: GitHub API, 카카오톡 메시지 API

### 데이터베이스 스키마

#### users 테이블
사용자 정보 및 GitHub 계정 정보를 저장합니다.
```sql
CREATE TABLE users
(
    id                 SERIAL PRIMARY KEY,
    github_id          VARCHAR(255) UNIQUE NOT NULL,
    github_api_token   TEXT,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### github_commits 테이블
사용자별 GitHub 커밋 기록을 저장합니다.
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
```

#### attendance 테이블
일별 출석 현황을 저장합니다. github_commits 테이블의 내용을 이용해서 생성합니다.
```sql
CREATE TABLE attendance (
    id SERIAL PRIMARY KEY,
    github_id      VARCHAR(255) NOT NULL,
    attendance_date DATE NOT NULL,
    is_attended BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (github_id, attendance_date)
);
```

### 컴포넌트 구조

#### 서비스 계층 (`/app/services/`)
1. **GitHub Service (`github_service.py`)**
   - GitHub API를 통해 사용자별 커밋 내역 조회
   - 커밋 데이터 정제 및 가공
   - 에러 처리 및 재시도 로직

2. **Attendance Service (`attendance_service.py`)**
   - 커밋 내역 기반 출석 여부 판단
   - 출석 데이터 DB 저장 및 조회
   - 출석 통계 데이터 집계

#### API 엔드포인트 (`/app/routers/`)
1. **사용자 관리 (`/api/users`)**
   - `GET /api/users`: 모든 사용자 목록 조회
   - `GET /api/users/{user_id}`: ID로 사용자 조회
   - `GET /api/users/github/{github_id}`: GitHub ID로 사용자 조회
   - `POST /api/users`: 새 사용자 등록 (관리자 권한 필요)
   - `PUT /api/users/{user_id}`: 사용자 정보 업데이트 (관리자 권한 필요)

2. **출석 데이터 관리 (`/api/attendance`)**
   - `POST /api/attendance/check`: 모든 사용자의 출석 체크를 실행
   - `POST /api/attendance/check/{github_id}`: 특정 사용자의 출석 체크를 실행
   - `GET /api/attendance/history/{github_id}`: 특정 사용자의 출석 기록을 조회
   - `GET /api/attendance/stats`: 출석 통계를 조회
   - `GET /api/attendance/stats/{date_str}`: 특정 날짜의 출석 통계를 조회
   - `GET /api/attendance/ranking`: 출석률 순위를 조회
   - `GET /api/attendance/{date_str}`: 특정 날짜의 출석 현황을 조회

#### 스케줄러
- 1시간 간격으로 출석 데이터 자동 갱신
- 매일 오후 10시에 미출석자 대상 알림 메시지 발송
  - 미출석자 명단 집계
  - 카카오톡 API를 통한 관리자 알림

## 사용자 인터페이스

### 레이아웃 구조
1. **GNB (Global Navigation Bar)**
   - 시스템 타이틀 및 로고
   - 출석부 수동 갱신 버튼 (중복 실행 방지 처리)

2. **대시보드 영역**
   - 전체 참여자 프로필 그리드뷰
   - 챌린지 진행률 표시 (프로그레스 바)
   - 주요 통계 요약 (전체 출석률, 총 출석/미출석 수)

3. **상세 데이터 영역**
   - **오늘의 출석부**: 현재 날짜 기준 참여자별 출석 현황 (이모지 표시)
   - **전체 출석부**: 전체 기간 출석 현황 테이블
     - 사용자별 출석률, 순위
     - 일별 출석 데이터 (아래쪽)
   - **통계 시각화**:
     - 출석률 순위 차트
     - 일별 출석률 추이 그래프
     - 요일별 출석률 비교
     - 시간대별 커밋 분포 히스토그램

## 처리 흐름

### 출석 데이터 수집 프로세스
1. 데이터베이스에서 모든 사용자 정보 조회
2. 각 사용자별 GitHub API 호출
   - API 요청 제한 고려 (rate limiting)
   - 토큰 인증 처리
3. 수집된 커밋 데이터를 github_commits 테이블에 저장
4. 커밋 데이터 기반 출석 여부 판단 및 attendance 테이블 업데이트

### 알림 프로세스 (오후 10시)
1. 당일 미출석자 명단 조회
2. 알림 메시지 템플릿에 미출석자 정보 삽입
3. 카카오톡 API를 통해 관리자에게 알림 메시지 발송
4. 알림 발송 결과 로깅

## 성능 및 확장성 고려사항
- GitHub API 호출 최적화 (캐싱, 배치 처리)
- 데이터베이스 인덱싱 전략 (날짜, 사용자명 기준)
- 대시보드 성능 최적화 (데이터 캐싱, 비동기 로딩)
- 사용자 수 증가에 따른 확장성 고려
