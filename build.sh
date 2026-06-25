#!/usr/bin/env bash
set -euo pipefail

echo "============================================"
echo " Retail Management System — Build Script"
echo "============================================"

echo ""
echo "[1/6] Installing Node.js dependencies..."
npm install

echo ""
echo "[2/6] Building Tailwind CSS..."
npm run build:css

echo ""
echo "[3/6] Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "[4/6] Ensuring logs directory exists..."
mkdir -p logs

echo ""
echo "[5/6] Collecting static files..."
python manage.py collectstatic --noinput

echo ""
echo "[6/6] Running database migrations..."
python manage.py migrate

echo ""
echo "---------------------------------------------"
echo " Seeding demo data..."
python manage.py seed_demo_data

echo ""
echo "============================================"
echo " Build complete!"
echo "============================================"
