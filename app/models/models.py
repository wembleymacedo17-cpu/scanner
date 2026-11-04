from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class BaseRetirada(db.Model):
    """Classe abstrata base contendo os campos em comum para retiradas."""
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
    """Mapeamento da tabela de retiradas de Kits de Dependentes (Excel)."""
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
    """Mapeamento da tabela de retiradas para Jovens Aprendizes (CSV)."""
    __tablename__ = 'retiradas_jovens_aprendizes'

    def extrair_nome_jovem(self):
        """Extrai o nome do Jovem Aprendiz do texto do resumo de kits."""
        if not self.resumo_kits:
            return f"Jovem Aprendiz (ID {self.id_colaborador})"
        
        # Pega a primeira parte antes do traço '-'
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
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    ultima_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id_estoque': self.id_estoque,
            'codigo_kit': self.codigo_kit,
            'descricao_kit': self.descricao_kit,
            'quantidade_disponivel': self.quantidade_disponivel,
            'quantidade_reservada': self.quantidade_reservada,
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