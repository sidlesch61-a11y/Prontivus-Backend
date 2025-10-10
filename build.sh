#!/bin/bash
set -e

echo "=== Build Script Starting ==="
echo "Python version:"
python --version

echo "=== Installing Dependencies ==="
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo "=== Running Database Migrations ==="
echo "DATABASE_URL: ${DATABASE_URL:0:40}..."

if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL is not set!"
    exit 1
fi

echo "Running alembic migrations..."
python -m alembic -c app/db/alembic/alembic.ini upgrade head

if [ $? -eq 0 ]; then
    echo "=== Migrations Complete Successfully ==="
else
    echo "=== Migrations Failed with exit code $? ==="
    exit 1
fi

echo "=== Build Script Complete ==="

