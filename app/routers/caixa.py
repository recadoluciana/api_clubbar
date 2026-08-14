import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import (
    APP_ENV,
    ASAAS_API_KEY,
    ASAAS_PIX_ADDRESS_KEY,
    ASAAS_SANDBOX_PAYER_API_KEY,
)
from app.core.security import get_usuario_logado, hash_senha
from app.database import get_db
from app.models.carrinho import Carrinho
from app.models.checkout_asaas import CheckoutAsaas
from app.models.cliente import Cliente
from app.models.itvenda import ItVenda
from app.models.loja import Loja
from app.models.produto import Produto
from app.models.venda import Venda
from app.routers.carrinho import adicionar_item
from app.routers.pagamentos import (
    _montar_itens_asaas,
    _recalcular_itens_carrinho,
    pagar_asaas,
    status_checkout_asaas,
)
from app.schemas.carrinho import AddItemIn
from app.schemas.pagamentos import PagarNovoIn
from app.services.carrinho_service import get_carrinho
from app.services.asaas_service import (
    criar_qrcode_pix_estatico_asaas,
    excluir_qrcode_pix_estatico_asaas,
    pagar_qrcode_pix_sandbox_asaas,
)
from app.services.venda_service import criar_ou_obter_venda_idempotente


router = APIRouter(prefix="/caixa", tags=["Frente de caixa"])
EMAIL_CLIENTE_PADRAO = "consumidor.nao.identificado@clubbar.app"


class CaixaItemIn(BaseModel):
    produto_id: int
    quantidade: int = Field(default=1, ge=1)
    observacao: str | None = None


def _contexto_caixa(payload: dict, db: Session) -> tuple[Loja, Cliente]:
    cargo = str(payload.get("dscargo") or "").upper()
    if payload.get("role") != "usuario" or cargo not in {"CAIXA", "TOTEM"}:
        raise HTTPException(403, "Acesso exclusivo para usuários CAIXA.")
    loja_id = payload.get("loja_id")
    organizacao_id = payload.get("organizacao_id")
    if not loja_id:
        raise HTTPException(403, "O usuário CAIXA deve estar vinculado a uma loja.")
    loja = db.query(Loja).filter(
        Loja.loja_id == int(loja_id),
        Loja.organizacao_id == int(organizacao_id),
    ).first()
    if not loja:
        raise HTTPException(404, "Loja do caixa não encontrada.")
    cliente = db.query(Cliente).filter(Cliente.cliente_padrao == "S").first()
    if not cliente:
        cliente = Cliente(
            nmcliente="Consumidor nao identificado",
            emailcliente=EMAIL_CLIENTE_PADRAO,
            senhahashcli=hash_senha(uuid.uuid4().hex),
            sitcliente="ATIVO",
            emailconf="S",
            cliente_padrao="S",
        )
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
    return loja, cliente


@router.get("/contexto")
def contexto(payload: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    loja, cliente = _contexto_caixa(payload, db)
    return {
        "cliente_id": cliente.cliente_id,
        "cliente_nome": cliente.nmcliente,
        "loja_id": loja.loja_id,
        "organizacao_id": loja.organizacao_id,
        "nmloja": loja.nmloja,
        "vrtaxaprod": float(loja.vrtaxaprod or 0),
        "vrtaxaing": float(loja.vrtaxaing or 0),
    }


@router.post("/carrinho/itens")
def adicionar_item_caixa(dados: CaixaItemIn, payload: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    loja, cliente = _contexto_caixa(payload, db)
    carrinho_aberto = db.query(Carrinho).filter(
        Carrinho.cliente_id == cliente.cliente_id,
        Carrinho.loja_id == loja.loja_id,
        Carrinho.usuario_id == int(payload["sub"]),
        Carrinho.sitcarrinho == "ABERTO",
    ).first()
    if carrinho_aberto:
        pix_pendente = db.query(CheckoutAsaas).filter(
            CheckoutAsaas.carrinho_id == carrinho_aberto.carrinho_id,
            CheckoutAsaas.status == "PENDING",
            CheckoutAsaas.pix_qr_code_id.isnot(None),
            CheckoutAsaas.pix_expiration_date > datetime.now(),
        ).first()
        if pix_pendente:
            raise HTTPException(
                409,
                "Carrinho bloqueado enquanto o QR Code PIX estiver aguardando pagamento.",
            )
    produto = db.query(Produto).filter(
        Produto.produto_id == dados.produto_id,
        Produto.loja_id == loja.loja_id,
        Produto.organizacao_id == loja.organizacao_id,
        Produto.sitproduto == "ATIVO",
        Produto.idtipoproduto == "P",
    ).first()
    if not produto:
        raise HTTPException(404, "Produto não encontrado nesta loja.")
    return adicionar_item(
        AddItemIn(
            cliente_id=cliente.cliente_id,
            usuario_id=int(payload["sub"]),
            organizacao_id=loja.organizacao_id,
            loja_id=loja.loja_id,
            idtipoproduto="P",
            produto_id=produto.produto_id,
            qt=dados.quantidade,
            obs=dados.observacao,
        ),
        db,
    )


@router.get("/carrinho")
def consultar_carrinho(payload: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    loja, cliente = _contexto_caixa(payload, db)
    try:
        return get_carrinho(
            db, cliente.cliente_id, loja.loja_id, int(payload["sub"])
        )
    except HTTPException as exc:
        if exc.status_code not in {400, 404}:
            raise
        return {
            "carrinho_id": 0,
            "usuario_id": int(payload["sub"]),
            "itens": [],
            "total": 0,
        }


@router.post("/checkout/cartao")
async def checkout_cartao(payload: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    loja, cliente = _contexto_caixa(payload, db)
    return await pagar_asaas(
        PagarNovoIn(
            cliente_id=cliente.cliente_id,
            usuario_id=int(payload["sub"]),
            organizacao_id=loja.organizacao_id,
            loja_id=loja.loja_id,
            dsmetodopag="CREDIT_CARD",
            percentual_taxa_ingresso=float(loja.vrtaxaing or 0),
            percentual_taxa_produto=float(loja.vrtaxaprod or 0),
            origem_checkout="PARTNER",
        ),
        db,
    )


@router.post("/checkout/pix")
async def checkout_pix(payload: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    loja, cliente = _contexto_caixa(payload, db)
    if not ASAAS_API_KEY:
        raise HTTPException(503, "Conta global Asaas nao configurada")

    carrinho = get_carrinho(db, cliente.cliente_id, loja.loja_id, int(payload["sub"]))
    itens = carrinho.get("itens") or []
    if not itens:
        raise HTTPException(400, "Carrinho vazio")

    itens_recalculados, _ = _recalcular_itens_carrinho(db, itens)
    _, valor_total, valor_taxa = _montar_itens_asaas(itens_recalculados)
    carrinho_id = int(carrinho["carrinho_id"])

    qr_ativo = (
        db.query(CheckoutAsaas)
        .filter(
            CheckoutAsaas.carrinho_id == carrinho_id,
            CheckoutAsaas.pix_qr_code_id.isnot(None),
            CheckoutAsaas.status == "PENDING",
            CheckoutAsaas.pix_expiration_date > datetime.now(),
        )
        .order_by(CheckoutAsaas.checkout_asaas_id.desc())
        .first()
    )
    if qr_ativo and qr_ativo.pix_payload and qr_ativo.pix_encoded_image:
        return {
            "venda_id": int(qr_ativo.venda_id),
            "pagamento_id": qr_ativo.pix_qr_code_id,
            "pix_qr_code_id": qr_ativo.pix_qr_code_id,
            "encoded_image": qr_ativo.pix_encoded_image,
            "payload": qr_ativo.pix_payload,
            "expiration_date": qr_ativo.pix_expiration_date.isoformat(),
            "status": "PENDENTE",
            "reutilizado": True,
            "simulacao_sandbox_disponivel": bool(
                APP_ENV not in {"production", "prod"} and ASAAS_SANDBOX_PAYER_API_KEY
            ),
        }

    venda = await criar_ou_obter_venda_idempotente(
        db,
        cliente_id=cliente.cliente_id,
        usuario_id=int(payload["sub"]),
        organizacao_id=loja.organizacao_id,
        loja_id=loja.loja_id,
        carrinho={
            **carrinho,
            "total": valor_total,
            "itens": itens_recalculados,
        },
        chave=f"PIX-CAIXA-{carrinho_id}",
        plataforma="TOTEM",
        metodo_pagamento="PIX",
    )
    venda_id = int(venda["venda_id"])

    qr = await criar_qrcode_pix_estatico_asaas(
        address_key=ASAAS_PIX_ADDRESS_KEY,
        valor=valor_total,
        descricao=f"Clubbar venda {venda_id}",
        api_key=ASAAS_API_KEY,
    )
    pix_qr_code_id = str(qr["id"])
    registro = CheckoutAsaas(
        carrinho_id=carrinho_id,
        cliente_id=cliente.cliente_id,
        loja_id=loja.loja_id,
        venda_id=venda_id,
        checkout_id=pix_qr_code_id,
        pix_qr_code_id=pix_qr_code_id,
        pix_payload=str(qr["payload"]),
        pix_encoded_image=str(qr.get("encodedImage") or ""),
        pix_expiration_date=datetime.now() + timedelta(minutes=10),
        external_reference=f"VENDA-{venda_id}",
        status="PENDING",
        valor=valor_total,
        vrtaxaclubbar=valor_taxa,
    )
    db.add(registro)
    db.commit()
    return {
        "venda_id": venda_id,
        "pagamento_id": pix_qr_code_id,
        "pix_qr_code_id": pix_qr_code_id,
        "encoded_image": qr.get("encodedImage"),
        "payload": qr["payload"],
        "expiration_date": qr.get("expirationDate"),
        "status": "PENDENTE",
        "reutilizado": False,
        "simulacao_sandbox_disponivel": bool(
            APP_ENV not in {"production", "prod"} and ASAAS_SANDBOX_PAYER_API_KEY
        ),
    }


@router.post("/checkout/{checkout_id}/cancelar-pix")
async def cancelar_pix(
    checkout_id: str,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    loja, cliente = _contexto_caixa(payload, db)
    checkout = db.query(CheckoutAsaas).filter(
        CheckoutAsaas.checkout_id == checkout_id,
        CheckoutAsaas.loja_id == loja.loja_id,
        CheckoutAsaas.cliente_id == cliente.cliente_id,
        CheckoutAsaas.status == "PENDING",
    ).first()
    if not checkout or not checkout.pix_qr_code_id:
        raise HTTPException(404, "PIX pendente nao encontrado")
    await excluir_qrcode_pix_estatico_asaas(
        checkout.pix_qr_code_id, ASAAS_API_KEY
    )
    checkout.status = "CANCELLED"
    checkout.pix_expiration_date = datetime.now()
    db.commit()
    return {"status": "CANCELADO", "carrinho_liberado": True}


@router.post("/checkout/{checkout_id}/simular-pagamento-pix")
async def simular_pagamento_pix(
    checkout_id: str,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    loja, cliente = _contexto_caixa(payload, db)
    if APP_ENV in {"production", "prod"} or not ASAAS_SANDBOX_PAYER_API_KEY:
        raise HTTPException(404, "Simulacao PIX nao disponivel")
    checkout = db.query(CheckoutAsaas).filter(
        CheckoutAsaas.checkout_id == checkout_id,
        CheckoutAsaas.loja_id == loja.loja_id,
        CheckoutAsaas.cliente_id == cliente.cliente_id,
        CheckoutAsaas.status == "PENDING",
    ).first()
    if not checkout or not checkout.pix_payload:
        raise HTTPException(404, "PIX pendente nao encontrado")
    if checkout.pix_expiration_date and checkout.pix_expiration_date <= datetime.now():
        raise HTTPException(410, "QR Code PIX expirado")
    resultado = await pagar_qrcode_pix_sandbox_asaas(
        payload=checkout.pix_payload,
        valor=float(checkout.valor or 0),
        api_key_pagador=ASAAS_SANDBOX_PAYER_API_KEY,
    )
    return {
        "id": resultado.get("id"),
        "status": resultado.get("status"),
        "mensagem": (
            "Pagamento Sandbox enviado. Autorize a acao critica na conta "
            "pagadora, se solicitado."
        ),
    }


@router.get("/checkout/{checkout_id}/tickets")
async def tickets(checkout_id: str, payload: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    loja, cliente = _contexto_caixa(payload, db)
    status_checkout = await status_checkout_asaas(checkout_id, db)
    checkout_db = db.query(CheckoutAsaas).filter(
        CheckoutAsaas.checkout_id == checkout_id,
        CheckoutAsaas.loja_id == loja.loja_id,
        CheckoutAsaas.cliente_id == cliente.cliente_id,
    ).first()
    if not checkout_db:
        raise HTTPException(404, "Checkout não encontrado.")
    venda = db.query(Venda).filter(
        Venda.carrinho_id == checkout_db.carrinho_id,
        Venda.loja_id == loja.loja_id,
        Venda.cliente_id == cliente.cliente_id,
    ).order_by(Venda.venda_id.desc()).first()
    if not venda or venda.sitvenda != "PAGA":
        return {"status": status_checkout.get("status", "PENDENTE"), "tickets": []}
    itens = db.query(ItVenda, Produto).join(Produto, Produto.produto_id == ItVenda.produto_id).filter(
        ItVenda.venda_id == venda.venda_id
    ).order_by(ItVenda.itvenda_id).all()
    return {
        "status": "PAGO",
        "venda_id": venda.venda_id,
        "tickets": [
            {
                "itvenda_id": item.itvenda_id,
                "produto": produto.nmproduto,
                "observacao": item.dsobsitvenda,
                "valor": float(item.vrunititvenda or 0),
                "qr_token": item.qrtokenitvenda,
                "loja": loja.nmloja,
            }
            for item, produto in itens
        ],
    }
