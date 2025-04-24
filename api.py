from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models import db, Certificado, User
from datetime import datetime, timedelta
import jwt
from functools import wraps
import xml.etree.ElementTree as ET
import os
from werkzeug.utils import secure_filename

api = Blueprint('api', __name__)

# Configuração do JWT
SECRET_KEY = 'sua-chave-secreta-aqui'  # Em produção, use uma chave segura e armazene em variáveis de ambiente

# Configuração para upload de arquivos
UPLOAD_FOLDER = 'uploads/xml'
ALLOWED_EXTENSIONS = {'xml'}

# Garantir que o diretório de upload existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token não fornecido'}), 401
        
        try:
            token = token.split(' ')[1]  # Remove o 'Bearer ' do token
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
        except:
            return jsonify({'message': 'Token inválido'}), 401
        
        return f(current_user, *args, **kwargs)
    return decorated

# Rota de autenticação para gerar token
@api.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(days=1)
        }, SECRET_KEY)
        
        return jsonify({
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        })
    
    return jsonify({'message': 'Credenciais inválidas'}), 401

# Endpoints para Certificados
@api.route('/certificados', methods=['GET'])
@token_required
def get_certificados(current_user):
    certificados = Certificado.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'id': c.id,
        'razao_social': c.razao_social,
        'nome_fantasia': c.nome_fantasia,
        'cnpj': c.cnpj,
        'telefone': c.telefone,
        'data_emissao': c.data_emissao.isoformat(),
        'data_validade': c.data_validade.isoformat(),
        'status': c.status,
        'observacoes': c.observacoes
    } for c in certificados])

@api.route('/certificados/<int:id>', methods=['GET'])
@token_required
def get_certificado(current_user, id):
    certificado = Certificado.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    return jsonify({
        'id': certificado.id,
        'razao_social': certificado.razao_social,
        'nome_fantasia': certificado.nome_fantasia,
        'cnpj': certificado.cnpj,
        'telefone': certificado.telefone,
        'data_emissao': certificado.data_emissao.isoformat(),
        'data_validade': certificado.data_validade.isoformat(),
        'status': certificado.status,
        'observacoes': certificado.observacoes
    })

@api.route('/certificados', methods=['POST'])
@token_required
def create_certificado(current_user):
    data = request.get_json()
    
    # Validação básica
    required_fields = ['razao_social', 'nome_fantasia', 'cnpj', 'telefone', 'data_validade']
    if not all(field in data for field in required_fields):
        return jsonify({'message': 'Campos obrigatórios faltando'}), 400
    
    try:
        data_validade = datetime.fromisoformat(data['data_validade'])
    except ValueError:
        return jsonify({'message': 'Formato de data inválido'}), 400
    
    # Verifica se já existe certificado com o mesmo CNPJ
    if Certificado.query.filter_by(cnpj=data['cnpj'], user_id=current_user.id).first():
        return jsonify({'message': 'Já existe um certificado com este CNPJ'}), 400
    
    certificado = Certificado(
        razao_social=data['razao_social'],
        nome_fantasia=data['nome_fantasia'],
        cnpj=data['cnpj'],
        telefone=data['telefone'],
        data_validade=data_validade,
        observacoes=data.get('observacoes', ''),
        user_id=current_user.id
    )
    
    db.session.add(certificado)
    db.session.commit()
    
    return jsonify({
        'message': 'Certificado criado com sucesso',
        'id': certificado.id
    }), 201

@api.route('/certificados/<int:id>', methods=['PUT'])
@token_required
def update_certificado(current_user, id):
    certificado = Certificado.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    
    # Validação básica
    required_fields = ['razao_social', 'nome_fantasia', 'cnpj', 'telefone', 'data_validade']
    if not all(field in data for field in required_fields):
        return jsonify({'message': 'Campos obrigatórios faltando'}), 400
    
    try:
        data_validade = datetime.fromisoformat(data['data_validade'])
    except ValueError:
        return jsonify({'message': 'Formato de data inválido'}), 400
    
    # Verifica se o novo CNPJ já existe em outro certificado
    if data['cnpj'] != certificado.cnpj:
        if Certificado.query.filter_by(cnpj=data['cnpj'], user_id=current_user.id).first():
            return jsonify({'message': 'Já existe um certificado com este CNPJ'}), 400
    
    certificado.razao_social = data['razao_social']
    certificado.nome_fantasia = data['nome_fantasia']
    certificado.cnpj = data['cnpj']
    certificado.telefone = data['telefone']
    certificado.data_validade = data_validade
    certificado.observacoes = data.get('observacoes', '')
    
    db.session.commit()
    
    return jsonify({'message': 'Certificado atualizado com sucesso'})

@api.route('/certificados/<int:id>', methods=['DELETE'])
@token_required
def delete_certificado(current_user, id):
    certificado = Certificado.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    
    db.session.delete(certificado)
    db.session.commit()
    
    return jsonify({'message': 'Certificado excluído com sucesso'})

# Endpoint para estatísticas
@api.route('/dashboard/stats', methods=['GET'])
@token_required
def get_stats(current_user):
    certificados = Certificado.query.filter_by(user_id=current_user.id).all()
    
    stats = {
        'total_certificados': len(certificados),
        'proximos_vencer': sum(1 for c in certificados if c.status == 'Próximo ao Vencimento'),
        'expirados': sum(1 for c in certificados if c.status == 'Expirado'),
        'validos': sum(1 for c in certificados if c.status == 'Válido')
    }
    
    return jsonify(stats)

# Endpoint para upload de XML
@api.route('/xml/upload', methods=['POST'])
@token_required
def upload_xml(current_user):
    try:
        # Verifica se o arquivo foi enviado
        if 'file' not in request.files:
            return jsonify({'message': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['file']
        
        # Verifica se um arquivo foi selecionado
        if file.filename == '':
            return jsonify({'message': 'Nenhum arquivo selecionado'}), 400
        
        # Verifica se é um arquivo XML
        if not allowed_file(file.filename):
            return jsonify({'message': 'Tipo de arquivo não permitido. Apenas XML é aceito.'}), 400
        
        # Salva o arquivo
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Processa o XML
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            
            # Aqui você pode adicionar a lógica para processar o XML
            # Por exemplo, extrair dados e criar/atualizar certificados
            
            # Exemplo de processamento (ajuste conforme sua estrutura XML)
            for certificado_xml in root.findall('certificado'):
                try:
                    razao_social = certificado_xml.find('razao_social').text
                    nome_fantasia = certificado_xml.find('nome_fantasia').text
                    cnpj = certificado_xml.find('cnpj').text
                    telefone = certificado_xml.find('telefone').text
                    data_validade = datetime.fromisoformat(certificado_xml.find('data_validade').text)
                    
                    # Verifica se já existe certificado com o mesmo CNPJ
                    certificado_existente = Certificado.query.filter_by(
                        cnpj=cnpj,
                        user_id=current_user.id
                    ).first()
                    
                    if certificado_existente:
                        # Atualiza o certificado existente
                        certificado_existente.razao_social = razao_social
                        certificado_existente.nome_fantasia = nome_fantasia
                        certificado_existente.telefone = telefone
                        certificado_existente.data_validade = data_validade
                        certificado_existente.observacoes = f"Atualizado via XML em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
                    else:
                        # Cria novo certificado
                        novo_certificado = Certificado(
                            razao_social=razao_social,
                            nome_fantasia=nome_fantasia,
                            cnpj=cnpj,
                            telefone=telefone,
                            data_validade=data_validade,
                            observacoes=f"Importado via XML em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                            user_id=current_user.id
                        )
                        db.session.add(novo_certificado)
                    
                except Exception as e:
                    logger.error(f'Erro ao processar certificado do XML: {str(e)}')
                    continue
            
            db.session.commit()
            
            return jsonify({
                'message': 'Arquivo XML processado com sucesso',
                'filename': filename
            }), 200
            
        except ET.ParseError as e:
            return jsonify({'message': f'Erro ao processar XML: {str(e)}'}), 400
        
    except Exception as e:
        logger.error(f'Erro no upload de XML: {str(e)}')
        return jsonify({'message': 'Erro interno do servidor'}), 500

# Endpoint para listar arquivos XML processados
@api.route('/xml/files', methods=['GET'])
@token_required
def list_xml_files(current_user):
    try:
        files = []
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.endswith('.xml'):
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                files.append({
                    'filename': filename,
                    'size': os.path.getsize(filepath),
                    'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                })
        
        return jsonify(files)
    except Exception as e:
        logger.error(f'Erro ao listar arquivos XML: {str(e)}')
        return jsonify({'message': 'Erro interno do servidor'}), 500 