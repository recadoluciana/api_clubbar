from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, func

from app.database import Base


class CheckoutAsaasItem(Base):
    __tablename__ = "checkout_asaas_item"

    checkout_asaas_item_id = Column(BigInteger, primary_key=True, autoincrement=True)
    checkout_asaas_id = Column(
        BigInteger,
        ForeignKey("checkout_asaas.checkout_asaas_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    produto_id = Column(BigInteger, ForeignKey("produto.produto_id"), nullable=False)
    lote_id = Column(BigInteger, ForeignKey("eventolote.lote_id"), nullable=True)
    idtipoproduto = Column(String(1), nullable=False, server_default="P")
    nmproduto = Column(String(150), nullable=False)
    quantidade = Column(Integer, nullable=False)
    vrunitario = Column(Numeric(10, 2), nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)
    total_com_taxa = Column(Numeric(10, 2), nullable=False)
    pctaxaitvenda = Column(Numeric(10, 2), nullable=False, server_default="0")
    vrtaxaitvenda = Column(Numeric(10, 2), nullable=False, server_default="0")
    dsobsitem = Column(String(255), nullable=True)
    nmparticipante = Column(String(150), nullable=True)
    cpfparticipante = Column(String(11), nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
