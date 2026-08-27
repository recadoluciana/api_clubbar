from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Atracao(Base):
    __tablename__ = "atracao"
    atracao_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    nmatracao = Column(String(120), nullable=False)
    dsestilomusical = Column(String(255))
    urlbanneratracao = Column(String(255))
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, onupdate=func.now())
    eventos = relationship("EventoAtracao", back_populates="atracao")
    detalhes = relationship(
        "AtracaoDescricao",
        back_populates="atracao",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    @property
    def dsatracao(self):
        return self.detalhes.dsatracao if self.detalhes else None

    @dsatracao.setter
    def dsatracao(self, valor):
        if self.detalhes is None:
            from app.models.atracaodescricao import AtracaoDescricao
            self.detalhes = AtracaoDescricao()
        self.detalhes.dsatracao = valor


from app.models.atracaodescricao import AtracaoDescricao  # noqa: E402,F401
