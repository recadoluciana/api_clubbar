# app/models/leadparceiro.py

from sqlalchemy import BigInteger, Column, DateTime, String, UniqueConstraint, text

from app.database import Base


class LeadParceiro(Base):
    __tablename__ = "leadparceiro"
    __table_args__ = (
        UniqueConstraint("email", "telefone", name="uq_leadparceiro_email_telefone"),
    )

    leadparceiro_id = Column(
        BigInteger,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    nmresponsavel = Column(
        String(120),
        nullable=False,
    )

    nmorganizacao = Column(String(160), nullable=True)
    
    telefone = Column(
        String(30),
        nullable=False,
    )

    email = Column(
        String(160),
        nullable=False,
        index=True,
    )

    dtcriacao = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    dtultatu = Column(
        DateTime,
        nullable=True,
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    def __repr__(self) -> str:
        return (
            f"<LeadParceiro "
            f"id={self.leadparceiro_id} "
            f"responsavel={self.nmresponsavel}>"
        )
