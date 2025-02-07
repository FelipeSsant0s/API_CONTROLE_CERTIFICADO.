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
from sqlalchemy import create_engine, text

with app.app_context():
    try:
        # Get database URL from app config
        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        
        # Create SQLAlchemy engine
        engine = create_engine(db_url)
        
        with engine.connect() as connection:
            # Drop and recreate the certificado table with correct column sizes
            connection.execute(text("""
                DROP TABLE IF EXISTS certificado;
                
                CREATE TABLE certificado (
                    id SERIAL PRIMARY KEY,
                    razao_social VARCHAR(200) NOT NULL,
                    nome_fantasia VARCHAR(200) NOT NULL,
                    cnpj VARCHAR(30) NOT NULL,
                    telefone VARCHAR(30) NOT NULL,
                    data_emissao TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    data_validade TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    status VARCHAR(30) NOT NULL,
                    observacoes TEXT,
                    user_id INTEGER NOT NULL REFERENCES "user" (id)
                );
                
                CREATE UNIQUE INDEX unique_cnpj_per_user ON certificado (cnpj, user_id);
            """))
            
            connection.commit()
            print("Database tables recreated successfully!")
            
    except Exception as e:
        print(f"Error during database initialization: {str(e)}")
        raise

END

echo "Build completed successfully!" 