"""Vínculo de categorias do catálogo mestre de produtos.

O nome do módulo é mantido temporariamente para evitar uma mudança de import
ampla; ele não contém mais o modelo legado de cardápios.
"""

from sqlalchemy import BigInteger, Column, ForeignKey

from app.database import Base


class ProdutoCategoriaOrg(Base):
    __tablename__ = "produtocategoriaorg"

    produto_id = Column(
        BigInteger,
        ForeignKey("produto.produto_id", ondelete="CASCADE"),
        primary_key=True,
    )
    categoria_id = Column(
        BigInteger,
        ForeignKey("categoriaorg.categoria_id"),
        primary_key=True,
    )
