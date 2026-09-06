from sqlalchemy import BigInteger, CHAR, Column, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Time, UniqueConstraint, text

from app.database import Base


class CategoriaPadrao(Base):
    __tablename__ = "categoriapadrao"

    categoriapadrao_id = Column(BigInteger, primary_key=True, autoincrement=True)
    nmcategoria = Column(String(120), nullable=False, unique=True)
    dsicone = Column(String(50), nullable=True)
    sitcategoria = Column(String(10), nullable=False, server_default="ATIVA")
    idordcategoria = Column(BigInteger, nullable=False, server_default="1")
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(DateTime, nullable=True, server_onupdate=text("CURRENT_TIMESTAMP"))


class Cardapio(Base):
    __tablename__ = "cardapio"

    cardapio_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, nullable=False, index=True)
    loja_id = Column(BigInteger, ForeignKey("loja.loja_id"), nullable=False, index=True)
    nmcardapio = Column(String(120), nullable=False)
    tipocardapio = Column(Enum("PRINCIPAL", "ESPECIAL", "SAZONAL", "EVENTO"), nullable=False, server_default="PRINCIPAL")
    prioridade = Column(Integer, nullable=False, server_default="0")
    sitcardapio = Column(Enum("ATIVO", "INATIVO"), nullable=False, server_default="ATIVO")
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(DateTime, nullable=True, server_onupdate=text("CURRENT_TIMESTAMP"))

    __table_args__ = (UniqueConstraint("loja_id", "nmcardapio", name="uk_cardapio_loja_nome"),)


class CardapioVersao(Base):
    __tablename__ = "cardapioversao"

    cardapioversao_id = Column(BigInteger, primary_key=True, autoincrement=True)
    cardapio_id = Column(BigInteger, ForeignKey("cardapio.cardapio_id", ondelete="CASCADE"), nullable=False, index=True)
    nrversao = Column(Integer, nullable=False)
    statusversao = Column(Enum("RASCUNHO", "AGUARDANDO_ASAAS", "PROGRAMADA", "PUBLICADA", "SUBSTITUIDA", "CANCELADA"), nullable=False, server_default="RASCUNHO")
    publicaraposaprovacao = Column(CHAR(1), nullable=False, server_default="N")
    dtiniciovigencia = Column(DateTime, nullable=True)
    dtfimvigencia = Column(DateTime, nullable=True)
    dtpublicacao = Column(DateTime, nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(DateTime, nullable=True, server_onupdate=text("CURRENT_TIMESTAMP"))

    __table_args__ = (UniqueConstraint("cardapio_id", "nrversao", name="uk_cardapioversao_numero"),)


class CardapioVersaoCategoria(Base):
    __tablename__ = "cardapioversaocategoria"

    cardapioversaocategoria_id = Column(BigInteger, primary_key=True, autoincrement=True)
    cardapioversao_id = Column(BigInteger, ForeignKey("cardapioversao.cardapioversao_id", ondelete="CASCADE"), nullable=False, index=True)
    categoria_id = Column(BigInteger, ForeignKey("categoria.categoria_id"), nullable=False)
    idordcategoria = Column(Integer, nullable=False, server_default="1")

    __table_args__ = (UniqueConstraint("cardapioversao_id", "categoria_id", name="uk_cardapioversaocategoria"),)


class CardapioItem(Base):
    __tablename__ = "cardapioitem"

    cardapioitem_id = Column(BigInteger, primary_key=True, autoincrement=True)
    cardapioversao_id = Column(BigInteger, ForeignKey("cardapioversao.cardapioversao_id", ondelete="CASCADE"), nullable=False, index=True)
    cardapioversaocategoria_id = Column(BigInteger, ForeignKey("cardapioversaocategoria.cardapioversaocategoria_id", ondelete="CASCADE"), nullable=False)
    produto_id = Column(BigInteger, ForeignKey("produto.produto_id"), nullable=False)
    vrpreco = Column(Numeric(10, 2), nullable=False)
    sititem = Column(Enum("ATIVO", "INATIVO"), nullable=False, server_default="ATIVO")
    idorditem = Column(Integer, nullable=False, server_default="1")
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(DateTime, nullable=True, server_onupdate=text("CURRENT_TIMESTAMP"))

    __table_args__ = (UniqueConstraint("cardapioversao_id", "produto_id", name="uk_cardapioitem_produto"),)


class CardapioProgramacao(Base):
    __tablename__ = "cardapioprogramacao"

    cardapioprogramacao_id = Column(BigInteger, primary_key=True, autoincrement=True)
    cardapio_id = Column(BigInteger, ForeignKey("cardapio.cardapio_id", ondelete="CASCADE"), nullable=False, index=True)
    diasemana = Column(Integer, nullable=True)
    dtinicio = Column(Date, nullable=True)
    dtfim = Column(Date, nullable=True)
    hrinicio = Column(Time, nullable=True)
    hrfim = Column(Time, nullable=True)
    sitprogramacao = Column(Enum("ATIVA", "INATIVA"), nullable=False, server_default="ATIVA")
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(DateTime, nullable=True, server_onupdate=text("CURRENT_TIMESTAMP"))


class CardapioReajuste(Base):
    __tablename__ = "cardapioreajuste"

    cardapioreajuste_id = Column(BigInteger, primary_key=True, autoincrement=True)
    cardapioversao_id = Column(BigInteger, ForeignKey("cardapioversao.cardapioversao_id"), nullable=False, index=True)
    categoria_id = Column(BigInteger, ForeignKey("categoria.categoria_id"), nullable=True)
    usuario_id = Column(BigInteger, ForeignKey("usuario.usuario_id"), nullable=False)
    tipoajuste = Column(Enum("PERCENTUAL", "VALOR"), nullable=False)
    operacao = Column(Enum("AUMENTO", "REDUCAO"), nullable=False)
    valorajuste = Column(Numeric(10, 2), nullable=False)
    arredondamento = Column(Integer, nullable=False, server_default="2")
    qtitensalterados = Column(Integer, nullable=False, server_default="0")
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
