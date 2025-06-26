# Garden10 (정원사들 시즌10)

A FastAPI-based attendance management system for tracking daily GitHub commits in a 100-day challenge community. The system automatically monitors participants' GitHub activities and maintains attendance records from March 10, 2025 to June 17, 2025.

## 🌟 Features

- **Automated Attendance Tracking**: Monitors GitHub commits daily to mark attendance
- **User Dashboard**: Personal statistics and progress visualization
- **Admin Panel**: User management and system administration
- **GitHub Integration**: OAuth authentication and API integration
- **AI-powered Messages**: Personalized encouragement messages using OpenAI
- **RESTful API**: Well-documented API with Swagger/ReDoc support
- **Responsive UI**: Mobile-friendly web interface

## 🔗 Links

* **Production**: https://garden10.junho85.pe.kr
* **GitHub**: https://github.com/junho85/garden10

## 📋 Prerequisites

- Python 3.8+
- PostgreSQL or SQLite
- GitHub OAuth App credentials
- OpenAI API key (optional, for AI messages)

## 🚀 Installation

1. **Clone the repository**
```bash
git clone https://github.com/junho85/garden10.git
cd garden10
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure the application**
   - Copy `config.example.yaml` to `config.yaml`
   - Update configuration with your settings

## 🏃 Running the Application

### Development Mode
```bash
# Run without scheduler (for development)
python -m app.main --port=8010
```

### Production Mode
```bash
# Run with automated attendance checking
python -m app.main --scheduler --port=8010
```

## 📁 Project Structure

```
garden10/
├── app/
│   ├── main.py           # Application entry point
│   ├── config.py         # Configuration management
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   ├── routers/          # API endpoints
│   ├── static/           # Frontend assets
│   └── utils/            # Utility functions
├── test/                 # Test suite
├── docs/                 # Documentation
├── config.yaml           # Configuration file
└── requirements.txt      # Dependencies
```

## 🏗️ Architecture

For detailed architecture documentation, see [Architecture Documentation](docs/architecture.md)

## 📚 API Documentation

API documentation is available through Swagger UI and ReDoc:

### Local Development
- **Swagger UI**: http://localhost:8010/docs
- **ReDoc**: http://localhost:8010/redoc

### Production
- **Swagger UI**: https://garden10.junho85.pe.kr/docs
- **ReDoc**: https://garden10.junho85.pe.kr/redoc

## 🚀 Deployment

Deploy to production:

```bash
# Pull latest changes
git pull

# Install/update dependencies
pip install -r requirements.txt

# Run with scheduler enabled
python -m app.main --scheduler --port=8010
```
