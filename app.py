from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, abort, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import UniqueConstraint
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

# Database configuration
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # Render.com usa 'postgres://', mas SQLAlchemy requer 'postgresql://'
    database_url = database_url.replace('postgres://', 'postgresql://')
else:
    # Fallback para SQLite em desenvolvimento local
    database_url = 'sqlite:///certificados.db'

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'info'

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    certificados = db.relationship('Certificado', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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
    cnpj = db.Column(db.String(30), nullable=False)
    telefone = db.Column(db.String(30), nullable=False)
    data_emissao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_validade = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    observacoes = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Adiciona restrição única para CNPJ por usuário
    __table_args__ = (UniqueConstraint('cnpj', 'user_id', name='unique_cnpj_per_user'),)

    def atualizar_status(self):
        """Atualiza o status do certificado com base na data de validade"""
        self.status = determinar_status(self.data_validade)

# Initialize database
with app.app_context():
    try:
        logger.info('Starting database initialization...')
        
        # Drop all existing tables
        logger.info('Dropping all existing tables...')
        db.drop_all()
        
        # Create all tables with new structure
        logger.info('Creating tables with new structure...')
        db.create_all()
        
        # Create default admin user if it doesn't exist
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@example.com',
                name='Administrador'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            logger.info('Default admin user created')
        
        logger.info('Database initialization completed successfully')
    except Exception as e:
        logger.error(f'Error in database initialization: {str(e)}')
        raise

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            flash('Login realizado com sucesso!', 'success')
            return redirect(next_page or url_for('index'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        name = request.form['name']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Este nome de usuário já está em uso.', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Este e-mail já está em uso.', 'danger')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email, name=name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registro realizado com sucesso! Faça login para continuar.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Protected routes
@app.route('/')
@login_required
def index():
    try:
        logger.info('Accessing index page')
        return render_template('index.html')
    except Exception as e:
        logger.error(f'Error in index route: {str(e)}')
        return render_template('500.html'), 500

@app.route('/certificados', methods=['GET'])
@login_required
def listar_certificados():
    try:
        logger.info('Listing certificates')
        certificados = Certificado.query.filter_by(user_id=current_user.id).all()
        # Atualiza o status de todos os certificados antes de exibir
        for certificado in certificados:
            certificado.atualizar_status()
        db.session.commit()
        return render_template('certificados.html', certificados=certificados)
    except Exception as e:
        logger.error(f'Error in listar_certificados route: {str(e)}')
        return render_template('500.html'), 500

@app.route('/certificados/novo', methods=['GET', 'POST'])
@login_required
def novo_certificado():
    try:
        if request.method == 'POST':
            logger.info('Creating new certificate')
            try:
                # Log dos dados recebidos
                logger.info('Form data received:')
                for key, value in request.form.items():
                    logger.info(f'{key}: {value}')

                # Captura todos os campos do formulário
                razao_social = request.form.get('razao_social')
                nome_fantasia = request.form.get('nome_fantasia')
                cnpj = request.form.get('cnpj')
                telefone = request.form.get('telefone')
                data_validade_str = request.form.get('data_validade')
                observacoes = request.form.get('observacoes', '')  # Campo opcional

                logger.info('Validating required fields...')
                # Validação dos campos obrigatórios
                campos_obrigatorios = {
                    'Razão Social': razao_social,
                    'Nome Fantasia': nome_fantasia,
                    'CNPJ': cnpj,
                    'Telefone': telefone,
                    'Data de Validade': data_validade_str
                }

                campos_vazios = [campo for campo, valor in campos_obrigatorios.items() if not valor]
                if campos_vazios:
                    mensagem = f'Os seguintes campos são obrigatórios: {", ".join(campos_vazios)}'
                    logger.warning(f'Validation failed: {mensagem}')
                    flash(mensagem, 'danger')
                    return render_template('novo_certificado.html')

                logger.info('Converting date...')
                # Conversão da data
                try:
                    data_validade = datetime.strptime(data_validade_str, '%Y-%m-%d')
                except ValueError as e:
                    logger.error(f'Date conversion error: {str(e)}')
                    flash('Data de validade inválida. Use o formato YYYY-MM-DD.', 'danger')
                    return render_template('novo_certificado.html')

                logger.info('Checking for existing CNPJ...')
                # Verifica se já existe um certificado com este CNPJ para este usuário
                certificado_existente = Certificado.query.filter_by(
                    user_id=current_user.id,
                    cnpj=cnpj
                ).first()

                if certificado_existente:
                    logger.warning(f'Duplicate CNPJ found: {cnpj}')
                    flash('Já existe um certificado cadastrado com este CNPJ.', 'danger')
                    return render_template('novo_certificado.html')

                logger.info('Creating certificate object...')
                # Cria o certificado com status automático
                certificado = Certificado(
                    razao_social=razao_social,
                    nome_fantasia=nome_fantasia,
                    cnpj=cnpj,
                    telefone=telefone,
                    data_validade=data_validade,
                    observacoes=observacoes,
                    user_id=current_user.id
                )
                
                # Define o status automaticamente
                certificado.atualizar_status()
                logger.info(f'Certificate status set to: {certificado.status}')

                logger.info('Saving to database...')
                db.session.add(certificado)
                db.session.commit()
                logger.info(f'Certificate created successfully: {razao_social}')

                flash('Certificado criado com sucesso!', 'success')
                return redirect(url_for('listar_certificados'))

            except Exception as e:
                logger.error(f'Detailed error in form processing: {str(e)}', exc_info=True)
                db.session.rollback()
                flash(f'Erro ao processar os dados do formulário: {str(e)}', 'danger')
                return render_template('novo_certificado.html')

        return render_template('novo_certificado.html')
    except Exception as e:
        logger.error(f'General error in novo_certificado route: {str(e)}', exc_info=True)
        db.session.rollback()
        flash('Ocorreu um erro ao processar sua solicitação. Por favor, tente novamente.', 'danger')
        return render_template('novo_certificado.html')

@app.route('/certificados/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_certificado(id):
    try:
        certificado = Certificado.query.get_or_404(id)
        if certificado.user_id != current_user.id:
            abort(403)
        
        if request.method == 'POST':
            logger.info(f'Updating certificate {id}')
            try:
                # Captura todos os campos do formulário
                razao_social = request.form.get('razao_social')
                nome_fantasia = request.form.get('nome_fantasia')
                novo_cnpj = request.form.get('cnpj')
                telefone = request.form.get('telefone')
                data_validade_str = request.form.get('data_validade')
                observacoes = request.form.get('observacoes')

                # Validação dos campos obrigatórios
                if not all([razao_social, nome_fantasia, novo_cnpj, telefone, data_validade_str]):
                    flash('Todos os campos obrigatórios devem ser preenchidos.', 'danger')
                    return render_template('editar_certificado.html', certificado=certificado)

                # Conversão da data
                try:
                    data_validade = datetime.strptime(data_validade_str, '%Y-%m-%d')
                except ValueError:
                    flash('Data de validade inválida.', 'danger')
                    return render_template('editar_certificado.html', certificado=certificado)

                # Verifica se o novo CNPJ já existe para outro certificado do mesmo usuário
                if novo_cnpj != certificado.cnpj:
                    certificado_existente = Certificado.query.filter_by(
                        user_id=current_user.id,
                        cnpj=novo_cnpj
                    ).first()

                    if certificado_existente:
                        flash('Já existe um certificado cadastrado com este CNPJ.', 'danger')
                        return render_template('editar_certificado.html', certificado=certificado)

                # Atualiza os dados do certificado
                certificado.razao_social = razao_social
                certificado.nome_fantasia = nome_fantasia
                certificado.cnpj = novo_cnpj
                certificado.telefone = telefone
                certificado.data_validade = data_validade
                certificado.observacoes = observacoes
                
                # Atualiza o status automaticamente
                certificado.atualizar_status()
                
                db.session.commit()
                logger.info(f'Certificate updated successfully: {certificado.razao_social}')
                
                flash('Certificado atualizado com sucesso!', 'success')
                return redirect(url_for('listar_certificados'))

            except Exception as e:
                logger.error(f'Error processing form data: {str(e)}')
                db.session.rollback()
                flash('Erro ao processar os dados do formulário. Por favor, verifique os campos e tente novamente.', 'danger')
                return render_template('editar_certificado.html', certificado=certificado)
        
        return render_template('editar_certificado.html', certificado=certificado)
    except Exception as e:
        logger.error(f'Error in editar_certificado route: {str(e)}')
        db.session.rollback()
        flash('Ocorreu um erro ao processar sua solicitação. Por favor, tente novamente.', 'danger')
        return render_template('editar_certificado.html', certificado=certificado)

@app.route('/certificados/<int:id>/deletar', methods=['POST'])
@login_required
def deletar_certificado(id):
    try:
        certificado = Certificado.query.get_or_404(id)
        if certificado.user_id != current_user.id:
            abort(403)
            
        razao_social = certificado.razao_social
        
        db.session.delete(certificado)
        db.session.commit()
        
        logger.info(f'Certificate deleted successfully: {razao_social}')
        flash('Certificado excluído com sucesso!', 'success')
        
        return redirect(url_for('listar_certificados'))
    except Exception as e:
        logger.error(f'Error in deletar_certificado route: {str(e)}')
        db.session.rollback()
        flash('Erro ao excluir certificado.', 'danger')
        return redirect(url_for('listar_certificados'))

@app.route('/certificados/exportar')
@login_required
def exportar_certificados():
    try:
        logger.info('Exporting certificates to Excel')
        certificados = Certificado.query.filter_by(user_id=current_user.id).all()
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