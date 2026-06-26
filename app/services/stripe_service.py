import os
import stripe
from fastapi import HTTPException

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

APP_URL = os.getenv("APP_URL", "https://app.clubbar.com.br")
API_URL = os.getenv("API_URL", "https://api.clubbar.com.br")


def criar_checkout_stripe(
    *,
    carrinho_id: int,
    cliente_id: int,
    organizacao_id: int,
    loja_id: int,
    valor_total: float,
    email: str | None = None,
):
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY não configurada")

    valor_centavos = int(round(float(valor_total or 0) * 100))

    if valor_centavos <= 0:
        raise HTTPException(status_code=400, detail="Valor inválido para pagamento Stripe")

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        customer_email=email if email and "@" in email else None,
        billing_address_collection="auto",
        phone_number_collection={"enabled": True},
        automatic_tax={"enabled": False},
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
        success_url=f"{API_URL}/stripe/sucesso?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{APP_URL}/?pagamento=cancelado&gateway=stripe",
        metadata={
            "carrinho_id": str(carrinho_id),
            "cliente_id": str(cliente_id),
            "loja_id": str(loja_id),
            "organizacao_id": str(organizacao_id),
            "gateway": "STRIPE",
        },
    )

    return session