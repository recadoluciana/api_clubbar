import inspect
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from app.routers.eventolotes import listar_lotes_evento
from app.services.reserva_ingresso_service import lote_atual_do_setor


class ConsultaLotesFalsa:
    def __init__(self, lotes):
        self.lotes = lotes

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return self.lotes


class BancoLotesFalso:
    def __init__(self, lotes):
        self.lotes = lotes

    def query(self, *args):
        return ConsultaLotesFalsa(self.lotes)


def criar_lote(numero, inicio, fim, *, vendidos=0, total=100, status="ATIVO"):
    return SimpleNamespace(
        lote_id=numero,
        evento_id=10,
        eventosetor_id=20,
        nrlote=numero,
        dtiniciovenda=inicio,
        dtfimvenda=fim,
        qtvendidalote=vendidos,
        qttotallote=total,
        statuslote=status,
    )


class LotesPublicosTest(unittest.TestCase):
    def test_listagem_de_lotes_ativos_nao_exige_usuario(self):
        parametros = inspect.signature(listar_lotes_evento).parameters

        self.assertNotIn("usuario", parametros)
        self.assertEqual({"evento_id", "db"}, set(parametros))

    @patch(
        "app.services.reserva_ingresso_service.quantidade_reservada",
        return_value=0,
    )
    def test_lote_anterior_continua_vigente_quando_periodos_se_sobrepoem(
        self, _quantidade_reservada
    ):
        agora = datetime(2026, 9, 18, 5, 0)
        lote_1 = criar_lote(
            1,
            agora - timedelta(hours=4),
            agora + timedelta(hours=19),
        )
        lote_2 = criar_lote(
            2,
            agora - timedelta(hours=2),
            agora + timedelta(hours=17),
        )
        banco = BancoLotesFalso([lote_1, lote_2])

        atual = lote_atual_do_setor(banco, lote_2, agora)

        self.assertIs(lote_1, atual)

    @patch(
        "app.services.reserva_ingresso_service.quantidade_reservada",
        return_value=0,
    )
    def test_proximo_lote_assume_quando_anterior_encerra(
        self, _quantidade_reservada
    ):
        agora = datetime(2026, 9, 18, 5, 0)
        lote_1 = criar_lote(
            1,
            agora - timedelta(days=1),
            agora - timedelta(minutes=1),
        )
        lote_2 = criar_lote(
            2,
            agora + timedelta(days=1),
            agora + timedelta(days=2),
        )
        banco = BancoLotesFalso([lote_1, lote_2])

        atual = lote_atual_do_setor(banco, lote_1, agora)

        self.assertIs(lote_2, atual)


if __name__ == "__main__":
    unittest.main()
