# psycopg3 Migration for Python 3.13 Compatibility

## Overview
This project has been migrated from `psycopg2-binary` to `psycopg[binary]` (psycopg3) to support Python 3.13 deployment on Render.

## Problem
The original error on Render with Python 3.13:
```
ImportError: undefined symbol: _PyInterpreterState_Get
```

This was caused by `psycopg2-binary==2.9.9` being incompatible with Python 3.13's ABI changes.

## Solution
Migrated to psycopg3, which is:
- ✅ Fully compatible with Python 3.13
- ✅ Backward compatible with SQLAlchemy 2.0+
- ✅ Faster and more modern than psycopg2
- ✅ Drop-in replacement with minimal code changes

## Changes Made

### 1. requirements.txt
**Before:**
```
psycopg2-binary==2.9.9
```

**After:**
```
psycopg[binary]>=3.1.0
```

### 2. app/core/config.py
**Before:**
```python
@property
def database_url_sync(self) -> str:
    """Get synchronous database URL for Alembic migrations."""
    return self.database_url.replace("+asyncpg", "")
```

**After:**
```python
@property
def database_url_sync(self) -> str:
    """Get synchronous database URL for Alembic migrations and psycopg3."""
    # Replace asyncpg with psycopg (psycopg3 dialect)
    return self.database_url.replace("+asyncpg", "+psycopg")
```

This changes the dialect from `postgresql://` (which defaults to psycopg2) to `postgresql+psycopg://` (psycopg3).

### 3. No Other Changes Needed
- ✅ No changes to `app/db/base.py` (no direct psycopg2 imports)
- ✅ No changes to `app/main.py`
- ✅ No changes to other application code
- ✅ SQLAlchemy 2.0.36 already supports psycopg3

## Testing

### Local Testing (Python 3.13)
```bash
# Install updated dependencies
pip install -r requirements.txt

# Run migration test
python test_psycopg3_migration.py

# Start the application
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

### Expected Output
```
✅ psycopg3 imported successfully
✅ SQLAlchemy imported successfully
✅ Config loaded successfully
✅ Sync URL correctly uses psycopg dialect
✅ Database engines created successfully
✅ Models imported successfully
✅ Database connection successful
🎉 All tests passed! psycopg3 migration successful!
```

## Deployment on Render

### Build Command
```bash
pip install -r requirements.txt
```

### Start Command
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Environment Variables
Ensure these are set in Render:
- `DATABASE_URL`: Your PostgreSQL connection string
- `SECRET_KEY`: Your application secret key
- `JWT_SECRET_KEY`: Your JWT secret key
- `REDIS_URL`: Your Redis connection string (if applicable)

## Compatibility

### Python Versions
- ✅ Python 3.13 (primary target)
- ✅ Python 3.12
- ✅ Python 3.11
- ✅ Python 3.10

### Database Versions
- ✅ PostgreSQL 16
- ✅ PostgreSQL 15
- ✅ PostgreSQL 14
- ✅ PostgreSQL 13

## Performance Benefits
psycopg3 offers several improvements over psycopg2:
- 🚀 Better performance with connection pooling
- 🔒 Improved security with prepared statements
- 🎯 Native async support
- 📦 Smaller binary size
- 🔧 Better error messages

## Rollback (if needed)
If you need to rollback to psycopg2:

1. In `requirements.txt`:
   ```
   psycopg2-binary==2.9.9
   ```

2. In `app/core/config.py`:
   ```python
   return self.database_url.replace("+asyncpg", "")
   ```

3. Reinstall dependencies:
   ```bash
   pip install -r requirements.txt
   ```

**Note:** Rollback is only needed if deploying to Python <3.13. For Python 3.13, psycopg3 is required.

## References
- [psycopg3 Documentation](https://www.psycopg.org/psycopg3/docs/)
- [SQLAlchemy psycopg3 Support](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg)
- [Python 3.13 Release Notes](https://docs.python.org/3.13/whatsnew/3.13.html)

## Support
For issues or questions, check:
1. Run `python test_psycopg3_migration.py` to diagnose
2. Check Render logs for specific error messages
3. Verify environment variables are set correctly
4. Ensure PostgreSQL version is compatible (13+)
