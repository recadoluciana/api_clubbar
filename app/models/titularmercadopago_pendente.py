from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text

from app.database import Base


class TitularMercadoPagoPendente(Base):
    """Autorização OAuth que aguarda confirmação do titular financeiro."""

    __tablename__ = "titularmercadopagopendente"

    titularfinanceiro_id = Column(
        BigInteger,
        ForeignKey("titularfinanceiro.titularfinanceiro_id"),
        primary_key=True,
    )
    ambiente = Column(String(20), primary_key=True)
    confirmacao_id = Column(String(64), nullable=False)
    credenciais = Column(Text, nullable=False)
    expira_em = Column(DateTime, nullable=False)
