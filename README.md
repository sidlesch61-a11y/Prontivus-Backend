# Prontivus Medical SaaS Backend

A production-ready FastAPI backend for Brazilian healthcare clinics with comprehensive EMR, AI consultation assistance, telemedicine, and TISS integration.

## Features

- **Multi-tenant Architecture** - Complete clinic isolation
- **AI Consultation Assistant** - Real-time audio processing and summarization
- **Telemedicine Platform** - WebRTC video consultations
- **TISS Integration** - Health insurance automation
- **Digital Prescriptions** - ICP-Brasil compliant signatures
- **Offline Sync** - Mobile app support
- **Security & Compliance** - LGPD ready with audit logging

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables:**
   ```bash
   export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/prontivus"
   export SECRET_KEY="your-secret-key"
   export REDIS_URL="redis://localhost:6379/0"
   ```

3. **Run database migrations:**
   ```bash
   alembic upgrade head
   ```

4. **Start the application:**
   ```bash
   python start.py
   ```

## API Documentation

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/health

## Architecture

- **FastAPI** - Modern async web framework
- **PostgreSQL** - Primary database with async support
- **Redis** - Caching and message broker
- **Celery** - Background task processing
- **SQLModel** - Type-safe ORM with Pydantic

## License

MIT License
