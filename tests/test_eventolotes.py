import unittest
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException

from app.routers.eventolotes import _validar_programacao_vendas, atualizar_lote_evento
from app.schemas.eventolote import EventoLoteUpdate


class QueryFalsa:
    def __init__(self, resultado):
        self.resultado = resultado

    def filter(self, *args):
        return self

    def first(self):
        return self.resultado

    def all(self):
        return self.resultado


class BancoFalso:
    def __init__(self, resultados, falhar_commit=False):
        self.resultados = iter(resultados)
        self.falhar_commit = falhar_commit
        self.commits = 0
        self.rollbacks = 0
        self.refreshes = 0

    def query(self, *args):
        return QueryFalsa(next(self.resultados))

    def commit(self):
        self.commits += 1
        if self.falhar_commit:
            raise RuntimeError("falha simulada no commit")

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, obj):
        self.refreshes += 1


class Registro:
    pass


def criar_lote():
    lote = Registro()
    lote.lote_id = 5
    lote.organizacao_id = 1
    lote.loja_id = 2
    lote.evento_id = 3
    lote.nmlote = "Primeiro lote"
    lote.eventosetor_id = 10
    lote.qttotallote = 100
    lote.qtvendidalote = 0
    lote.dtiniciovenda = None
    lote.dtfimvenda = None
    lote.statuslote = "ATIVO"
    lote.dtcriacao = datetime(2026, 8, 1)
    lote.dtultatu = None
    return lote


class AtualizarLoteTest(unittest.TestCase):
    usuario = {
        "role": "usuario",
        "dscargo": "ADMIN",
        "organizacao_id": 1,
        "loja_id": 2,
    }

    def test_status_do_estoque_compartilhado_pode_ser_atualizado(self):
        lote = criar_lote()
        produto = Registro()
        produto.lote_id = 5
        produto.vrprecoprod = Decimal("50.00")
        banco = BancoFalso([lote, [produto]])

        resposta = atualizar_lote_evento(
            lote_id=5,
            data=EventoLoteUpdate(statuslote="INATIVO"),
            db=banco,
            usuario=self.usuario,
        )

        self.assertEqual("INATIVO", lote.statuslote)
        self.assertEqual(Decimal("50.00"), produto.vrprecoprod)
        self.assertEqual(1, banco.commits)
        self.assertEqual(0, banco.rollbacks)
        self.assertEqual("INATIVO", resposta["lote"]["statuslote"])

    def test_erro_no_commit_faz_rollback_da_operacao_completa(self):
        lote = criar_lote()
        produto = Registro()
        produto.lote_id = 5
        produto.vrprecoprod = Decimal("50.00")
        banco = BancoFalso([lote, [produto]], falhar_commit=True)

        with self.assertRaises(HTTPException) as erro:
            atualizar_lote_evento(
                lote_id=5,
                data=EventoLoteUpdate(statuslote="INATIVO"),
                db=banco,
                usuario=self.usuario,
            )

        self.assertEqual(500, erro.exception.status_code)
        self.assertEqual(1, banco.commits)
        self.assertEqual(1, banco.rollbacks)

    def test_nome_do_lote_pode_ser_atualizado(self):
        lote = criar_lote()
        banco = BancoFalso([lote, []])

        atualizar_lote_evento(
            lote_id=5,
            data=EventoLoteUpdate(nmlote="Lote 2 - Pista"),
            db=banco,
            usuario=self.usuario,
        )

        self.assertEqual("Lote 2 - Pista", lote.nmlote)
        self.assertEqual(1, banco.commits)


class ProgramacaoDeVendasTest(unittest.TestCase):
    def _evento(self):
        evento = Registro()
        evento.evento_id = 3
        evento.dtinicioevento = datetime(2026, 10, 1, 20, 0)
        return evento

    def _setor(self):
        setor = Registro()
        setor.eventosetor_id = 10
        return setor

    def _lote_anterior(self):
        lote = Registro()
        lote.lote_id = 5
        lote.nrlote = 1
        lote.dtiniciovenda = datetime(2026, 9, 21, 18, 0)
        lote.dtfimvenda = datetime(2026, 9, 25, 15, 10)
        return lote

    def test_proximo_lote_inicia_um_minuto_apos_o_anterior(self):
        banco = BancoFalso([[self._lote_anterior()]])

        _validar_programacao_vendas(
            banco,
            evento=self._evento(),
            setor=self._setor(),
            nrlote=2,
            dtinicio=datetime(2026, 9, 25, 15, 11),
            dtfim=datetime(2026, 10, 1, 19, 59),
        )

    def test_proximo_lote_nao_pode_deixar_intervalo_sem_venda(self):
        banco = BancoFalso([[self._lote_anterior()]])

        with self.assertRaises(HTTPException) as erro:
            _validar_programacao_vendas(
                banco,
                evento=self._evento(),
                setor=self._setor(),
                nrlote=2,
                dtinicio=datetime(2026, 9, 25, 15, 12),
                dtfim=datetime(2026, 10, 1, 19, 59),
            )

        self.assertEqual(422, erro.exception.status_code)


if __name__ == "__main__":
    unittest.main()
