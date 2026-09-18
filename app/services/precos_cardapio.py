from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.cardapio import Cardapio, CardapioItem, CardapioVersao


def atualizar_preco_nas_lojas(
    db: Session, organizacao_id: int, produto_id: int, novo_preco: Decimal
) -> int:
    """Atualiza itens das lojas da mesma organização após confirmação explícita."""
    versoes = (
        db.query(CardapioVersao.cardapioversao_id)
        .join(Cardapio, Cardapio.cardapio_id == CardapioVersao.cardapio_id)
        .filter(
            Cardapio.organizacao_id == organizacao_id,
            CardapioVersao.statusversao.in_(["RASCUNHO", "PROGRAMADA", "PUBLICADA"]),
        )
    )
    return (
        db.query(CardapioItem)
        .filter(
            CardapioItem.produto_id == produto_id,
            CardapioItem.cardapioversao_id.in_(versoes),
        )
        .update({CardapioItem.vrpreco: novo_preco}, synchronize_session=False)
    )
