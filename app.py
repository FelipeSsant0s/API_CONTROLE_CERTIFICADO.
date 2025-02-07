from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import openpyxl
from openpyxl.styles import Font, PatternFill
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui'  # Altere isso em produção
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///certificados.db'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Modelos
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(100), nullable=False)
    cnpj = db.Column(db.String(18), nullable=False)
    proprietario = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(15), nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def formatar_cnpj(cnpj):
    cnpj = ''.join(filter(str.isdigit, cnpj))
    if len(cnpj) != 14:
        return cnpj
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

def formatar_telefone(telefone):
    telefone = ''.join(filter(str.isdigit, telefone))
    if len(telefone) == 11:
        return f"({telefone[:2]}) {telefone[2:7]}-{telefone[7:]}"
    elif len(telefone) == 10:
        return f"({telefone[:2]}) {telefone[2:6]}-{telefone[6:]}"
    return telefone

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        
        flash('Usuário ou senha inválidos')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Nome de usuário já existe')
            return redirect(url_for('register'))
        
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registro realizado com sucesso!')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/lista-clientes')
@login_required
def lista_clientes():
    hoje = datetime.now().date()
    clientes = Cliente.query.filter_by(user_id=current_user.id).all()
    
    # Função para definir a ordem dos status
    def ordem_status(cliente):
        dias_restantes = (cliente.data_vencimento - hoje).days
        if dias_restantes < 0:
            return 0  # VENCIDO
        elif dias_restantes <= 30:
            return 1  # PRÓXIMO AO VENCIMENTO
        else:
            return 2  # REGULAR
    
    # Ordenar clientes por status e data de vencimento
    clientes_ordenados = sorted(clientes, key=lambda x: (ordem_status(x), x.data_vencimento))
    
    return render_template('lista_clientes.html', clientes=clientes_ordenados)

@app.route('/cliente/novo', methods=['POST'])
@login_required
def novo_cliente():
    try:
        data = request.form
        data_vencimento = datetime.strptime(data['data_vencimento'], '%Y-%m-%d').date()
        
        cliente = Cliente(
            razao_social=data['razao_social'],
            cnpj=formatar_cnpj(data['cnpj']),
            proprietario=data['proprietario'],
            telefone=formatar_telefone(data['telefone']),
            data_vencimento=data_vencimento,
            user_id=current_user.id
        )
        
        db.session.add(cliente)
        db.session.commit()
        flash('Cliente cadastrado com sucesso!')
        
    except Exception as e:
        flash(f'Erro ao cadastrar cliente: {str(e)}')
    
    return redirect(url_for('dashboard'))

@app.route('/cliente/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    if cliente.user_id != current_user.id:
        return jsonify({'error': 'Não autorizado'}), 403
    
    db.session.delete(cliente)
    db.session.commit()
    flash('Cliente excluído com sucesso!')
    return redirect(url_for('dashboard'))

@app.route('/cliente/editar', methods=['POST'])
@login_required
def editar_cliente():
    try:
        cliente = Cliente.query.get_or_404(request.form.get('id'))
        
        # Verificar se o cliente pertence ao usuário atual
        if cliente.user_id != current_user.id:
            return jsonify({'error': 'Não autorizado'}), 403
        
        # Atualizar dados do cliente
        cliente.razao_social = request.form.get('razao_social')
        cliente.cnpj = formatar_cnpj(request.form.get('cnpj'))
        cliente.proprietario = request.form.get('proprietario')
        cliente.telefone = formatar_telefone(request.form.get('telefone'))
        cliente.data_vencimento = datetime.strptime(request.form.get('data_vencimento'), '%Y-%m-%d').date()
        
        db.session.commit()
        flash('Cliente atualizado com sucesso!')
        
    except Exception as e:
        flash(f'Erro ao atualizar cliente: {str(e)}')
    
    return redirect(url_for('dashboard'))

@app.template_filter('status_vencimento')
def status_vencimento(data_vencimento):
    hoje = datetime.now().date()
    dias_restantes = (data_vencimento - hoje).days
    
    if dias_restantes < 0:
        return 'VENCIDO'
    elif dias_restantes <= 30:
        return 'PRÓXIMO AO VENCIMENTO'
    else:
        return 'REGULAR'

@app.route('/exportar-excel')
@login_required
def exportar_excel():
    try:
        # Criar um novo workbook e selecionar a planilha ativa
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Clientes"

        # Definir estilos
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="0D6EFD", end_color="0D6EFD", fill_type="solid")
        
        # Adicionar cabeçalho
        headers = ['ID', 'Razão Social', 'CNPJ', 'Proprietário', 'Telefone', 'Data Vencimento', 'Status']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill

        # Buscar clientes ordenados
        hoje = datetime.now().date()
        clientes = Cliente.query.filter_by(user_id=current_user.id).all()
        
        def ordem_status(cliente):
            dias_restantes = (cliente.data_vencimento - hoje).days
            if dias_restantes < 0:
                return 0  # VENCIDO
            elif dias_restantes <= 30:
                return 1  # PRÓXIMO AO VENCIMENTO
            else:
                return 2  # REGULAR
        
        clientes_ordenados = sorted(clientes, key=lambda x: (ordem_status(x), x.data_vencimento))

        # Adicionar dados
        for row, cliente in enumerate(clientes_ordenados, 2):
            ws.cell(row=row, column=1, value=cliente.id)
            ws.cell(row=row, column=2, value=cliente.razao_social)
            ws.cell(row=row, column=3, value=cliente.cnpj)
            ws.cell(row=row, column=4, value=cliente.proprietario)
            ws.cell(row=row, column=5, value=cliente.telefone)
            ws.cell(row=row, column=6, value=cliente.data_vencimento.strftime('%d/%m/%Y'))
            
            status = status_vencimento(cliente.data_vencimento)
            cell = ws.cell(row=row, column=7, value=status)
            
            # Definir cor do status
            if status == 'VENCIDO':
                cell.font = Font(color="FF0000")  # Vermelho
            elif status == 'PRÓXIMO AO VENCIMENTO':
                cell.font = Font(color="FFA500")  # Laranja
            else:
                cell.font = Font(color="008000")  # Verde

        # Ajustar largura das colunas
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column].width = adjusted_width

        # Salvar o arquivo em memória
        excel_file = io.BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)

        return send_file(
            excel_file,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'clientes_{datetime.now().strftime("%d%m%Y")}.xlsx'
        )

    except Exception as e:
        flash(f'Erro ao exportar para Excel: {str(e)}')
        return redirect(url_for('lista_clientes'))

@app.route('/dashboard-analytics')
@login_required
def dashboard_analytics():
    hoje = datetime.now().date()
    clientes = Cliente.query.filter_by(user_id=current_user.id).all()
    
    # Contadores para o gráfico de pizza
    vencidos = 0
    proximos = 0
    regulares = 0
    
    # Dicionário para contar vencimentos por mês
    vencimentos_mensais = {}
    
    for cliente in clientes:
        dias_restantes = (cliente.data_vencimento - hoje).days
        
        # Contar status
        if dias_restantes < 0:
            vencidos += 1
        elif dias_restantes <= 30:
            proximos += 1
        else:
            regulares += 1
        
        # Agrupar por mês
        mes_ano = cliente.data_vencimento.strftime('%m/%Y')
        if mes_ano in vencimentos_mensais:
            vencimentos_mensais[mes_ano] += 1
        else:
            vencimentos_mensais[mes_ano] = 1
    
    # Ordenar meses e preparar dados para o gráfico de barras
    meses_ordenados = sorted(vencimentos_mensais.keys(), 
                           key=lambda x: datetime.strptime(x, '%m/%Y'))
    vencimentos_por_mes = [vencimentos_mensais[mes] for mes in meses_ordenados]
    
    # Preparar dados para os templates
    stats = {
        'vencidos': vencidos,
        'proximos': proximos,
        'regulares': regulares
    }
    
    return render_template('dashboard_analytics.html',
                         stats=stats,
                         meses=meses_ordenados,
                         vencimentos_por_mes=vencimentos_por_mes)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 