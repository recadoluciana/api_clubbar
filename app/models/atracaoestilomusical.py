from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Table
from sqlalchemy.sql import func

from app.database import Base


atracao_estilo_musical = Table(
    "atracaoorganizacaoestilomusical",
    Base.metadata,
    Column(
        "atracao_id",
        BigInteger,
        ForeignKey("atracao.atracao_id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    ),
    Column(
        "organizacaoestilomusical_id",
        BigInteger,
        ForeignKey(
            "organizacaoestilomusical.organizacaoestilomusical_id",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
    ),
    Column("dtcriacao", DateTime, nullable=False, server_default=func.now()),
)
