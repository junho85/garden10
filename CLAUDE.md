# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Garden10 (정원사들 시즌10) is a FastAPI-based attendance management system for a 100-day GitHub commit challenge community. The system tracks daily GitHub commits as attendance records for participants from March 10, 2025 to June 17, 2025.

## Development Commands

### Running the Application
```bash
# Development server (without scheduler)
python -m app.main --port=8010

# Production server (with automated attendance checking)
python -m app.main --scheduler --port=8010
```

### Testing
```bash
# Run all tests
python -m pytest test/

# Run specific test file
python -m pytest test/services/test_attendance_service.py

# Run with verbose output
python -m pytest -v test/
```

### Deployment
```bash
git pull
pip install -r requirements.txt
python -m app.main --port=8010
```

## Architecture Overview

### Service Layer Pattern
- **Models** (`app/models/`): SQLAlchemy ORM entities (User, Attendance, GitHubCommit)
- **Services** (`app/services/`): Business logic layer containing core functionality
- **Routers** (`app/routers/`): FastAPI route handlers (thin controllers)
- **Schemas** (`app/schemas/`): Pydantic models for API validation

### Key Services
- **attendance_service.py**: Core attendance logic, GitHub commit checking
- **github_service.py**: GitHub API integration and commit data management
- **admin_service.py**: Administrative functions and user management
- **openai_service.py**: AI-generated encouragement messages

### Configuration Management
- Configuration loaded from `config.yaml` via Pydantic models in `app/config.py`
- **Important**: `config.project` is a Pydantic object, access attributes with dot notation (`config.project.start_date`), not dictionary keys (`config.project["start_date"]`)

### Database Schema
Three main tables with clear relationships:
- `users`: GitHub user information and API tokens
- `github_commits`: Raw commit data from GitHub API
- `attendance`: Daily attendance records derived from commits

### Authentication & Authorization
- JWT-based authentication with GitHub OAuth
- Admin access controlled by API key (`admin.api_key` in config)
- User sessions managed via HTTP-only cookies

## Critical Implementation Details

### Date Handling
- All project date calculations use `start_date` + `total_days - 1` for end date
- Project completion determined by `date.today() > project_end_date`
- APIs default to project period (2025-03-10 to 2025-06-17) when no date range specified

### GitHub API Integration
- Automated hourly attendance checking via APScheduler
- Individual and bulk commit data retrieval
- Rate limiting and token management for GitHub API calls

### Frontend Architecture
- Server-side rendered with static assets in `app/static/`
- Main dashboard: `index.html` with `main.js`
- User profiles: `user_profile.html` with embedded JavaScript
- No build system - direct HTML/CSS/JavaScript serving

### Testing Structure
- Unit tests for services in `test/services/`
- Integration tests in `test/integration/`
- Configuration-based test setup in `test/test_config.py`

## Important Patterns

### Error Handling
Centralized error handling in `app/utils/error_utils.py` with consistent HTTP exception patterns.

### API Response Format
Use `service_result_to_response()` for consistent API responses from service layer operations.

### Logging
Comprehensive logging with daily rotating files. All service operations should include appropriate log statements.

### Scheduler Management
APScheduler runs independently and can be enabled/disabled via command line flag. Attendance checking jobs are configured in service layer.