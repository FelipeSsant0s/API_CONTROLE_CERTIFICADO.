import os
import json
from datetime import datetime
import glob

def visualizar_ultimo_backup():
    """Visualiza as informações do último backup realizado"""
    
    BACKUP_DIR = 'db_backups'
    
    # Verifica se o diretório de backups existe
    if not os.path.exists(BACKUP_DIR):
        print("❌ Diretório de backups não encontrado!")
        return
    
    # Lista todos os arquivos de backup
    arquivos_backup = glob.glob(os.path.join(BACKUP_DIR, 'backup_*.json'))
    
    if not arquivos_backup:
        print("❌ Nenhum arquivo de backup encontrado!")
        return
    
    # Ordena os arquivos por data (mais recente primeiro)
    ultimo_backup = max(arquivos_backup, key=os.path.getctime)
    
    print("\n=== Informações do Último Backup ===")
    print(f"📁 Arquivo: {os.path.basename(ultimo_backup)}")
    print(f"📅 Data: {datetime.fromtimestamp(os.path.getctime(ultimo_backup)).strftime('%d/%m/%Y %H:%M:%S')}")
    
    try:
        with open(ultimo_backup, 'r', encoding='utf-8') as f:
            dados = json.load(f)
            
        if not dados:
            print("⚠️ Arquivo de backup está vazio!")
            return
            
        print(f"\n📊 Quantidade de registros: {len(dados)}")
        print("\n🔍 Exemplo de registro:")
        primeiro_registro = dados[0]
        for chave, valor in primeiro_registro.items():
            print(f"   {chave}: {valor}")
            
    except json.JSONDecodeError:
        print("❌ Erro ao ler o arquivo de backup: formato JSON inválido")
    except Exception as e:
        print(f"❌ Erro ao ler o arquivo de backup: {str(e)}")

if __name__ == '__main__':
    print("Iniciando visualização do último backup...")
    visualizar_ultimo_backup() 