#!/bin/bash

# Exit on error
set -o errexit

echo "Installing Python dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Initializing database..."
python << END
from app import db, app
import sqlalchemy as sa
from sqlalchemy import create_engine, MetaData, Table, Column, String

with app.app_context():
    try:
        # Get database URL from app config
        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        
        # Create SQLAlchemy engine
        engine = create_engine(db_url)
        
        # Create MetaData instance
        metadata = MetaData()
        
        # Try to reflect existing tables
        metadata.reflect(bind=engine)
        
        # If certificado table exists, alter column types
        if 'certificado' in metadata.tables:
            with engine.begin() as connection:
                # Alter CNPJ column
                connection.execute(sa.text(
                    "ALTER TABLE certificado ALTER COLUMN cnpj TYPE varchar(30);"
                ))
                # Alter telefone column
                connection.execute(sa.text(
                    "ALTER TABLE certificado ALTER COLUMN telefone TYPE varchar(30);"
                ))
                print("Altered existing table columns")
        else:
            # If table doesn't exist, create all tables
            db.create_all()
            print("Created all tables with new structure")
        
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Error during database initialization: {str(e)}")
        raise
END

echo "Build completed successfully!" 