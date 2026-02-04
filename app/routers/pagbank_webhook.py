# app/routers/pagbank_webhook.py
from __future__ import annotations

import hashlib
import hmac
import os
import traceback

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
import os
import smtplib
from email.mime.text import MIMEText

# para enviar email
from fastapi import BackgroundTasks

from app.database import get_db
from app.models.produto import Produto
from app.models.cliente import Cliente
from app.models.loja import Loja
from app.models.venda import Venda
from app.models.itvenda import ItVenda
from app.models.pagvenda import PagVenda
from app.models.carrinho import Carrinho
from app.models.itcarrinho import ItCarrinho

router = APIRouter(prefix="/pagamentos", tags=["pagamentos"])

PAGBANK_TOKEN = os.getenv("PAGBANK_TOKEN", "").strip()


from sqlalchemy.orm import Session

def montar_resumo_venda(db: Session, venda_id: int):
    venda = db.query(Venda).filter(Venda.venda_id == venda_id).first()
    if not venda:
        return None

    cliente = db.query(Cliente).filter(Cliente.cliente_id == venda.cliente_id).first()
    if not cliente or not cliente.emailcliente:
        return None

    # pega itens da venda com dados do produto
    rows = (
        db.query(
            ItVenda.produto_id,
            Produto.nmproduto,
            Produto.vrprecoprod,
            ItVenda.qtitvenda,  # se existir
        )
        .join(Produto, Produto.produto_id == ItVenda.produto_id)
        .filter(ItVenda.venda_id == venda_id)
        .all()
    )

    itens = []
    total = 0.0
    for produto_id, nmproduto, vrprecoprod, qtitvenda in rows:
        qt = int(qtitvenda or 1)
        preco = float(vrprecoprod or 0.0)
        subtotal = qt * preco
        total += subtotal
        itens.append({
            "produto_id": int(produto_id),
            "nmproduto": nmproduto,
            "vrprecoprod": preco,
            "qt": qt,
            "subtotal": subtotal,
        })

    return {
        "email": cliente.emailcliente,
        "nome": getattr(cliente, "nmcliente", "") or "",
        "venda_id": int(venda_id),
        "itens": itens,
        "total": total,
    }


def montar_email_texto(resumo: dict) -> str:
    linhas = []
    linhas.append(f"Olá {resumo['nome'] or 'cliente'},")
    linhas.append("")
    linhas.append(f"Pagamento confirmado! Venda #{resumo['venda_id']}")
    linhas.append("")
    linhas.append("Produtos:")

    for it in resumo["itens"]:
        linhas.append(
            f"{it['nmproduto']} | {it['qt']} x {it['vrprecoprod']:.2f} = R$ {it['subtotal']:.2f}"
        )

    linhas.append("")
    linhas.append(f"Total pago: R$ {resumo['total']:.2f}")
    linhas.append("")
    linhas.append("Obrigado pela compra!")
    return "\n".join(linhas)


def enviar_email_smtp(destino: str, assunto: str, corpo: str):

    try:

        host = os.getenv("SMTP_HOST")
        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("SMTP_USER")
        password = os.getenv("SMTP_PASS")
        from_email = os.getenv("SMTP_FROM", user)

        msg = MIMEText(corpo, "plain", "utf-8")
        msg["Subject"] = assunto
        msg["From"] = from_email
        msg["To"] = destino
        
        print("[EMAIL] Dados do email:", assunto,from_email,destino)


        with smtplib.SMTP_SSL(host, port, timeout=20) as server:
            server.login(user, password)
            server.sendmail(from_email, [destino], msg.as_string())

    except Exception as e:

        print("[EMAIL] Falha ao enviar:", repr(e))
        print(traceback.format_exc())


def validar_assinatura_pagbank(raw_body: bytes, header_signature: str) -> bool:
    """
    Se você for validar assinatura:
    - precisa saber qual header o PagBank envia (ex.: x-signature / x-hub-signature etc.)
    - e a regra exata. Aqui fica como referência.
    """
    if not PAGBANK_TOKEN or not header_signature:
        return False
    base = (PAGBANK_TOKEN + "-").encode("utf-8") + raw_body
    digest = hashlib.sha256(base).hexdigest()
    return hmac.compare_digest(digest, header_signature)


def extrair_reference_id_pagbank(data: dict) -> str | None:
    # alguns eventos vêm embrulhados em "data"
    if isinstance(data.get("data"), dict):
        ref = extrair_reference_id_pagbank(data["data"])
        if ref:
            return ref

    ref = data.get("reference_id")
    if ref:
        return ref

    charges = data.get("charges") or []
    if isinstance(charges, list):
        for ch in charges:
            ref = (ch or {}).get("reference_id")
            if ref:
                return ref

    checkout = data.get("checkout") or {}
    if isinstance(checkout, dict):
        ref = checkout.get("reference_id")
        if ref:
            return ref

    return None


def extrair_status_pagbank(data: dict) -> str:
    # 1) status no topo
    s = data.get("status")
    if s:
        return str(s).upper().strip()

    # 2) status dentro de data
    s = (data.get("data") or {}).get("status")
    if s:
        return str(s).upper().strip()

    # 3) charges[*].status
    charges = data.get("charges") or []
    if isinstance(charges, list):
        primeiro = ""
        for ch in charges:
            s = (ch or {}).get("status")
            if not s:
                continue
            st = str(s).upper().strip()
            if st == "PAID":
                return st
            if not primeiro:
                primeiro = st
        if primeiro:
            return primeiro

    return ""


@router.post("/webhook")
async def pagbank_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    raw = await request.body()
    print("[PAGBANK][WEBHOOK] RAW:", raw.decode("utf-8", errors="ignore"))

    # Se quiser validar assinatura, descomente e ajuste o header correto:
    # signature = request.headers.get("X-Signature", "")
    # if not validar_assinatura_pagbank(raw, signature):
    #     raise HTTPException(status_code=401, detail="Assinatura inválida")

    try:
        data = await request.json()
    except Exception:
        data = None

    print("[PAGBANK][WEBHOOK] JSON:", data)

    if not isinstance(data, dict):
        return {"ok": True, "ignored": "invalid_payload"}

    # 1) reference_id -> VENDA-XX
    reference_id = extrair_reference_id_pagbank(data)
    print("[PAGBANK][WEBHOOK] reference_id =", reference_id)

    if not reference_id or not str(reference_id).startswith("VENDA-"):
        return {"ok": True, "ignored": "no_reference_id", "reference_id": reference_id}

    try:
        venda_id = int(str(reference_id).split("-", 1)[1])
    except Exception:
        return {"ok": True, "ignored": "bad_reference_id", "reference_id": reference_id}

    # 2) status (pode vir vazio em eventos não conclusivos)
    status_charge = extrair_status_pagbank(data)
    print("[PAGBANK][WEBHOOK] status_charge =", status_charge)

    if status_charge == "":
        # evento “informativo” (ex.: order criado/qr gerado). Espera o evento com PAID.
        return {"ok": True, "ignored": "pending", "venda_id": venda_id}

    # 3) mapear status PagBank -> seu banco
    if status_charge == "PAID":
        novo_sitpag = "PAGO"
        novo_sitvenda = "PAGA"
    elif status_charge in {"CANCELED", "CANCELLED"}:
        novo_sitpag = "CANCELADO"
        novo_sitvenda = "CANCELADA"
    else:
        return {"ok": True, "ignored": "not_paid", "venda_id": venda_id, "status": status_charge}

    
    # buscar venda e pagvenda e loja para trazer dias de validade da ficha do item
    try:    

        carrinho_id = None
        carrinho    = None

        # abre transação
        with db.begin():
    
            venda = (
                db.query(Venda)
                .filter(Venda.venda_id == venda_id)
                .with_for_update()          # trava a linha da venda
                .first()
            )
            if not venda:
                return {"ok": True, "ignored": "not_found", "venda_id": venda_id}     

            pag = (
                db.query(PagVenda)
                .filter(PagVenda.venda_id == venda_id)
                .order_by(PagVenda.pagvenda_id.desc())
                .with_for_update()          # trava a linha do pag também
                .first()
            )
            if not pag:
                return {"ok": True, "ignored": "not_found", "venda_id": venda_id}

            # idempotência geral (pago ou cancelado)
            if (pag.sitpagvenda or "").upper() == novo_sitpag and (venda.sitvenda or "").upper() == novo_sitvenda:
                return {"ok": True, "already_processed": True, "venda_id": venda_id}

            # atualiza status
            pag.sitpagvenda = novo_sitpag
            pag.dtultatu    = datetime.now()
            venda.sitvenda  = novo_sitvenda
            venda.dtultatu  = datetime.now()

            
            # só calcula validade se realmente pagou
            if novo_sitpag == "PAGO" and novo_sitvenda in {"PAGA", "PAGO"}:
                # validade DATE (nrdiavalidade da loja)
                loja = (
                    db.query(Loja)
                    .filter(
                        Loja.loja_id == venda.loja_id,
                        Loja.organizacao_id == venda.organizacao_id,
                    )
                    .first()
                )
                nr_dias = int(getattr(loja, "nrdiavalidade", 0) or 0) if loja else 0
                if nr_dias <= 0:
                    nr_dias = 30

                data_expira = date.today() + timedelta(days=nr_dias)

                # atualizar itvenda da venda inteira (todas as linhas)
                db.query(ItVenda).filter(ItVenda.venda_id == venda_id).update(
                    {"dtexpiraitvenda": data_expira},
                    synchronize_session=False
                )
            ############ fecha if de atualizar validade do itemvenda

            # 7) fechar carrinho da venda (GARANTIDO) + limpar itens
            carrinho_id = getattr(venda, "carrinho_id", None)

            if carrinho_id:
                
                carrinho = (
                    db.query(Carrinho)
                    .filter(Carrinho.carrinho_id == carrinho_id)
                    .with_for_update()
                    .first()
                )

                if carrinho:
                    # fecha o carrinho (histórico)
                    carrinho.sitcarrinho = "FECHADO"

                    # limpa somente os itens do carrinho (opção A)
                    db.query(ItCarrinho).filter(
                        ItCarrinho.carrinho_id == carrinho.carrinho_id
                    ).delete(synchronize_session=False)
            else:
                # fallback opcional (só pra log)
                print("[PAGBANK][WEBHOOK] Aviso: venda sem carrinho_id, não fechei carrinho.")

        ### aqui finaliza o db.begin e isto já comita sozinho.       
        
        ####### enviar email confirmando a compra do cliente
        if status_charge == "PAID":
            resumo = montar_resumo_venda(db, venda_id)
            if resumo:
                assunto = f"Pagamento confirmado • Venda #{resumo['venda_id']}"
                corpo = montar_email_texto(resumo)
                background_tasks.add_task(enviar_email_smtp, resumo["email"], assunto, corpo)

        return {
            "ok": True,
            "venda_id": venda_id,
            "status": status_charge,
            "sitvenda_db": venda.sitvenda,
            "sitpagvenda_db": pag.sitpagvenda,
            "carrinho_encontrado": bool(carrinho)
        }

    except Exception as e:
        db.rollback()
        print("[PAGBANK][WEBHOOK] ERRO:", repr(e))
        print(traceback.format_exc())
        raise HTTPException(500, f"Erro processando webhook: {e}")
