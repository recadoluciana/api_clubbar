#leadmaterial.py
from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.sql import func

from app.database import Base


class LeadMaterial(Base):
    __tablename__ = "leadmaterial"

    leadmaterial_id = Column(BigInteger, primary_key=True, autoincrement=True)
    leadparceiro_id = Column(
        BigInteger,
        ForeignKey("leadparceiro.leadparceiro_id"),
        nullable=False,
        index=True,
    )
    titulo = Column(String(160), nullable=False)
    descricao = Column(String(500), nullable=True)
    tipo = Column(
        Enum(
            "APRESENTACAO",
            "PROPOSTA",
            "CONTRATO",
            "VIDEO",
            "OUTRO",
            name="enum_leadmaterial_tipo",
        ),
        nullable=False,
    )
    urlarquivo = Column(String(500), nullable=False)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())