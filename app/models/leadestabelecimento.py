import enum

from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, Numeric, String, Text, text

from app.database import Base


class StatusLeadEstabelecimento(str, enum.Enum):
    NOVO = "NOVO"
    CONTATADO = "CONTATADO"
    NEGOCIANDO = "NEGOCIANDO"
    ACEITOU_PARCERIA = "ACEITOU_PARCERIA"
    CONVERTIDO = "CONVERTIDO"
    RECUSOU_PARCERIA = "RECUSOU_PARCERIA"


class LeadEstabelecimento(Base):
    __tablename__ = "leadestabelecimento"

    leadestabelecimento_id = Column(BigInteger, primary_key=True, autoincrement=True)
    leadparceiro_id = Column(
        BigInteger,
        ForeignKey("leadparceiro.leadparceiro_id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
        index=True,
    )
    nmestabelecimento = Column(String(160), nullable=False)
    tipo = Column(String(30), nullable=False)
    tipovenda = Column(
        Enum("PRODUTOS", "INGRESSOS", "AMBOS", name="enum_leadestabelecimento_tipovenda"),
        nullable=False,
        server_default="AMBOS",
    )
    cpfcnpj = Column(String(14), nullable=True)
    estado_id = Column(BigInteger, ForeignKey("estado.estado_id"), nullable=False)
    cidade_id = Column(BigInteger, ForeignKey("cidade.cidade_id"), nullable=False)
    cep = Column(String(9), nullable=True)
    endereco = Column(String(255), nullable=True)
    numero = Column(String(20), nullable=True)
    complemento = Column(String(120), nullable=True)
    bairro = Column(String(120), nullable=True)
    mensagem = Column(Text, nullable=True)
    status = Column(Enum(StatusLeadEstabelecimento), nullable=False, server_default=text("'NOVO'"), index=True)
    decisao = Column(
        Enum("PENDENTE", "ANALISANDO", "ACEITOU", "RECUSOU", name="enum_leadestabelecimento_decisao"),
        nullable=False,
        server_default="PENDENTE",
    )
    vrtaxaprod = Column(Numeric(10, 2), nullable=False, server_default="5")
    vrtaxaing = Column(Numeric(10, 2), nullable=False, server_default="5")
    dtaceite = Column(DateTime, nullable=True)
    dtconversao = Column(DateTime, nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(DateTime, nullable=True, server_onupdate=text("CURRENT_TIMESTAMP"))
