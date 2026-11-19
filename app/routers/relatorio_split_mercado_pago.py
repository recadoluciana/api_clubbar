import csv
import io
import os
import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import criar_jwt, get_usuario_logado, verificar_jwt
from app.database import get_db
from app.models.checkout_mercadopago import CheckoutMercadoPago
from app.models.loja import Loja
from app.routers.reconciliacao_cancelamentos import _organizacao_administradora

router = APIRouter(prefix='/relatorio-split-mercado-pago', tags=['Relatório split Mercado Pago'])
BASE = 'https://api.mercadopago.com/v1/reports/marketplace_sellers_sales'
CAMPOS = ('COLLECTOR', 'COLLECTOR_NICKNAME', 'PAYMENT', 'STATUS_DESCRIPTION',
          'STATUS_DETAIL', 'PURCHASE_ORDER', 'PAYMENT_METHOD_TYPE', 'TRANSACTION_AMOUNT',
          'DATE_CREATED', 'DATE_APPROVED', 'MARKETPLACE_FEE_AMOUNT',
          'MERCADOPAGO_FEE_AMOUNT', 'TOTAL_PAID_AMOUNT', 'NET_RECEIVED_AMOUNT')


class Periodo(BaseModel):
    inicio: date
    fim: date


def _config():
    token = os.getenv('MERCADO_PAGO_REPORT_ACCESS_TOKEN', '').strip()
    estrutura = os.getenv('MERCADO_PAGO_REPORT_STRUCTURE_ID', '').strip()
    notificador = os.getenv('MERCADO_PAGO_REPORT_NOTIFIER_ID', '').strip()
    if not token or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', estrutura) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', notificador):
        raise HTTPException(503, 'Relatório ainda não configurado. Contate a administração do Clubbar.')
    return token, int(estrutura) if estrutura.isdigit() else estrutura, int(notificador) if notificador.isdigit() else notificador


def _report_id(comprovante: str, organizacao_id: int) -> str:
    try:
        dados = verificar_jwt(comprovante)
    except HTTPException as exc:
        raise HTTPException(400, 'Consulta expirada ou inválida. Gere outro relatório.') from exc
    if dados.get('tipo') != 'relatorio_split' or dados.get('organizacao_id') != organizacao_id:
        raise HTTPException(403, 'Relatório não disponível para esta empresa.')
    identificador = str(dados.get('relatorio_id') or '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', identificador):
        raise HTTPException(400, 'Identificador de relatório inválido.')
    return identificador


async def _request(method: str, url: str, token: str, **kwargs):
    try:
        async with httpx.AsyncClient(timeout=35) as client:
            resposta = await client.request(method, url, headers={'Authorization': f'Bearer {token}'}, **kwargs)
    except httpx.RequestError as exc:
        raise HTTPException(502, 'Não foi possível conectar ao Mercado Pago.') from exc
    if resposta.is_error:
        raise HTTPException(502, f'Mercado Pago não conseguiu processar o relatório (HTTP {resposta.status_code}).')
    return resposta


@router.post('')
async def gerar(periodo: Periodo, payload: dict = Depends(get_usuario_logado)):
    organizacao_id = _organizacao_administradora(payload)
    if periodo.inicio > periodo.fim or (periodo.fim - periodo.inicio).days > 90:
        raise HTTPException(422, 'Escolha um período válido de até 91 dias.')
    if periodo.fim > datetime.now(ZoneInfo('America/Sao_Paulo')).date():
        raise HTTPException(422, 'A data final não pode estar no futuro.')
    token, estrutura, notificador = _config()
    fuso = ZoneInfo('America/Sao_Paulo')
    inicio = datetime.combine(periodo.inicio, time.min, fuso).astimezone(timezone.utc)
    fim = (datetime.combine(periodo.fim + timedelta(days=1), time.min, fuso) - timedelta(milliseconds=1)).astimezone(timezone.utc)
    resposta = await _request('POST', f'{BASE}/statements', token, json={
        'user_description': 'Clubbar - relatorio de vendas', 'created_by': 'automatic',
        'origin': {'type': 'date_range', 'data': {'date_start': inicio.isoformat().replace('+00:00', 'Z'), 'date_end': fim.isoformat().replace('+00:00', 'Z')}},
        'structure_id': estrutura, 'notifiers_id': [notificador],
    })
    try:
        identificador = str(resposta.json()['request_id'])
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', identificador):
            raise ValueError('id inválido')
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(502, 'Mercado Pago retornou uma resposta de relatório inválida.') from exc
    comprovante = criar_jwt({'tipo': 'relatorio_split', 'organizacao_id': organizacao_id, 'relatorio_id': identificador}, expires_delta=timedelta(days=1))
    return {'comprovante': comprovante, 'status': 'processing'}


@router.post('/consultar')
async def consultar(dados: dict, payload: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    organizacao_id = _organizacao_administradora(payload)
    identificador = _report_id(str(dados.get('comprovante') or ''), organizacao_id)
    token, _, _ = _config()
    resposta = await _request('GET', f'{BASE}/statements/{identificador}', token)
    try:
        situacao = str(resposta.json().get('status') or '').lower()
    except ValueError as exc:
        raise HTTPException(502, 'Mercado Pago retornou um status inválido.') from exc
    if situacao != 'available':
        return {'status': situacao or 'processing', 'itens': []}
    arquivo = await _request('GET', f'{BASE}/statements/{identificador}/download', token, params={'format': 'csv'})
    if len(arquivo.content) > 20_000_000:
        raise HTTPException(422, 'Relatório muito grande. Selecione um período menor.')
    try:
        leitor = csv.DictReader(io.StringIO(arquivo.content.decode('utf-8-sig')), delimiter=';')
        if not set(CAMPOS).issubset(set(leitor.fieldnames or [])):
            raise HTTPException(502, 'A estrutura do relatório não contém todas as colunas necessárias.')
        linhas = list(leitor)
    except UnicodeDecodeError as exc:
        raise HTTPException(502, 'Não foi possível ler o relatório do Mercado Pago.') from exc
    ids = {str(linha.get('PAYMENT') or '').strip() for linha in linhas} - {''}
    autorizados = set()
    lista_ids = list(ids)
    for indice in range(0, len(lista_ids), 500):
        consulta = (db.query(CheckoutMercadoPago.payment_id)
                    .join(Loja, Loja.loja_id == CheckoutMercadoPago.loja_id)
                    .filter(Loja.organizacao_id == organizacao_id,
                            CheckoutMercadoPago.payment_id.in_(lista_ids[indice:indice + 500])).all())
        autorizados.update(str(item[0]) for item in consulta)
    itens = [{campo: linha.get(campo, '') for campo in CAMPOS}
             for linha in linhas if str(linha.get('PAYMENT') or '').strip() in autorizados]
    return {'status': 'available', 'itens': itens}
