from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import io
import openpyxl
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Create Flask application
app = Flask(__name__)
logger.info('Initializing Flask application...')

# Configure application
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///certificados.db').replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

logger.info(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

# Create SQLAlchemy instance
db = SQLAlchemy(app)

def determinar_status(data_validade):
    """Determina o status do certificado com base na data de validade"""
    hoje = datetime.now()
    dias_para_vencer = (data_validade - hoje).days
    
    if dias_para_vencer < 0:
        return 'Expirado'
    elif dias_para_vencer <= 30:
        return 'Próximo ao Vencimento'
    else:
        return 'Válido'

# Define models
class Certificado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(200), nullable=False)
    nome_fantasia = db.Column(db.String(200), nullable=False)
    cnpj = db.Column(db.String(18), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    data_emissao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_validade = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    observacoes = db.Column(db.Text)

    def atualizar_status(self):
        """Atualiza o status do certificado com base na data de validade"""
        self.status = determinar_status(self.data_validade)

# Initialize database
with app.app_context():
    try:
        logger.info('Creating database tables...')
        db.create_all()
        logger.info('Database tables created successfully')
    except Exception as e:
        logger.error(f'Error creating database tables: {str(e)}')
        raise

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    logger.error(f'Page not found: {request.url}')
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f'Server Error: {error}')
    db.session.rollback()
    return render_template('500.html'), 500

# Routes
@app.route('/')
def index():
    try:
        logger.info('Accessing index page')
        return render_template('index.html')
    except Exception as e:
        logger.error(f'Error in index route: {str(e)}')
        return render_template('500.html'), 500

@app.route('/certificados', methods=['GET'])
def listar_certificados():
    try:
        logger.info('Listing certificates')
        certificados = Certificado.query.all()
        # Atualiza o status de todos os certificados antes de exibir
        for certificado in certificados:
            certificado.atualizar_status()
        db.session.commit()
        return render_template('certificados.html', certificados=certificados)
    except Exception as e:
        logger.error(f'Error in listar_certificados route: {str(e)}')
        return render_template('500.html'), 500

@app.route('/certificados/novo', methods=['GET', 'POST'])
def novo_certificado():
    try:
        if request.method == 'POST':
            logger.info('Creating new certificate')
            razao_social = request.form['razao_social']
            nome_fantasia = request.form['nome_fantasia']
            cnpj = request.form['cnpj']
            telefone = request.form['telefone']
            data_validade = datetime.strptime(request.form['data_validade'], '%Y-%m-%d')
            observacoes = request.form['observacoes']

            # Cria o certificado com status automático
            certificado = Certificado(
                razao_social=razao_social,
                nome_fantasia=nome_fantasia,
                cnpj=cnpj,
                telefone=telefone,
                data_validade=data_validade,
                observacoes=observacoes
            )
            
            # Define o status automaticamente
            certificado.atualizar_status()

            db.session.add(certificado)
            db.session.commit()
            logger.info(f'Certificate created successfully: {razao_social}')

            flash('Certificado criado com sucesso!', 'success')
            return redirect(url_for('listar_certificados'))

        return render_template('novo_certificado.html')
    except Exception as e:
        logger.error(f'Error in novo_certificado route: {str(e)}')
        db.session.rollback()
        return render_template('500.html'), 500

@app.route('/certificados/exportar')
def exportar_certificados():
    try:
        logger.info('Exporting certificates to Excel')
        certificados = Certificado.query.all()
        # Atualiza o status antes de exportar
        for certificado in certificados:
            certificado.atualizar_status()
        db.session.commit()
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Certificados"
        
        # Headers
        headers = ['ID', 'Razão Social', 'Nome Fantasia', 'CNPJ', 'Telefone', 'Data Emissão', 'Data Validade', 'Status', 'Observações']
        for col, header in enumerate(headers, 1):
            ws.cell(row=1, column=col, value=header)
        
        # Data
        for row, cert in enumerate(certificados, 2):
            ws.cell(row=row, column=1, value=cert.id)
            ws.cell(row=row, column=2, value=cert.razao_social)
            ws.cell(row=row, column=3, value=cert.nome_fantasia)
            ws.cell(row=row, column=4, value=cert.cnpj)
            ws.cell(row=row, column=5, value=cert.telefone)
            ws.cell(row=row, column=6, value=cert.data_emissao.strftime('%d/%m/%Y'))
            ws.cell(row=row, column=7, value=cert.data_validade.strftime('%d/%m/%Y'))
            ws.cell(row=row, column=8, value=cert.status)
            ws.cell(row=row, column=9, value=cert.observacoes)
        
        # Save to bytes
        excel_file = io.BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)
        
        logger.info('Excel file generated successfully')
        return send_file(
            excel_file,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='certificados.xlsx'
        )
    except Exception as e:
        logger.error(f'Error in exportar_certificados route: {str(e)}')
        return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True) 