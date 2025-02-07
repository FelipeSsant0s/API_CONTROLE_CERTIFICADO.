import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

def test_database_connection():
    """Test database connection and permissions"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL não está definida!")
        return False
    
    # Ajustar URL para formato SQLAlchemy
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    print("\n=== Teste de Conexão com Banco de Dados ===")
    print(f"Tentando conectar ao banco de dados...")
    
    try:
        # Criar engine
        engine = create_engine(database_url)
        
        # Testar conexão básica
        with engine.connect() as connection:
            print("\n1. Teste de Conexão Básica: ✓ Sucesso")
            
            # Testar permissões de leitura
            try:
                connection.execute(text("SELECT current_database()")).scalar()
                print("2. Permissão de Leitura: ✓ Sucesso")
            except ProgrammingError:
                print("2. Permissão de Leitura: ✗ Falha - Sem permissão para SELECT")
            
            # Testar permissões de escrita
            try:
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS test_permissions (
                        id SERIAL PRIMARY KEY,
                        test_column VARCHAR(50)
                    )
                """))
                print("3. Permissão de Criação de Tabela: ✓ Sucesso")
                
                # Limpar tabela de teste
                connection.execute(text("DROP TABLE test_permissions"))
                print("4. Permissão de Remoção de Tabela: ✓ Sucesso")
            except ProgrammingError as e:
                print(f"3/4. Permissão de Escrita: ✗ Falha - {str(e)}")
            
            # Testar informações do banco
            try:
                db_name = connection.execute(text("SELECT current_database()")).scalar()
                user = connection.execute(text("SELECT current_user")).scalar()
                print(f"\nInformações Adicionais:")
                print(f"- Banco de Dados: {db_name}")
                print(f"- Usuário: {user}")
            except ProgrammingError:
                print("Não foi possível obter informações adicionais")
        
        return True
        
    except OperationalError as e:
        print("\n❌ ERRO DE CONEXÃO:")
        print(str(e))
        print("\nPossíveis problemas:")
        print("1. Credenciais incorretas")
        print("2. IP não autorizado")
        print("3. Banco de dados não está aceitando conexões")
        print("4. Firewall bloqueando a conexão")
        return False
    except Exception as e:
        print(f"\n❌ ERRO INESPERADO: {str(e)}")
        return False

if __name__ == '__main__':
    print("Iniciando teste de conexão com o banco de dados...")
    success = test_database_connection()
    if not success:
        sys.exit(1) 