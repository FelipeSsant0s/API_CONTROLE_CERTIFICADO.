#!/bin/bash

# Exit on error
set -o errexit

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
python -m pip install wheel setuptools
python -m pip install --no-cache-dir -r requirements.txt

# Initialize database
python << END
from app import db, app
with app.app_context():
    db.create_all()
END 