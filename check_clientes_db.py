import sqlite3
import os
from datetime import datetime

def check_clientes_db():
    try:
        # Conectar ao banco de dados
        conn = sqlite3.connect('clientes.db')
        cursor = conn.cursor()
        
        # Listar todas as tabelas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print("\n=== Tabelas encontradas no banco de dados ===")
        for table in tables:
            table_name = table[0]
            print(f"\nTabela: {table_name}")
            
            # Obter estrutura da tabela
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            print("\nColunas:")
            for col in columns:
                print(f"- {col[1]} ({col[2]})")
            
            # Contar registros
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"\nTotal de registros: {count}")
            
            # Mostrar alguns registros de exemplo
            if count > 0:
                print("\nPrimeiros 5 registros:")
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
                rows = cursor.fetchall()
                for row in rows:
                    print(row)
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"\nErro ao verificar o banco de dados: {str(e)}")
        return False

if __name__ == '__main__':
    print("Verificando conteúdo do banco de dados clientes.db...")
    if not check_clientes_db():
        print("Não foi possível verificar o banco de dados.") 