from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String

from app.database import Base


class UsuarioSenha(Base):
    __tablename__ = "usuariosenha"

    usuariosenha_id = Column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id = Column(
        BigInteger,
        ForeignKey("usuario.usuario_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    codigohash = Column(String(255), nullable=False)
    expiracao = Column(DateTime, nullable=False)
    usado = Column(String(1), nullable=False, default="N")
    dtcriacao = Column(DateTime, nullable=False)
