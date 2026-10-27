from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, UniqueConstraint, text

from app.database import Base


class ClienteIdentidadeSocial(Base):
    __tablename__ = 'clienteidentidadesocial'

    clienteidentidadesocial_id = Column(
        BigInteger, primary_key=True, index=True, autoincrement=True,
    )
    cliente_id = Column(
        BigInteger,
        ForeignKey('cliente.cliente_id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    provedor = Column(String(20), nullable=False)
    subject = Column(String(255), nullable=False)
    email = Column(String(160), nullable=True)
    dtcriacao = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP'),
    )
    dtultatu = Column(DateTime, nullable=True, server_onupdate=text('CURRENT_TIMESTAMP'))

    __table_args__ = (
        UniqueConstraint(
            'provedor', 'subject', name='uq_clienteidentidadesocial_provedor_subject',
        ),
    )
