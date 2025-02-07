from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import io
import openpyxl
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask application
app = Flask(__name__)

# Configure application
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///certificados.db').replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Create SQLAlchemy instance
db = SQLAlchemy(app)

# Define models
class Certificado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    data_emissao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_validade = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    observacoes = db.Column(db.Text)

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
        return render_template('index.html')
    except Exception as e:
        logger.error(f'Error in index route: {str(e)}')
        return render_template('500.html'), 500

@app.route('/certificados', methods=['GET'])
def listar_certificados():
    try:
        certificados = Certificado.query.all()
        return render_template('certificados.html', certificados=certificados)
    except Exception as e:
        logger.error(f'Error in listar_certificados route: {str(e)}')
        return render_template('500.html'), 500

@app.route('/certificados/novo', methods=['GET', 'POST'])
def novo_certificado():
    try:
        if request.method == 'POST':
            nome = request.form['nome']
            data_emissao = datetime.strptime(request.form['data_emissao'], '%Y-%m-%d')
            data_validade = datetime.strptime(request.form['data_validade'], '%Y-%m-%d')
            status = request.form['status']
            observacoes = request.form['observacoes']

            certificado = Certificado(
                nome=nome,
                data_emissao=data_emissao,
                data_validade=data_validade,
                status=status,
                observacoes=observacoes
            )

            db.session.add(certificado)
            db.session.commit()

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
        certificados = Certificado.query.all()
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Certificados"
        
        # Headers
        headers = ['ID', 'Nome', 'Data Emissão', 'Data Validade', 'Status', 'Observações']
        for col, header in enumerate(headers, 1):
            ws.cell(row=1, column=col, value=header)
        
        # Data
        for row, cert in enumerate(certificados, 2):
            ws.cell(row=row, column=1, value=cert.id)
            ws.cell(row=row, column=2, value=cert.nome)
            ws.cell(row=row, column=3, value=cert.data_emissao.strftime('%d/%m/%Y'))
            ws.cell(row=row, column=4, value=cert.data_validade.strftime('%d/%m/%Y'))
            ws.cell(row=row, column=5, value=cert.status)
            ws.cell(row=row, column=6, value=cert.observacoes)
        
        # Save to bytes
        excel_file = io.BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)
        
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
    with app.app_context():
        db.create_all()
    app.run(debug=True) 