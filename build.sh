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
from datetime import datetime
import json

def backup_table_data(connection, table_name):
    """Faz backup dos dados de uma tabela em formato JSON"""
    try:
        result = connection.execute(text(f'SELECT * FROM "{table_name}"'))
        data = [dict(row) for row in result]
        
        # Converter timestamps para string
        for row in data:
            for key, value in row.items():
                if isinstance(value, datetime):
                    row[key] = value.isoformat()
        
        backup_file = f'backup_{table_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(backup_file, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Backup da tabela {table_name} criado com sucesso: {backup_file}")
        return True
    except Exception as e:
        print(f"Erro ao fazer backup da tabela {table_name}: {str(e)}")
        return False

def safe_execute_with_backup(connection, table_name, sql_commands):
    """Executa comandos SQL com backup de segurança e rollback em caso de erro"""
    transaction = connection.begin()
    try:
        # Fazer backup antes de qualquer alteração
        if table_name in ['user', 'certificado']:
            if not backup_table_data(connection, table_name):
                raise Exception(f"Falha ao criar backup da tabela {table_name}")
        
        # Executar os comandos SQL
        for command in sql_commands.split(';'):
            if command.strip():
                connection.execute(text(command))
        
        # Commit se tudo deu certo
        transaction.commit()
        return True
    except Exception as e:
        # Rollback em caso de erro
        transaction.rollback()
        print(f"Erro durante a execução dos comandos SQL: {str(e)}")
        raise

with app.app_context():
    try:
        print("Iniciando processo de atualização do banco de dados...")
        
        # Get database URL from app config
        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        
        # Create SQLAlchemy engine
        engine = create_engine(db_url)
        
        # Create MetaData instance
        metadata = MetaData()
        
        # Reflect existing tables
        metadata.reflect(bind=engine)
        
        with engine.connect() as connection:
            # Verificar e atualizar a tabela de usuários
            if 'user' in metadata.tables:
                inspector = sa.inspect(engine)
                columns = inspector.get_columns('user')
                needs_update = False
                
                # Verificar se precisa atualizar alguma coluna
                for column in columns:
                    if column['name'] in ['username', 'email', 'name'] and (
                        not hasattr(column['type'], 'length') or column['type'].length < 120
                    ):
                        needs_update = True
                        break
                
                if needs_update:
                    print("Atualizando estrutura da tabela de usuários preservando dados...")
                    sql_commands = """
                        CREATE TABLE user_temp AS SELECT * FROM "user";
                        DROP TABLE "user";
                        
                        CREATE TABLE "user" (
                            id SERIAL PRIMARY KEY,
                            username VARCHAR(120) UNIQUE NOT NULL,
                            password_hash VARCHAR(200) NOT NULL,
                            email VARCHAR(120) UNIQUE NOT NULL,
                            name VARCHAR(120) NOT NULL
                        );
                        
                        INSERT INTO "user" SELECT * FROM user_temp;
                        DROP TABLE user_temp
                    """
                    safe_execute_with_backup(connection, 'user', sql_commands)
                    print("Tabela de usuários atualizada com sucesso!")
            else:
                print("Criando tabela de usuários...")
                sql_commands = """
                    CREATE TABLE "user" (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(120) UNIQUE NOT NULL,
                        password_hash VARCHAR(200) NOT NULL,
                        email VARCHAR(120) UNIQUE NOT NULL,
                        name VARCHAR(120) NOT NULL
                    )
                """
                safe_execute_with_backup(connection, 'user', sql_commands)
            
            # Verificar e atualizar a tabela de certificados
            if 'certificado' in metadata.tables:
                inspector = sa.inspect(engine)
                columns = inspector.get_columns('certificado')
                needs_update = False
                
                # Verificar se precisa atualizar alguma coluna
                for column in columns:
                    if column['name'] in ['cnpj', 'telefone', 'status'] and (
                        not hasattr(column['type'], 'length') or column['type'].length < 30
                    ):
                        needs_update = True
                        break
                
                if needs_update:
                    print("Atualizando estrutura da tabela de certificados preservando dados...")
                    sql_commands = """
                        CREATE TABLE certificado_temp AS SELECT * FROM certificado;
                        DROP TABLE certificado CASCADE;
                        
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
                        
                        INSERT INTO certificado SELECT * FROM certificado_temp;
                        DROP TABLE certificado_temp;
                        
                        CREATE UNIQUE INDEX unique_cnpj_per_user ON certificado (cnpj, user_id)
                    """
                    safe_execute_with_backup(connection, 'certificado', sql_commands)
                    print("Tabela de certificados atualizada com sucesso!")
            else:
                print("Criando tabela de certificados...")
                sql_commands = """
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
                    
                    CREATE UNIQUE INDEX unique_cnpj_per_user ON certificado (cnpj, user_id)
                """
                safe_execute_with_backup(connection, 'certificado', sql_commands)
            
            # Verificar e criar tabela de recuperação de senha se não existir
            if 'recuperacao_senha' not in metadata.tables:
                print("Criando tabela de recuperação de senha...")
                sql_commands = """
                    CREATE TABLE recuperacao_senha (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES "user" (id),
                        codigo VARCHAR(8) NOT NULL,
                        expiracao TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                        usado BOOLEAN DEFAULT FALSE
                    )
                """
                safe_execute_with_backup(connection, 'recuperacao_senha', sql_commands)
        
        print("Inicialização do banco de dados concluída com sucesso!")
        
    except Exception as e:
        print(f"Erro durante a inicialização do banco de dados: {str(e)}")
        print("ATENÇÃO: Em caso de erro, os backups podem ser encontrados nos arquivos backup_*.json")
        raise

END

echo "Build completed successfully!" 