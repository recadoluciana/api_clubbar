import importlib
import pkgutil
from unittest.mock import patch

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

import app.models
for module in pkgutil.iter_modules(app.models.__path__):
    importlib.import_module(f'app.models.{module.name}')

from app.models.loja import Loja
from app.models.cliente import Cliente
from app.models.campanha_promocional import CampanhaPromocional
from app.models.dispositivo_promocao import DispositivoPromocao
from app.models.envio_campanha_promocional import EnvioCampanhaPromocional
from app.routers.campanhas_promocionais import EnvioIn, enviar, resultado, clique_email, _processar_envios
from app.routers.dispositivos_promocao import listar_notificacoes, registrar_clique


@compiles(BigInteger, 'sqlite')
def _bigint_sqlite(_type, _compiler, **_kwargs):
    return 'INTEGER'


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    for model in (Loja, Cliente, CampanhaPromocional, DispositivoPromocao, EnvioCampanhaPromocional):
        model.__table__.create(engine)
    with Session(engine) as db:
        db.add(Loja(loja_id=1, organizacao_id=1, nmloja='Loja'))
        db.add_all([Cliente(cliente_id=i, nmcliente=f'Cliente {i}', emailcliente=f'{i}@teste.com', senhahashcli='hash', sitcliente='ATIVO') for i in (1, 2)])
        db.flush()
        db.query(Cliente).filter_by(cliente_id=2).one().recebe_push_promocoes = False
        db.add(CampanhaPromocional(id=1, loja_id=1, titulo='Oferta', mensagem='Olá', status='RASCUNHO'))
        db.add_all([DispositivoPromocao(cliente_id=i, token_hash=str(i), token=f'token{i}', plataforma='ios') for i in (1, 2)])
        db.commit()
        yield db
    engine.dispose()


def test_envia_apenas_para_dispositivo_com_consentimento_e_impede_duplicacao(db):
    usuario = {'role': 'usuario', 'sub': '2', 'organizacao_id': 1, 'dscargo': 'ADMIN'}
    background = BackgroundTasks()
    with patch('app.routers.campanhas_promocionais.verificar_configuracao_push'):
        resultado = enviar(1, EnvioIn(push=True), background, usuario, db)
        assert resultado['destinatarios'] == 1
        assert [e.cliente_id for e in db.query(EnvioCampanhaPromocional).all()] == [1]
        assert len(background.tasks) == 1
        with pytest.raises(HTTPException) as erro:
            enviar(1, EnvioIn(push=True), BackgroundTasks(), usuario, db)
        assert erro.value.status_code == 409


def test_nao_envia_quando_firebase_indisponivel(db):
    from app.services.envio_promocoes_service import CanalIndisponivel
    usuario = {'role': 'usuario', 'sub': '2', 'organizacao_id': 1, 'dscargo': 'ADMIN'}
    with patch('app.routers.campanhas_promocionais.verificar_configuracao_push', side_effect=CanalIndisponivel('Firebase indisponível')):
        with pytest.raises(HTTPException) as erro:
            enviar(1, EnvioIn(push=True), BackgroundTasks(), usuario, db)
    assert erro.value.status_code == 503
    assert db.query(EnvioCampanhaPromocional).count() == 0
    assert db.query(CampanhaPromocional).first().status == 'RASCUNHO'


def test_respeita_retirada_de_consentimento_antes_do_disparo(db):
    usuario = {'role': 'usuario', 'sub': '2', 'organizacao_id': 1, 'dscargo': 'ADMIN'}
    with patch('app.routers.campanhas_promocionais.verificar_configuracao_push'):
        enviar(1, EnvioIn(push=True), BackgroundTasks(), usuario, db)
    db.query(Cliente).filter_by(cliente_id=1).one().recebe_push_promocoes = False
    db.commit()
    with patch('app.routers.campanhas_promocionais.SessionLocal', side_effect=lambda: Session(db.get_bind())), patch('app.routers.campanhas_promocionais.enviar_push_promocional') as push:
        _processar_envios(1)
    db.expire_all()
    push.assert_not_called()
    assert db.query(EnvioCampanhaPromocional).one().status == 'IGNORADO'


def test_processa_envio_e_registra_aceite_do_provedor(db):
    usuario = {'role': 'usuario', 'sub': '2', 'organizacao_id': 1, 'dscargo': 'ADMIN'}
    with patch('app.routers.campanhas_promocionais.verificar_configuracao_push'):
        enviar(1, EnvioIn(push=True), BackgroundTasks(), usuario, db)
    with patch('app.routers.campanhas_promocionais.SessionLocal', side_effect=lambda: Session(db.get_bind())), patch('app.routers.campanhas_promocionais.enviar_push_promocional', return_value='mensagem') as push:
        _processar_envios(1)
    db.expire_all()
    push.assert_called_once_with(token_dispositivo='token1', titulo='Oferta', mensagem='Olá', plataforma='ios', envio_id=1, nome_loja='Loja')
    assert db.query(EnvioCampanhaPromocional).one().status == 'ENVIADO'
    assert db.query(CampanhaPromocional).one().status == 'CONCLUIDA'


def test_resultado_apresenta_destinatarios_e_canais(db):
    usuario = {'role': 'usuario', 'sub': '2', 'organizacao_id': 1, 'dscargo': 'ADMIN'}
    with patch('app.routers.campanhas_promocionais.verificar_configuracao_push'):
        enviar(1, EnvioIn(push=True, email=True, cliente_ids=[1]), BackgroundTasks(), usuario, db)
    dados = resultado(1, usuario, db)
    assert len(dados['destinatarios']) == 1
    assert dados['destinatarios'][0]['cliente_id'] == 1
    assert {e['canal'] for e in dados['destinatarios'][0]['envios']} == {'push', 'email'}
    with pytest.raises(HTTPException) as erro:
        resultado(1, {'role': 'usuario', 'sub': '2', 'organizacao_id': 2, 'dscargo': 'ADMIN'}, db)
    assert erro.value.status_code == 404


def test_notificacoes_e_cliques_sao_restritos_ao_cliente(db):
    parceiro = {'role': 'usuario', 'sub': '2', 'organizacao_id': 1, 'dscargo': 'ADMIN'}
    with patch('app.routers.campanhas_promocionais.verificar_configuracao_push'):
        enviar(1, EnvioIn(push=True, cliente_ids=[1]), BackgroundTasks(), parceiro, db)
    envio = db.query(EnvioCampanhaPromocional).one()
    envio.status = 'ENVIADO'
    db.commit()
    cliente = {'role': 'cliente', 'sub': '1'}
    assert len(listar_notificacoes(cliente, db)) == 1
    with pytest.raises(HTTPException):
        registrar_clique(envio.id, {'role': 'cliente', 'sub': '2'}, db)
    registrar_clique(envio.id, cliente, db)
    assert resultado(1, parceiro, db)['destinatarios'][0]['envios'][0]['clicado_em'] is not None


def test_email_link_registra_clique_e_redireciona(db, monkeypatch):
    from app.core.security import criar_jwt
    from app.services.envio_promocoes_service import enviar_email_promocional
    from datetime import timedelta
    from urllib.parse import parse_qs, urlsplit
    import re

    parceiro = {'role': 'usuario', 'sub': '2', 'organizacao_id': 1, 'dscargo': 'ADMIN'}
    enviar(1, EnvioIn(email=True, cliente_ids=[1]), BackgroundTasks(), parceiro, db)
    envio = db.query(EnvioCampanhaPromocional).one()
    enviados = []
    monkeypatch.setattr('app.services.envio_promocoes_service._enviar_email_smtp', lambda *args: enviados.append(args))
    enviar_email_promocional(destinatario='1@teste.com', titulo='Teste', mensagem='Acesse https://example.com/oferta.', envio_id=envio.id, nome_loja='Loja & Cia')
    assert 'Loja &amp; Cia' in enviados[0][2]
    link = re.search(r'href="([^"]*clique-email[^\"]*)"', enviados[0][2]).group(1)
    token = parse_qs(urlsplit(link).query)['token'][0]
    resposta = clique_email(token, db)
    assert resposta.headers['location'] == 'https://example.com/oferta'
    assert envio.clicado_em is not None
    invalido = criar_jwt({'tipo': 'campanha_email_clique', 'envio_id': envio.id, 'url': 'javascript:alert(1)'}, expires_delta=timedelta(days=1))
    with pytest.raises(HTTPException):
        clique_email(invalido, db)
