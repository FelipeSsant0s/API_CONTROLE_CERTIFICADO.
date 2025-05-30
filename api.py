from flask import Blueprint, jsonify, request
from flask_login import LoginManager, login_required, current_user
from models import db, Certificado, User
from datetime import datetime, timedelta
import jwt
from functools import wraps
import logging
import os
from werkzeug.utils import secure_filename
import xml.etree.ElementTree as ET

# Create API Blueprint
api_bp = Blueprint('api', __name__)

# Configure logging
logger = logging.getLogger(__name__)

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Configuração para upload de arquivos
UPLOAD_FOLDER = 'uploads/xml'
ALLOWED_EXTENSIONS = {'xml'}

# Garantir que o diretório de upload existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            token = request.headers.get('Authorization')
            if not token:
                logger.warning('No token provided')
                return jsonify({'message': 'Token não fornecido'}), 401
            
            try:
                token = token.split(' ')[1]  # Remove o 'Bearer ' do token
                logger.debug(f'Decoding token: {token}')
                data = jwt.decode(token, os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key'), algorithms=['HS256'])
                logger.debug(f'Token data: {data}')
                current_user = User.query.get(data['user_id'])
                if not current_user:
                    logger.warning(f'User not found for id: {data["user_id"]}')
                    return jsonify({'message': 'Usuário não encontrado'}), 401
            except jwt.ExpiredSignatureError:
                logger.warning('Token expired')
                return jsonify({'message': 'Token expirado'}), 401
            except jwt.InvalidTokenError as e:
                logger.warning(f'Invalid token: {str(e)}')
                return jsonify({'message': 'Token inválido'}), 401
            except Exception as e:
                logger.error(f'Error processing token: {str(e)}')
                return jsonify({'message': 'Erro ao processar token'}), 401
            
            return f(current_user, *args, **kwargs)
        except Exception as e:
            logger.error(f'Unexpected error in token_required: {str(e)}')
            return jsonify({'message': 'Erro interno do servidor'}), 500
    return decorated

# API Routes
@api_bp.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(days=1)
        }, os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key'))
        
        return jsonify({
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        })
    
    return jsonify({'message': 'Credenciais inválidas'}), 401

@api_bp.route('/certificados', methods=['GET'])
@token_required
def get_certificados(current_user):
    try:
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
    except Exception as e:
        logger.error(f"Erro ao buscar certificados: {str(e)}")
        return jsonify({'error': 'Erro ao buscar certificados'}), 500

@api_bp.route('/certificados/<int:id>', methods=['GET'])
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

@api_bp.route('/certificados', methods=['POST'])
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

@api_bp.route('/certificados/<int:id>', methods=['PUT'])
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

@api_bp.route('/certificados/<int:id>', methods=['DELETE'])
@token_required
def delete_certificado(current_user, id):
    certificado = Certificado.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    
    db.session.delete(certificado)
    db.session.commit()
    
    return jsonify({'message': 'Certificado excluído com sucesso'})

# Endpoint para estatísticas
@api_bp.route('/dashboard/stats', methods=['GET'])
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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@api_bp.route('/upload_xml', methods=['POST'])
def api_upload_xml():
    try:
        # Verificar se o arquivo foi enviado
        if 'xml_file' not in request.files:
            logger.error("Nenhum arquivo enviado")
            return jsonify({
                'status': 'error',
                'message': 'Nenhum arquivo enviado'
            }), 400

        file = request.files['xml_file']
        if file.filename == '':
            logger.error("Nome do arquivo vazio")
            return jsonify({
                'status': 'error',
                'message': 'Nome do arquivo vazio'
            }), 400

        # Verificar se é um arquivo XML
        if not allowed_file(file.filename):
            logger.error(f"Tipo de arquivo não permitido: {file.filename}")
            return jsonify({
                'status': 'error',
                'message': 'Tipo de arquivo não permitido. Apenas XML é aceito.'
            }), 400

        # Salvar o arquivo
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # Processar o XML
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()

            # Extrair dados do XML
            empresa_id = request.form.get('empresa_id', '')
            razao_social = root.find('.//razao_social').text
            nome_fantasia = root.find('.//nome_fantasia').text
            cnpj = root.find('.//cnpj').text
            telefone = root.find('.//telefone').text
            data_validade = datetime.strptime(root.find('.//data_validade').text, '%Y-%m-%d')
            observacoes = request.form.get('observacoes', '')

            # Criar novo certificado
            certificado = Certificado(
                empresa_id=empresa_id,
                razao_social=razao_social,
                nome_fantasia=nome_fantasia,
                cnpj=cnpj,
                telefone=telefone,
                data_validade=data_validade,
                observacoes=observacoes
            )

            db.session.add(certificado)
            db.session.commit()

            logger.info(f"Certificado criado com sucesso para a empresa {empresa_id}")
            return jsonify({
                'status': 'success',
                'message': 'Certificado processado com sucesso',
                'certificado_id': certificado.id
            }), 201

        except ET.ParseError as e:
            logger.error(f"Erro ao processar XML: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Erro ao processar o arquivo XML'
            }), 400
        except Exception as e:
            logger.error(f"Erro ao processar certificado: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Erro ao processar o certificado: {str(e)}'
            }), 500

    except Exception as e:
        logger.error(f"Erro no endpoint de upload: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Erro ao processar o upload: {str(e)}'
        }), 500 