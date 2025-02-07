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
import os

# Criar diretório para backups se não existir
BACKUP_DIR = 'db_backups'
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

def table_exists(connection, table_name):
    """Verifica se uma tabela existe no banco de dados"""
    try:
        result = connection.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :table)"
        ), {"table": table_name})
        return result.scalar()
    except Exception:
        return False

def backup_table_data(connection, table_name):
    """Faz backup dos dados de uma tabela em formato JSON"""
    try:
        # Verificar se a tabela existe antes de tentar fazer backup
        if not table_exists(connection, table_name):
            print(f"Tabela {table_name} ainda não existe. Backup não é necessário.")
            return True
            
        result = connection.execute(text(f'SELECT * FROM "{table_name}"'))
        data = [dict(row) for row in result]
        
        # Se não há dados, não precisa criar arquivo de backup
        if not data:
            print(f"Tabela {table_name} está vazia. Backup não é necessário.")
            return True
        
        # Converter timestamps para string
        for row in data:
            for key, value in row.items():
                if isinstance(value, datetime):
                    row[key] = value.isoformat()
        
        backup_file = os.path.join(BACKUP_DIR, f'backup_{table_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Backup da tabela {table_name} criado com sucesso: {backup_file}")
        return True
    except Exception as e:
        print(f"Erro ao fazer backup da tabela {table_name}: {str(e)}")
        return False

def execute_sql_commands(connection, commands):
    """Executa uma lista de comandos SQL"""
    for command in commands.split(';'):
        if command.strip():
            try:
                connection.execute(text(command.strip()))
            except Exception as e:
                print(f"Erro ao executar comando SQL: {command.strip()}")
                raise

def safe_execute_with_backup(connection, table_name, sql_commands, is_new_table=False):
    """Executa comandos SQL com backup de segurança e rollback em caso de erro"""
    try:
        # Verificar se é uma criação de nova tabela
        if is_new_table:
            print(f"Criando nova tabela {table_name}, backup não é necessário.")
            execute_sql_commands(connection, sql_commands)
            print(f"Tabela {table_name} criada com sucesso!")
            return True
        
        # Para atualizações de tabelas existentes
        if table_name in ['user', 'certificado']:
            if not backup_table_data(connection, table_name):
                print(f"Aviso: Não foi possível fazer backup da tabela {table_name}, mas continuando com a operação...")
        
        try:
            # Executar os comandos SQL
            execute_sql_commands(connection, sql_commands)
            print(f"Comandos SQL executados com sucesso para a tabela {table_name}")
        except Exception as e:
            print(f"Erro durante a execução dos comandos SQL para {table_name}: {str(e)}")
            raise
        
        return True
    except Exception as e:
        print(f"Erro durante o processo de atualização da tabela {table_name}: {str(e)}")
        if os.path.exists(BACKUP_DIR) and os.listdir(BACKUP_DIR):
            print(f"Os backups podem ser encontrados no diretório: {BACKUP_DIR}")
        raise

with app.app_context():
    try:
        print("Iniciando processo de atualização do banco de dados...")
        print(f"Os backups serão salvos no diretório: {BACKUP_DIR}")
        
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
                        -- Criar backup das tabelas se existirem
                        CREATE TABLE IF NOT EXISTS user_backup AS SELECT * FROM "user";
                        CREATE TABLE IF NOT EXISTS certificado_backup AS 
                        SELECT * FROM certificado WHERE EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_name = 'certificado'
                        );
                        
                        -- Remover tabelas mantendo sequências
                        DROP TABLE IF EXISTS certificado CASCADE;
                        DROP TABLE IF EXISTS "user" CASCADE;
                        
                        -- Recriar tabela user mantendo a sequência do id
                        CREATE TABLE "user" (
                            id SERIAL PRIMARY KEY,
                            username VARCHAR(120) UNIQUE NOT NULL,
                            password_hash VARCHAR(200) NOT NULL,
                            email VARCHAR(120) UNIQUE NOT NULL,
                            name VARCHAR(120) NOT NULL
                        );
                        
                        -- Restaurar dados do user
                        INSERT INTO "user" SELECT * FROM user_backup;
                        
                        -- Recriar tabela certificado
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

                        -- Recriar o índice único
                        CREATE UNIQUE INDEX unique_cnpj_per_user ON certificado (cnpj, user_id);

                        -- Restaurar dados do certificado se existir backup
                        INSERT INTO certificado 
                        SELECT * FROM certificado_backup 
                        WHERE EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_name = 'certificado_backup'
                        );

                        -- Limpar backups
                        DROP TABLE IF EXISTS certificado_backup;
                        DROP TABLE IF EXISTS user_backup;
                    """
                    safe_execute_with_backup(connection, 'user', sql_commands)
                    print("Tabelas atualizadas com sucesso mantendo todos os dados!")
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
                safe_execute_with_backup(connection, 'user', sql_commands, is_new_table=True)
            
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
                safe_execute_with_backup(connection, 'certificado', sql_commands, is_new_table=True)
            
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
                safe_execute_with_backup(connection, 'recuperacao_senha', sql_commands, is_new_table=True)
        
        print("Inicialização do banco de dados concluída com sucesso!")
        
    except Exception as e:
        print(f"Erro durante a inicialização do banco de dados: {str(e)}")
        print(f"ATENÇÃO: Os backups podem ser encontrados no diretório: {BACKUP_DIR}")
        raise

END

echo "Build completed successfully!" 