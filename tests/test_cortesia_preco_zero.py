from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import main  # Registra os modelos da aplicação.
import pytest
from app.routers.eventolotes import _dados_preco_catalogo
from app.routers.reservas_ingressos import _eh_cortesia
from app.services import reserva_ingresso_service as svc


def test_catalogo_forca_preco_zero_para_cortesia():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        modalidade_id=3, cdmodalidade='CORTESIA', permitepersonalizarnome=False,
        nmmodalidade='Cortesia', aplicacotalegal=False, exigecomprovante=False)
    preco = SimpleNamespace(modalidade_id=3, nmpreco='Cortesia', vrpreco=Decimal('3'),
        travarentradaaposlimite=False, qtlimitemodalidade=None, nrminutosaposinicio=None,
        situacao='ATIVO', nrordem=1)
    assert _dados_preco_catalogo(db, preco)['vrpreco'] == Decimal('0.00')


def test_preco_antigo_identificado_por_modalidade():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        tipopreco='CORTESIA', vrpreco=Decimal('3'))
    assert _eh_cortesia(db, 3)


def test_reserva_corrige_cortesia_antiga_e_nao_cobra_taxa(monkeypatch):
    db = MagicMock()
    preco = SimpleNamespace(lotepreco_id=3, modalidade_id=4, vrpreco=Decimal('3'), aplicacotalegal=False)
    lote = SimpleNamespace(lote_id=2, evento_id=10, loteglobal_id=11, situacao='ATIVO',
        lote_global=SimpleNamespace(situacao='ATIVO'), eventosetor_id=12, organizacao_id=1, loja_id=5)
    evento = SimpleNamespace(evento_id=10, statusevento='ATIVO')
    modalidade = SimpleNamespace(cdmodalidade='CORTESIA', exigebeneficio=False)
    setor = SimpleNamespace(eventosetor_id=12, sitsetor='ATIVO', qtcapacidade=20)
    loja = SimpleNamespace(vrtaxaing=10, vrtaxaminimaingresso=3)
    valores = {svc.EventoLote: lote, svc.EventoLotePreco: preco, svc.ModalidadeIngresso: modalidade,
               svc.Evento: evento, svc.EventoSetor: setor, svc.Loja: loja}
    def consulta(modelo):
        q = MagicMock()
        q.filter.return_value.first.return_value = valores.get(modelo)
        q.filter.return_value.with_for_update.return_value.first.return_value = valores.get(modelo)
        q.filter.return_value.scalar.return_value = 0
        return q
    db.query.side_effect = consulta
    monkeypatch.setattr(svc, 'expirar_reservas', lambda db: None)
    monkeypatch.setattr(svc, 'lote_global_ativo', lambda *args: SimpleNamespace(loteglobal_id=11))
    monkeypatch.setattr(svc, 'quantidade_disponivel_configuracao', lambda *args: 20)
    monkeypatch.setattr(svc, 'quantidade_disponivel_modalidade', lambda *args: None)
    monkeypatch.setattr(svc, '_fim_efetivo_evento', lambda *args: None)
    monkeypatch.setattr(svc, '_capacidade_evento', lambda *args: 20)
    monkeypatch.setattr(svc, 'capacidade_restante_setor', lambda *args: 20)
    reserva = svc.criar_reserva(db, cliente_id=7, lote_id=2, lotepreco_id=3,
        beneficio_id=None, tipo_beneficio=None, quantidade=1)
    assert preco.vrpreco == Decimal('0.00')
    assert reserva.vrunitario == reserva.vrtaxa == reserva.vrtotal == Decimal('0.00')
