from sqlalchemy import (
    Column,
    BigInteger,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from app.database import Base

class Usuario(Base):
    __tablename__ = "usuario"

    usuario_id = Column(BigInteger, primary_key=True, index=True)

    organizacao_id = Column(
        BigInteger,
        ForeignKey("organizacao.organizacao_id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
        index=True,
    )

    loja_id = Column(
        BigInteger,
        ForeignKey("loja.loja_id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=True,
        index=True,
    )

    nmusuario = Column(String(200), nullable=False)

    emailuser = Column(
        String(200),
        nullable=False,
        unique=True,
        index=True,
    )

    senhahashuser = Column(String(255), nullable=False)

    dscargo = Column(String(50), nullable=False, default="BARMAN")

    situsuario = Column(String(15), nullable=False, default="ATIVO")

    dtcriacao = Column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    dtultatu = Column(
        DateTime,
        nullable=True,
        onupdate=func.current_timestamp(),
    )

    def __repr__(self) -> str:
        return f"<Usuario id={self.usuario_id} email={self.emailuser} cargo={self.dscargo}>"
