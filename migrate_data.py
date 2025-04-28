import sqlite3
from datetime import datetime, timedelta
from app import app, db, User, Certificado

def migrate_data():
    try:
        with app.app_context():
            # Conectar ao banco antigo
            old_conn = sqlite3.connect('clientes.db')
            old_cursor = old_conn.cursor()

            # Obter todos os clientes
            old_cursor.execute("SELECT * FROM clientes")
            clientes = old_cursor.fetchall()

            print(f"\nEncontrados {len(clientes)} clientes para migrar")

            # Criar usuário admin se não existir
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                admin = User(
                    username='admin',
                    email='admin@certificados.com',
                    name='Administrador'
                )
                admin.set_password('Admin@123')
                db.session.add(admin)
                db.session.commit()
                print("Usuário admin criado")

            # Migrar cada cliente
            for cliente in clientes:
                try:
                    # Converter a data de vencimento
                    data_validade = datetime.strptime(cliente[5], '%Y-%m-%d')
                    
                    # Criar novo certificado
                    certificado = Certificado(
                        razao_social=cliente[1],  # razao_social
                        nome_fantasia=cliente[1],  # usando razao_social como nome_fantasia
                        cnpj=cliente[2],  # cnpj
                        telefone=cliente[4],  # telefone
                        data_emissao=datetime.now(),  # data atual
                        data_validade=data_validade,  # data de vencimento do banco antigo
                        status='Válido',  # status padrão
                        observacoes=f'Migrado do sistema antigo. Proprietário: {cliente[3]}',  # incluindo proprietário nas observações
                        user_id=admin.id  # associando ao admin
                    )
                    db.session.add(certificado)
                    print(f"Migrando cliente: {cliente[1]} (CNPJ: {cliente[2]})")
                except Exception as e:
                    print(f"Erro ao migrar cliente {cliente[1]}: {str(e)}")
                    continue

            # Commit das alterações
            try:
                db.session.commit()
                print("\nMigração concluída com sucesso!")
            except Exception as e:
                db.session.rollback()
                print(f"\nErro ao salvar os dados: {str(e)}")

            # Fechar conexão com o banco antigo
            old_conn.close()

    except Exception as e:
        print(f"\nErro durante a migração: {str(e)}")
        return False

if __name__ == '__main__':
    print("Iniciando migração de dados...")
    migrate_data() 