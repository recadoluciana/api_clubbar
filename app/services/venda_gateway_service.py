
async def criar_venda_paga_por_carrinho_gateway(
    db: Session,
    *,
    carrinho_id: int,
    gateway: str,
    pagamento: dict,
    metodo_pagamento: str,
):
    carrinho_db = (
        db.query(Carrinho)
        .filter(Carrinho.carrinho_id == carrinho_id)
        .filter(Carrinho.sitcarrinho == "ABERTO")
        .first()
    )

    if not carrinho_db:
        print("[MP WEBHOOK] Carrinho não encontrado ou já fechado:", carrinho_id)
        return {
            "ok": True,
            "msg": "Carrinho não encontrado ou já fechado",
            "carrinho_id": carrinho_id,
        }

    carrinho = get_carrinho(
        db,
        carrinho_db.cliente_id,
        carrinho_db.loja_id,
    )

    if not carrinho:
        raise HTTPException(status_code=404, detail="Carrinho não encontrado")

    itens = carrinho.get("itens") or []

    if not itens:
        raise HTTPException(status_code=400, detail="Carrinho vazio")

    itens_recalculados, total_recalculado = _recalcular_itens_carrinho(
        db,
        itens,
    )

    payment_type_id = (pagamento.get("payment_type_id") or "").lower()
    payment_method_id = (pagamento.get("payment_method_id") or "").lower()

    if not metodo_pagamento:
        if payment_type_id == "credit_card":
            metodo_pagamento = "CREDITO"
        elif payment_type_id == "debit_card":
            metodo_pagamento = "DEBITO"
        elif payment_method_id == "pix" or payment_type_id in {"bank_transfer", "account_money"}:
            metodo_pagamento = "PIX"
        else:
            metodo_pagamento = "OUTRO"

    venda = await criar_ou_obter_venda_idempotente(
        db,
        cliente_id=carrinho_db.cliente_id,
        organizacao_id=carrinho_db.organizacao_id,
        loja_id=carrinho_db.loja_id,
        carrinho={
            **carrinho,
            "total": total_recalculado,
            "itens": itens_recalculados,
        },
        chave=str(uuid.uuid4()),
        metodo_pagamento=metodo_pagamento,
    )

    venda_id = int(venda["venda_id"])
    pagvenda_id = int(venda["pagvenda_id"])

    pag = (
        db.query(PagVenda)
        .filter(PagVenda.pagvenda_id == pagvenda_id)
        .with_for_update()
        .first()
    )

    if not pag:
        raise HTTPException(status_code=404, detail="PagVenda não encontrada")

    pag.dsmetodopag = metodo_pagamento
    pag.sitpagvenda = "PAGO"
    pag.idtransacaopagvenda = str(pagamento.get("id"))
    pag.checkout_id = str(pagamento.get("id"))
    pag.reference_id = str(venda_id)
    pag.pay_url = None
    pag.provedor = gateway

    resultado = set_venda_como_paga(
        db,
        venda_id=venda_id,
        gateway=gateway,
        payload=pagamento,
    )

    carrinho_db.idpixmercadopago = None
    carrinho_db.vrpixmercadopago = None

    return {
        "ok": True,
        "venda_id": venda_id,
        "pagvenda_id": pagvenda_id,
        "resultado": resultado,
    }