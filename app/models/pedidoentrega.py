from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.sql import func

from app.database import Base


class PedidoEntrega(Base):
    """Acompanhamento operacional de uma venda de produtos entregue no endereço."""

    __tablename__ = "pedidoentrega"

    pedidoentrega_id = Column(BigInteger, primary_key=True, autoincrement=True)
    venda_id = Column(
        BigInteger,
        ForeignKey("venda.venda_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    situacaopedido = Column(
        Enum(
            "AGUARDANDO_ACEITE",
            "ACEITO",
            "EM_ROTA",
            "ENTREGUE",
            "RECUSADO",
            "CANCELADO",
            name="situacaopedidoentrega_enum",
        ),
        nullable=False,
        server_default="AGUARDANDO_ACEITE",
        index=True,
    )
    # Token único do pedido: é o QR Code apresentado pelo cliente ao entregador.
    qrcode_token = Column(String(120), nullable=False, unique=True, index=True)

    cepentrega = Column(String(10), nullable=False)
    enderecoentrega = Column(String(255), nullable=False)
    numeroentrega = Column(String(20), nullable=False)
    complementoentrega = Column(String(120), nullable=True)
    bairroentrega = Column(String(120), nullable=False)
    cidadeentrega = Column(String(120), nullable=False)
    ufentrega = Column(String(2), nullable=False)
    observacaoentrega = Column(String(255), nullable=True)

    dtaceite = Column(DateTime, nullable=True)
    dtdespacho = Column(DateTime, nullable=True)
    dtrecebimento = Column(DateTime, nullable=True)
    dtrecusa = Column(DateTime, nullable=True)
    motivorecusa = Column(String(255), nullable=True)

    usuarioaceite_id = Column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=True)
    usuariodespacho_id = Column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=True)
    usuariorecebimento_id = Column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=True)

    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.current_timestamp())
