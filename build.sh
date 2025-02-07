#!/bin/bash
# exit on error
set -o errexit

# Upgrade pip and install base dependencies
python -m pip install --upgrade pip
pip install wheel setuptools

# Install openpyxl explicitly first
pip install openpyxl==3.1.2
pip install et-xmlfile==1.1.0

# Install other dependencies
pip install --no-cache-dir -r requirements.txt

# Initialize database
python << END
from app import db, app
with app.app_context():
    db.create_all()
END 