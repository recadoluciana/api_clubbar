import os
import stripe
from fastapi import HTTPException

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/pagar-cartao-stripe")
async def pagar_cartao_stripe(payload: PagarNovoIn, db: Session = Depends(get_db)):
    carrinho = get_carrinho(db, payload.cliente_id, payload.loja_id)

    if not carrinho:
        raise HTTPException(status_code=404, detail="Carrinho não encontrado")

    itens = carrinho.get("itens") or []

    if not itens:
        raise HTTPException(status_code=400, detail="Carrinho vazio")

    itens_recalculados, total_recalculado = _recalcular_itens_carrinho(db, itens)

    carrinho_id = int(carrinho.get("carrinho_id") or 0)

    if carrinho_id == 0:
        raise HTTPException(status_code=400, detail="Carrinho inválido")

    valor_centavos = int(round(float(total_recalculado) * 100))

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "brl",
                    "product_data": {
                        "name": f"Compra Clubbar - Carrinho {carrinho_id}",
                    },
                    "unit_amount": valor_centavos,
                },
                "quantity": 1,
            }
        ],
        success_url=f"{os.getenv('APP_URL')}/?pagamento=sucesso&gateway=stripe",
        cancel_url=f"{os.getenv('APP_URL')}/?pagamento=cancelado&gateway=stripe",
        metadata={
            "carrinho_id": str(carrinho_id),
            "cliente_id": str(payload.cliente_id),
            "loja_id": str(payload.loja_id),
            "organizacao_id": str(payload.organizacao_id),
        },
    )

    return {
        "ok": True,
        "gateway": "STRIPE",
        "checkout_url": session.url,
        "session_id": session.id,
        "carrinho_id": carrinho_id,
    }