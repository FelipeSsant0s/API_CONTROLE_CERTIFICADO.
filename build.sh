#!/bin/bash

# Exit on error
set -o errexit

echo "Installing Python dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Initializing database..."
python << END
from app import db, app
with app.app_context():
    db.create_all()
    print("Database initialized successfully!")
END

echo "Build completed successfully!" 