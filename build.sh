#!/bin/bash

# Exit on error
set -o errexit

echo "Installing Python dependencies..."
python -m pip install --upgrade pip
python -m pip install wheel setuptools
python -m pip install -r requirements.txt

echo "Initializing database..."
cd /opt/render/project/src/
PYTHONPATH=/opt/render/project/src python3 - << 'END'
from app import app, db
with app.app_context():
    db.create_all()
    print("Database initialized successfully!")
END

echo "Build completed successfully!" 