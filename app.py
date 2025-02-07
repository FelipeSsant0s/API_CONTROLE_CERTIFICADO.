import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import io

app = Flask(__name__)

# Configurações do ambiente
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sua_chave_secreta_aqui')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///certificados.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Ajuste para URL do PostgreSQL no Render
if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)

# Configuração do banco de dados
db = SQLAlchemy(app)

# Configuração do login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# [Mantenha o resto do seu código...]

@app.route('/exportar-excel')
@login_required
def exportar_excel():
    try:
        from excel_utils import gerar_excel
        
        hoje = datetime.now().date()
        clientes = Cliente.query.filter_by(user_id=current_user.id).all()
        
        # Ordenar clientes
        def ordem_status(cliente):
            dias_restantes = (cliente.data_vencimento - hoje).days
            if dias_restantes < 0:
                return 0  # VENCIDO
            elif dias_restantes <= 30:
                return 1  # PRÓXIMO AO VENCIMENTO
            else:
                return 2  # REGULAR
        
        clientes_ordenados = sorted(clientes, key=lambda x: (ordem_status(x), x.data_vencimento))
        
        # Gerar arquivo Excel
        excel_file = gerar_excel(clientes_ordenados, status_vencimento)
        
        return send_file(
            excel_file,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'clientes_{datetime.now().strftime("%d%m%Y")}.xlsx'
        )
        
    except ImportError:
        flash('Erro ao exportar: biblioteca Excel não disponível')
        return redirect(url_for('lista_clientes'))
    except Exception as e:
        flash(f'Erro ao exportar: {str(e)}')
        return redirect(url_for('lista_clientes'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Configuração da porta para desenvolvimento local
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False) 