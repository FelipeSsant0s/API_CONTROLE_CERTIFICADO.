import os
import sys
import subprocess

def build_exe():
    # Nome do arquivo executável
    exe_name = "Gerenciador de Certificados"
    
    # Comando para criar o executável
    cmd = [
        'pyinstaller',
        '--name', exe_name,
        '--onefile',
        '--windowed',
        '--icon=icon.ico' if os.path.exists('icon.ico') else None,
        '--add-data', 'README.md;.',
        'app.py'
    ]
    
    # Remove None values from cmd list
    cmd = [x for x in cmd if x is not None]
    
    try:
        subprocess.run(cmd, check=True)
        print("\nExecutável criado com sucesso!")
        print(f"Você pode encontrar o executável em: dist/{exe_name}.exe")
    except subprocess.CalledProcessError as e:
        print(f"Erro ao criar o executável: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_exe() 