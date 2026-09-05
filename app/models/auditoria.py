from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    func,
)

from app.database import Base


class Auditoria(Base):
    __tablename__ = "auditoria"

    auditoria_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(
        BigInteger,
        ForeignKey("organizacao.organizacao_id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    loja_id = Column(
        BigInteger,
        ForeignKey("loja.loja_id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    tabela = Column(String(100), nullable=False)
    registro_id = Column(String(255), nullable=False)
    acao = Column(String(15), nullable=False)

    ator_tipo = Column(String(20), nullable=False, default="SISTEMA")
    ator_id = Column(String(100), nullable=True)
    usuario_id = Column(
        BigInteger,
        ForeignKey("usuario.usuario_id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    operador_id = Column(
        BigInteger,
        ForeignKey("operador.operador_id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    ator_nome = Column(String(200), nullable=False)
    ator_email = Column(String(200), nullable=True)

    dados_anteriores = Column(JSON, nullable=True)
    dados_novos = Column(JSON, nullable=True)
    metodo_http = Column(String(10), nullable=True)
    rota = Column(String(500), nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    __table_args__ = (
        Index("idx_auditoria_registro", "tabela", "registro_id", "dtcriacao"),
        Index("idx_auditoria_organizacao", "organizacao_id", "dtcriacao"),
        Index("idx_auditoria_loja", "loja_id", "dtcriacao"),
        Index("idx_auditoria_usuario", "usuario_id", "dtcriacao"),
        Index("idx_auditoria_operador", "operador_id", "dtcriacao"),
    )
