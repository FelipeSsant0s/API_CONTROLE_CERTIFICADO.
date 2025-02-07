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
from sqlalchemy import create_engine, text, MetaData, Table, Column, String
from sqlalchemy.schema import CreateTable

with app.app_context():
    try:
        # Get database URL from app config
        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        
        # Create SQLAlchemy engine
        engine = create_engine(db_url)
        
        # Create MetaData instance
        metadata = MetaData()
        
        # Reflect existing tables
        metadata.reflect(bind=engine)
        
        # Check if certificado table exists and needs modification
        if 'certificado' in metadata.tables:
            with engine.connect() as connection:
                # Get current column types
                inspector = sa.inspect(engine)
                columns = inspector.get_columns('certificado')
                needs_update = False
                
                # Check column sizes
                for column in columns:
                    if column['name'] in ['cnpj', 'telefone', 'status']:
                        if hasattr(column['type'], 'length') and column['type'].length < 30:
                            needs_update = True
                            break
                
                if needs_update:
                    print("Updating column sizes while preserving data...")
                    # Create temporary table
                    connection.execute(text("""
                        CREATE TABLE certificado_temp AS SELECT * FROM certificado;
                        DROP TABLE certificado;
                        
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
                        
                        INSERT INTO certificado 
                        SELECT * FROM certificado_temp;
                        
                        DROP TABLE certificado_temp;
                        
                        CREATE UNIQUE INDEX unique_cnpj_per_user ON certificado (cnpj, user_id);
                    """))
                    print("Table structure updated successfully while preserving data!")
                else:
                    print("Table structure is already up to date!")
        else:
            # If table doesn't exist, create it
            print("Creating initial table structure...")
            with engine.connect() as connection:
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS certificado (
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
                    
                    CREATE UNIQUE INDEX IF NOT EXISTS unique_cnpj_per_user ON certificado (cnpj, user_id);
                """))
                print("Initial table structure created successfully!")
        
        print("Database initialization completed successfully!")
    except Exception as e:
        print(f"Error during database initialization: {str(e)}")
        raise

END

echo "Build completed successfully!" 