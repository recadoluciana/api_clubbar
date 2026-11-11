import importlib
import pkgutil

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import app.models

for module in pkgutil.iter_modules(app.models.__path__):
    importlib.import_module(f'app.models.{module.name}')

from app.services.cortesia_evento_service import validar_cortesia_unica_por_cpf


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE cliente (cliente_id INTEGER PRIMARY KEY, nmcliente TEXT)'))
        conn.execute(text('CREATE TABLE venda (venda_id INTEGER PRIMARY KEY, sitvenda TEXT, cliente_id INTEGER)'))
        conn.execute(text('CREATE TABLE eventoloteglobal (loteglobal_id INTEGER PRIMARY KEY, evento_id INTEGER)'))
        conn.execute(text('CREATE TABLE eventolotesetor (lote_id INTEGER PRIMARY KEY, loteglobal_id INTEGER)'))
        conn.execute(text('CREATE TABLE itvenda (itvenda_id INTEGER PRIMARY KEY, venda_id INTEGER, lote_id INTEGER, cpfparticipante TEXT, tipoitem TEXT, sititvenda TEXT, vrunititvenda NUMERIC)'))
        conn.execute(text("INSERT INTO cliente VALUES (1, 'Maria Silva')"))
        conn.execute(text("INSERT INTO venda VALUES (1, 'PAGA', 1), (2, 'CANCELADA', NULL)"))
        conn.execute(text('INSERT INTO eventoloteglobal VALUES (1, 10), (2, 11)'))
        conn.execute(text('INSERT INTO eventolotesetor VALUES (1, 1), (2, 2)'))
        conn.execute(text("INSERT INTO itvenda VALUES (1, 1, 1, '12345678909', 'INGRESSO', 'ATIVO', 0), (2, 1, 1, '98765432100', 'INGRESSO', 'ATIVO', 5), (3, 2, 1, '11111111111', 'INGRESSO', 'CANCELADO', 0)"))
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_bloqueia_gratuito_existente_no_mesmo_evento(db):
    with pytest.raises(HTTPException) as erro:
        validar_cortesia_unica_por_cpf(db, evento_id=10, cpf='12345678909')
    assert erro.value.status_code == 409
    assert erro.value.detail == 'Este CPF já resgatou uma cortesia deste evento. O resgate foi feito pela conta Maria.'


def test_bloqueia_cpf_com_formatacao_em_registro_antigo(db):
    db.execute(text("UPDATE itvenda SET cpfparticipante='123.456.789-09' WHERE itvenda_id=1"))
    with pytest.raises(HTTPException):
        validar_cortesia_unica_por_cpf(db, evento_id=10, cpf='12345678909')


def test_nao_bloqueia_outro_evento_pago_cancelado_ou_proprio_item(db):
    validar_cortesia_unica_por_cpf(db, evento_id=11, cpf='12345678909')
    validar_cortesia_unica_por_cpf(db, evento_id=10, cpf='98765432100')
    validar_cortesia_unica_por_cpf(db, evento_id=10, cpf='11111111111')
    validar_cortesia_unica_por_cpf(db, evento_id=10, cpf='12345678909', ignorar_itvenda_id=1)


def test_cancelamento_pendente_ainda_impede_novo_resgate(db):
    db.execute(text("UPDATE itvenda SET sititvenda='CANCELAMENTO_SOLICITADO' WHERE itvenda_id=1"))
    with pytest.raises(HTTPException):
        validar_cortesia_unica_por_cpf(db, evento_id=10, cpf='12345678909')
