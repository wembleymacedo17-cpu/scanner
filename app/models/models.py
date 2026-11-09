from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

db = SQLAlchemy()


class Usuario(db.Model):
    """Tabela de Usuários do sistema com níveis de acesso e controle de sessão única."""
    __tablename__ = 'usuarios'

    id_usuario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    perfil = db.Column(db.String(20), nullable=False, default='OPERADOR')  
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    session_token = db.Column(db.String(36), nullable=True, index=True)
    data_criacao = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def checar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def gerar_novo_session_token(self):
        """Gera e atribui um novo token único de sessão."""
        self.session_token = str(uuid.uuid4())
        return self.session_token

    def to_dict(self):
        return {
            'id_usuario': self.id_usuario,
            'nome': self.nome,
            'email': self.email,
            'perfil': self.perfil,
            'ativo': self.ativo,
            'data_criacao': self.data_criacao.isoformat() if self.data_criacao else None
        }

    
class HistoricoBaixa(db.Model):
    """Tabela para registro e auditoria de cada baixa realizada."""
    __tablename__ = 'historico_baixas'

    __table_args__ = (
        db.Index('idx_historico_user_data', 'id_usuario', db.desc('data_baixa')),
        db.Index('idx_historico_data_baixa', db.desc('data_baixa')),
    )

    id_historico = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=True)
    nome_operador = db.Column(db.String(255), nullable=True)
    codigo_retirada = db.Column(db.String(36), nullable=False, index=True)
    id_colaborador = db.Column(db.Integer, nullable=False)
    nome_beneficiario = db.Column(db.String(255), nullable=True)
    tipo_publico = db.Column(db.String(50), nullable=False)
    index_kit = db.Column(db.Integer, nullable=False)
    modelo_baixa = db.Column(db.String(100), nullable=False)
    divergencia_modelo = db.Column(db.Boolean, default=False, nullable=False)
    modelo_esperado = db.Column(db.String(100), nullable=True)
    data_baixa = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id_historico': self.id_historico,
            'id_usuario': self.id_usuario,
            'nome_operador': self.nome_operador or "Sistema / Anônimo",
            'codigo_retirada': self.codigo_retirada,
            'id_colaborador': self.id_colaborador,
            'nome_beneficiario': self.nome_beneficiario,
            'tipo_publico': self.tipo_publico,
            'index_kit': self.index_kit,
            'modelo_baixa': self.modelo_baixa,
            'divergencia_modelo': self.divergencia_modelo,
            'modelo_esperado': self.modelo_esperado or "---",
            'data_baixa': self.data_baixa.strftime("%d/%m/%Y %H:%M:%S")
        }
        


class BaseRetirada(db.Model):
    __abstract__ = True

    id_retirada = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo_retirada = db.Column(db.String(36), unique=True, nullable=False, index=True)
    id_colaborador = db.Column(db.Integer, nullable=False, index=True)
    email = db.Column(db.String(255), nullable=True)
    telefone = db.Column(db.String(50), nullable=True)
    qtd_kits = db.Column(db.Integer, nullable=False, default=1)
    resumo_kits = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='PENDENTE', index=True)
    data_geracao = db.Column(db.String(50), nullable=True)
    data_entrega = db.Column(db.DateTime, nullable=True)
    detalhes_entregas = db.Column(db.JSON, nullable=True)


class RetiradaDependente(BaseRetirada):
    __tablename__ = 'retiradas_dependentes'

    nome_colaborador = db.Column(db.String(255), nullable=True)
    log_modificacao_cracha = db.Column(db.String(100), nullable=True)
    necessita_recontato = db.Column(db.String(10), nullable=True)
    motivo_recontato = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id_retirada': self.id_retirada,
            'codigo_retirada': self.codigo_retirada,
            'id_colaborador': self.id_colaborador,
            'nome_colaborador': self.nome_colaborador or "NÃO INFORMADO",
            'log_modificacao_cracha': self.log_modificacao_cracha,
            'email': self.email,
            'telefone': self.telefone,
            'qtd_kits': self.qtd_kits,
            'resumo_kits': self.resumo_kits,
            'status': self.status,
            'data_geracao': self.data_geracao,
            'data_entrega': self.data_entrega.isoformat() if self.data_entrega else None,
            'necessita_recontato': self.necessita_recontato,
            'motivo_recontato': self.motivo_recontato,
            'detalhes_entregas': self.detalhes_entregas or {},
            'tipo_publico': 'Dependente'
        }


class RetiradaJovemAprendiz(BaseRetirada):
    __tablename__ = 'retiradas_jovens_aprendizes'

    def extrair_nome_jovem(self):
        if not self.resumo_kits:
            return f"Jovem Aprendiz (ID {self.id_colaborador})"
        primeira_parte = self.resumo_kits.split('|')[0].strip()
        nome_extraido = primeira_parte.split('-')[0].strip()
        return nome_extraido if nome_extraido else f"Jovem Aprendiz (ID {self.id_colaborador})"

    def to_dict(self):
        return {
            'id_retirada': self.id_retirada,
            'codigo_retirada': self.codigo_retirada,
            'id_colaborador': self.id_colaborador,
            'nome_colaborador': self.extrair_nome_jovem(),
            'email': self.email,
            'telefone': self.telefone,
            'qtd_kits': self.qtd_kits,
            'resumo_kits': self.resumo_kits,
            'status': self.status,
            'data_geracao': self.data_geracao,
            'data_entrega': self.data_entrega.isoformat() if self.data_entrega else None,
            'detalhes_entregas': self.detalhes_entregas or {},
            'tipo_publico': 'Jovem Aprendiz'
        }


class EstoqueKit(db.Model):
    __tablename__ = 'estoque_kits'

    id_estoque = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo_kit = db.Column(db.String(50), unique=True, nullable=False, index=True)
    descricao_kit = db.Column(db.String(255), nullable=False)
    quantidade_disponivel = db.Column(db.Integer, nullable=False, default=0) 
    quantidade_reservada = db.Column(db.Integer, nullable=False, default=0)  
    quantidade_baixada = db.Column(db.Integer, nullable=False, default=0)    
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    ultima_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        saidas = self.quantidade_baixada or 0
        lote_total = self.quantidade_disponivel or 0
        saldo_balcao = max(0, lote_total - saidas)
        reserva = self.quantidade_reservada or 0
        sobra_orfaos = saldo_balcao - reserva

        return {
            'id_estoque': self.id_estoque,
            'codigo_kit': self.codigo_kit,
            'descricao_kit': self.descricao_kit,
            'quantidade_total_entrada': lote_total,
            'quantidade_baixada': saidas,
            'quantidade_disponivel': saldo_balcao,  # Retorna o saldo real em mãos para as telas
            'quantidade_reservada': reserva,
            'sobra_orfaos': max(0, sobra_orfaos),
            'ativo': self.ativo,
            'ultima_atualizacao': self.ultima_atualizacao.isoformat() if self.ultima_atualizacao else None
        }


class MovimentacaoEstoque(db.Model):
    __tablename__ = 'movimentacoes_estoque'

    id_movimentacao = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_estoque = db.Column(db.Integer, db.ForeignKey('estoque_kits.id_estoque'), nullable=False, index=True)
    tipo_movimentacao = db.Column(db.String(20), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    codigo_retirada = db.Column(db.String(36), nullable=True)
    observacao = db.Column(db.Text, nullable=True)
    data_movimentacao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    estoque = db.relationship('EstoqueKit', backref=db.backref('movimentacoes', lazy=True))

    def to_dict(self):
        return {
            'id_movimentacao': self.id_movimentacao,
            'id_estoque': self.id_estoque,
            'tipo_movimentacao': self.tipo_movimentacao,
            'quantidade': self.quantidade,
            'codigo_retirada': self.codigo_retirada,
            'observacao': self.observacao,
            'data_movimentacao': self.data_movimentacao.isoformat() if self.data_movimentacao else None
        }