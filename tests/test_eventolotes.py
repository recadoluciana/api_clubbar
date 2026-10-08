import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from pydantic import ValidationError
from fastapi import HTTPException

from app.models.eventolote import EventoLote
from app.models.eventoloteglobal import EventoLoteGlobal
from app.models.eventolotepreco import EventoLotePreco
from app.routers.eventolotes import _validar_data_limite_evento, _validar_setores_do_lote
from app.schemas.eventolote import EventoLoteGlobalCreate, EventoLotePrecoIn, EventoLoteSetorIn


class ModeloLoteGlobalTest(unittest.TestCase):
    def test_tabelas_fisicas_nao_usam_o_modelo_legado(self):
        self.assertEqual("eventoloteglobal", EventoLoteGlobal.__tablename__)
        self.assertEqual("eventolotesetor", EventoLote.__tablename__)
        self.assertEqual("eventolotesetorpreco", EventoLotePreco.__tablename__)

    def test_o_mesmo_tipo_de_preco_nao_pode_repetir_no_setor(self):
        with self.assertRaises(ValidationError):
            EventoLoteSetorIn(
                eventosetor_id=1,
                qtlimite=50,
                precos=[
                    EventoLotePrecoIn(nmpreco="Inteira", tipopreco="INTEIRA", vrpreco=50),
                    EventoLotePrecoIn(nmpreco="Inteira promocional", tipopreco="INTEIRA", vrpreco=40),
                ],
            )

    def test_setor_precisa_ter_quantidade_definida_no_lote(self):
        with self.assertRaises(ValidationError):
            EventoLoteSetorIn(
                eventosetor_id=1,
                precos=[
                    EventoLotePrecoIn(
                        nmpreco="Inteira",
                        tipopreco="INTEIRA",
                        vrpreco=50,
                    ),
                ],
            )

    def test_fim_da_venda_nao_pode_vir_antes_do_inicio(self):
        with self.assertRaises(ValidationError):
            EventoLoteGlobalCreate(
                organizacao_id=1,
                loja_id=1,
                dtiniciovenda=datetime(2026, 8, 1, 10, 0),
                dtfimvenda=datetime(2026, 8, 1, 9, 59),
                setores=[
                    EventoLoteSetorIn(
                        eventosetor_id=1,
                        qtlimite=50,
                        precos=[
                            EventoLotePrecoIn(nmpreco="Inteira", tipopreco="INTEIRA", vrpreco=50),
                        ],
                    )
                ],
            )

    def test_lote_global_pode_incluir_apenas_alguns_setores(self):
        db = MagicMock()
        db.query().filter().all.return_value = [
            SimpleNamespace(eventosetor_id=1, nmsetor="Pista", qtcapacidade=100),
            SimpleNamespace(eventosetor_id=2, nmsetor="Camarote", qtcapacidade=30),
        ]
        evento = SimpleNamespace(evento_id=10)
        configuracoes = [SimpleNamespace(eventosetor_id=1, qtlimite=80)]

        _validar_setores_do_lote(
            db,
            evento=evento,
            configuracoes=configuracoes,
        )

    def test_data_limite_pode_ser_igual_ao_inicio_do_evento(self):
        inicio = datetime(2026, 10, 3, 20, 0)
        _validar_data_limite_evento(
            SimpleNamespace(dtinicioevento=inicio),
            inicio,
        )

    def test_data_limite_nao_pode_ultrapassar_inicio_do_evento(self):
        inicio = datetime(2026, 10, 3, 20, 0)
        with self.assertRaises(HTTPException) as erro:
            _validar_data_limite_evento(
                SimpleNamespace(dtinicioevento=inicio),
                datetime(2026, 10, 3, 20, 1),
            )
        self.assertEqual(422, erro.exception.status_code)


if __name__ == "__main__":
    unittest.main()
