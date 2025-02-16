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
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuração de logging mais detalhada
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
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
    try:
        hoje = datetime.now()
        if not isinstance(data_validade, datetime):
            logger.error(f'data_validade inválida: {data_validade} (tipo: {type(data_validade)})')
            return 'Erro'
            
        dias_para_vencer = (data_validade - hoje).days
        
        if dias_para_vencer < 0:
            return 'Expirado'
        elif dias_para_vencer <= 30:
            return 'Próximo ao Vencimento'
        else:
            return 'Válido'
    except Exception as e:
        logger.error(f'Erro ao determinar status: {str(e)}')
        return 'Erro'

# Define models
class Certificado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(200), nullable=False)
    nome_fantasia = db.Column(db.String(200), nullable=False)
    cnpj = db.Column(db.String(30), nullable=False)
    telefone = db.Column(db.String(30), nullable=False)
    data_emissao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_validade = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(30), nullable=False)
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
        
        # Create tables if they don't exist
        db.create_all()
        
        # Create default admin user if it doesn't exist
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin = User(
                username='admin',
                email='admin@certificados.com',
                name='Administrador'
            )
            # Senha fixa: Admin@123
            admin.set_password('Admin@123')
            db.session.add(admin)
            db.session.commit()
            logger.info('Default admin user created')
        else:
            # Atualiza a senha do admin existente
            admin_user.set_password('Admin@123')
            db.session.commit()
            logger.info('Admin password updated')
        
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
        logger.info('Iniciando listagem de certificados')
        logger.info(f'Usuário: {current_user.username} (ID: {current_user.id})')
        
        # Obter parâmetros de busca e filtro
        search_query = request.args.get('search', '').strip()
        data_inicial = request.args.get('data_inicial', '')
        data_final = request.args.get('data_final', '')
        
        logger.debug(f'Parâmetros de busca: search={search_query}, data_inicial={data_inicial}, data_final={data_final}')
        
        try:
            # Iniciar a query base
            query = Certificado.query.filter_by(user_id=current_user.id)
            logger.debug('Query base criada com sucesso')
            
            # Aplicar busca se houver termo de pesquisa
            if search_query:
                search_term = f"%{search_query}%"
                query = query.filter(
                    db.or_(
                        Certificado.nome_fantasia.ilike(search_term),
                        Certificado.razao_social.ilike(search_term),
                        Certificado.cnpj.ilike(search_term)
                    )
                )
                logger.debug(f'Filtro de busca aplicado: {search_query}')
            
            # Aplicar filtro de data se as datas forem fornecidas
            if data_inicial:
                try:
                    data_inicial = datetime.strptime(data_inicial, '%Y-%m-%d')
                    query = query.filter(Certificado.data_validade >= data_inicial)
                    logger.debug(f'Filtro de data inicial aplicado: {data_inicial}')
                except ValueError as e:
                    logger.warning(f'Data inicial inválida: {e}')
                    flash('Data inicial inválida', 'warning')
            
            if data_final:
                try:
                    data_final = datetime.strptime(data_final, '%Y-%m-%d')
                    # Adiciona 1 dia à data final para incluir todo o último dia
                    data_final = data_final + timedelta(days=1)
                    query = query.filter(Certificado.data_validade < data_final)
                    logger.debug(f'Filtro de data final aplicado: {data_final}')
                except ValueError as e:
                    logger.warning(f'Data final inválida: {e}')
                    flash('Data final inválida', 'warning')
            
            # Executar a query
            logger.debug('Executando query final')
            certificados = query.all()
            logger.info(f'Total de certificados encontrados: {len(certificados)}')
            
            # Atualizar status dos certificados
            logger.debug('Iniciando atualização de status dos certificados')
            for certificado in certificados:
                try:
                    certificado.atualizar_status()
                except Exception as e:
                    logger.error(f'Erro ao atualizar status do certificado {certificado.id}: {str(e)}')
                    continue
            
            try:
                db.session.commit()
                logger.debug('Status dos certificados atualizados com sucesso')
            except Exception as e:
                logger.error(f'Erro ao salvar atualizações de status: {str(e)}')
                db.session.rollback()
                flash('Erro ao atualizar status dos certificados', 'warning')
            
            return render_template('certificados.html', 
                                certificados=certificados,
                                search_query=search_query,
                                data_inicial=request.args.get('data_inicial', ''),
                                data_final=request.args.get('data_final', ''))
                                
        except Exception as e:
            logger.error(f'Erro ao processar query do banco de dados: {str(e)}', exc_info=True)
            db.session.rollback()
            flash('Erro ao buscar certificados no banco de dados', 'danger')
            return render_template('certificados.html', 
                                certificados=[],
                                search_query=search_query,
                                data_inicial=data_inicial,
                                data_final=data_final)
            
    except Exception as e:
        logger.error(f'Erro crítico em listar_certificados: {str(e)}', exc_info=True)
        db.session.rollback()
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

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        logger.info('Accessing dashboard page')
        
        # Buscar certificados do usuário
        certificados = Certificado.query.filter_by(user_id=current_user.id).all()
        
        # Atualizar status de todos os certificados
        for certificado in certificados:
            certificado.atualizar_status()
        
        # Dados para o gráfico de pizza (Status dos Certificados)
        status_counts = {
            'Válido': 0,
            'Próximo ao Vencimento': 0,
            'Expirado': 0
        }
        for certificado in certificados:
            status_counts[certificado.status] += 1
        
        # Dados para o gráfico de barras (Certificados por Mês)
        from collections import defaultdict
        import calendar
        
        certificados_por_mes = defaultdict(int)
        for certificado in certificados:
            mes = certificado.data_validade.strftime('%B')  # Nome do mês
            certificados_por_mes[mes] += 1
        
        # Ordenar os meses cronologicamente
        meses_ordenados = sorted(certificados_por_mes.items(), 
                               key=lambda x: list(calendar.month_name).index(x[0]))
        
        # Preparar dados para os gráficos
        chart_data = {
            'status_labels': list(status_counts.keys()),
            'status_data': list(status_counts.values()),
            'meses_labels': [item[0] for item in meses_ordenados],
            'meses_data': [item[1] for item in meses_ordenados]
        }
        
        # Estatísticas adicionais
        stats = {
            'total_certificados': len(certificados),
            'proximos_vencer': sum(1 for c in certificados if c.status == 'Próximo ao Vencimento'),
            'expirados': sum(1 for c in certificados if c.status == 'Expirado'),
            'validos': sum(1 for c in certificados if c.status == 'Válido')
        }
        
        return render_template('dashboard.html', chart_data=chart_data, stats=stats)
    except Exception as e:
        logger.error(f'Error in dashboard route: {str(e)}')
        return render_template('500.html'), 500

# Função para enviar email
def enviar_email(destinatario, assunto, corpo):
    try:
        # Configurações do email (você precisará definir estas variáveis de ambiente no Render.com)
        EMAIL_SENDER = os.environ.get('EMAIL_SENDER', 'seu-email@gmail.com')
        EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', 'sua-senha-app')
        
        # Criar mensagem
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = destinatario
        msg['Subject'] = assunto
        
        # Adicionar corpo
        msg.attach(MIMEText(corpo, 'html'))
        
        # Conectar ao servidor SMTP do Gmail
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        
        # Enviar email
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        logger.error(f'Erro ao enviar email: {str(e)}')
        return False

# Modelo para códigos de recuperação de senha
class RecuperacaoSenha(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    codigo = db.Column(db.String(8), nullable=False)
    expiracao = db.Column(db.DateTime, nullable=False)
    usado = db.Column(db.Boolean, default=False)

# Rotas de Administração
@app.route('/admin')
@login_required
def admin():
    try:
        # Apenas admin pode acessar
        if current_user.username != 'admin':
            abort(403)
        
        users = User.query.all()
        return render_template('admin.html', users=users)
    except Exception as e:
        logger.error(f'Error in admin route: {str(e)}')
        return render_template('500.html'), 500

@app.route('/admin/alterar_senha/<int:user_id>', methods=['POST'])
@login_required
def admin_alterar_senha(user_id):
    try:
        # Apenas admin pode alterar
        if current_user.username != 'admin':
            abort(403)
        
        user = User.query.get_or_404(user_id)
        nova_senha = request.form.get('nova_senha')
        
        if not nova_senha:
            flash('A nova senha é obrigatória.', 'danger')
        else:
            user.set_password(nova_senha)
            db.session.commit()
            flash(f'Senha do usuário {user.username} alterada com sucesso!', 'success')
        
        return redirect(url_for('admin'))
    except Exception as e:
        logger.error(f'Error in admin_alterar_senha route: {str(e)}')
        db.session.rollback()
        flash('Erro ao alterar senha.', 'danger')
        return redirect(url_for('admin'))

# Rotas de Recuperação de Senha
@app.route('/recuperar_senha', methods=['GET', 'POST'])
def recuperar_senha():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Gerar código de verificação
            codigo = secrets.token_hex(4).upper()
            expiracao = datetime.utcnow() + timedelta(hours=1)
            
            # Salvar código no banco
            recuperacao = RecuperacaoSenha(
                user_id=user.id,
                codigo=codigo,
                expiracao=expiracao
            )
            db.session.add(recuperacao)
            db.session.commit()
            
            # Enviar email
            assunto = 'Recuperação de Senha - Gerenciador de Certificados'
            corpo = f"""
            <h2>Recuperação de Senha</h2>
            <p>Olá {user.name},</p>
            <p>Seu código de verificação é: <strong>{codigo}</strong></p>
            <p>Este código expira em 1 hora.</p>
            <p>Se você não solicitou a recuperação de senha, ignore este email.</p>
            """
            
            if enviar_email(user.email, assunto, corpo):
                flash('Código de verificação enviado para seu email!', 'success')
                return redirect(url_for('verificar_codigo', user_id=user.id))
            else:
                flash('Erro ao enviar email. Tente novamente.', 'danger')
        else:
            flash('Email não encontrado.', 'danger')
    
    return render_template('recuperar_senha.html')

@app.route('/verificar_codigo/<int:user_id>', methods=['GET', 'POST'])
def verificar_codigo(user_id):
    if request.method == 'POST':
        codigo = request.form.get('codigo')
        recuperacao = RecuperacaoSenha.query.filter_by(
            user_id=user_id,
            codigo=codigo,
            usado=False
        ).order_by(RecuperacaoSenha.expiracao.desc()).first()
        
        if recuperacao and recuperacao.expiracao > datetime.utcnow():
            recuperacao.usado = True
            db.session.commit()
            session['reset_user_id'] = user_id  # Armazenar ID do usuário para próxima etapa
            return redirect(url_for('nova_senha'))
        else:
            flash('Código inválido ou expirado.', 'danger')
    
    return render_template('verificar_codigo.html')

@app.route('/nova_senha', methods=['GET', 'POST'])
def nova_senha():
    user_id = session.get('reset_user_id')
    if not user_id:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        senha = request.form.get('senha')
        confirmar_senha = request.form.get('confirmar_senha')
        
        if senha != confirmar_senha:
            flash('As senhas não coincidem.', 'danger')
        else:
            user = User.query.get(user_id)
            if user:
                user.set_password(senha)
                db.session.commit()
                session.pop('reset_user_id', None)  # Limpar sessão
                flash('Senha alterada com sucesso! Faça login com sua nova senha.', 'success')
                return redirect(url_for('login'))
    
    return render_template('nova_senha.html')

# Manipulador de erros global
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Erro não tratado: {str(e)}", exc_info=True)
    return render_template('500.html'), 500

@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"Página não encontrada: {request.url}")
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error("Erro interno do servidor", exc_info=True)
    return render_template('500.html'), 500

# Middleware para logging de requisições
@app.before_request
def log_request_info():
    logger.debug('Headers: %s', request.headers)
    logger.debug('Body: %s', request.get_data())

@app.after_request
def log_response_info(response):
    logger.debug('Response Status: %s', response.status)
    return response

if __name__ == '__main__':
    app.run(debug=True) 