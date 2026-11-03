from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class BaseRetirada(db.Model):
    """Classe abstrata base contendo os campos em comum para retiradas."""
    __abstract__ = True

    id_retirada = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo_retirada = db.Column(db.String(36), unique=True, nullable=False, index=True)  # UUID
    id_colaborador = db.Column(db.Integer, nullable=False, index=True)
    email = db.Column(db.String(255), nullable=True)
    telefone = db.Column(db.String(50), nullable=True)
    qtd_kits = db.Column(db.Integer, nullable=False, default=1)
    resumo_kits = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='PENDENTE', index=True)
    data_geracao = db.Column(db.String(50), nullable=True)
    data_entrega = db.Column(db.DateTime, nullable=True)


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
            'nome_colaborador': self.nome_colaborador,
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
            'tipo_publico': 'DEPENDENTE'
        }


class RetiradaJovemAprendiz(BaseRetirada):
    """Mapeamento da tabela de retiradas para Jovens Aprendizes (CSV)."""
    __tablename__ = 'retiradas_jovens_aprendizes'

    def to_dict(self):
        return {
            'id_retirada': self.id_retirada,
            'codigo_retirada': self.codigo_retirada,
            'id_colaborador': self.id_colaborador,
            'email': self.email,
            'telefone': self.telefone,
            'qtd_kits': self.qtd_kits,
            'resumo_kits': self.resumo_kits,
            'status': self.status,
            'data_geracao': self.data_geracao,
            'data_entrega': self.data_entrega.isoformat() if self.data_entrega else None,
            'tipo_publico': 'JOVEM_APRENDIZ'
        }