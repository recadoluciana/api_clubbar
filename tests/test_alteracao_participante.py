import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.routers.entregas import (
    validar_elegibilidade_alteracao_participante_itvenda,
)


class AlteracaoParticipanteTest(unittest.TestCase):
    def _db_para_ingresso(self, transferencias_realizadas=0):
        db = MagicMock()
        consulta_ingresso = MagicMock()
        consulta_historico = MagicMock()
        consulta_ingresso.join.return_value = consulta_ingresso
        consulta_ingresso.outerjoin.return_value = consulta_ingresso
        consulta_ingresso.filter.return_value = consulta_ingresso
        consulta_historico.filter.return_value = consulta_historico
        consulta_historico.scalar.return_value = transferencias_realizadas
        db.query.side_effect = [consulta_ingresso, consulta_historico]

        item = SimpleNamespace(
            itvenda_id=31,
            tipoitem="INGRESSO",
            sititvenda="ATIVO",
            identregaitvenda="NAO",
        )
        venda = SimpleNamespace(cliente_id=8)
        evento = SimpleNamespace(
            dtinicioevento=datetime.now() + timedelta(days=3),
        )
        preco = SimpleNamespace(tipopreco="MEIA_ENTRADA")
        consulta_ingresso.first.return_value = (item, venda, evento, preco)
        return db

    @patch("app.routers.entregas._politica_vigente")
    def test_valida_elegibilidade_antes_da_edicao(self, politica_vigente):
        politica_vigente.return_value = SimpleNamespace(
            qtd_horas_antecedencia_alteracao=24,
            qtd_alteracoes_participante=1,
        )

        resultado = validar_elegibilidade_alteracao_participante_itvenda(
            31,
            usuario={"role": "cliente", "sub": "8"},
            db=self._db_para_ingresso(),
        )

        self.assertTrue(resultado["elegivel"])
        self.assertEqual(0, resultado["alteracoes_realizadas"])
        self.assertEqual(1, resultado["limite_alteracoes"])
        self.assertTrue(resultado["eh_meia_entrada"])

    @patch("app.routers.entregas._politica_vigente")
    def test_impede_abertura_quando_limite_ja_foi_atingido(self, politica_vigente):
        politica_vigente.return_value = SimpleNamespace(
            qtd_horas_antecedencia_alteracao=24,
            qtd_alteracoes_participante=1,
        )

        with self.assertRaises(HTTPException) as erro:
            validar_elegibilidade_alteracao_participante_itvenda(
                31,
                usuario={"role": "cliente", "sub": "8"},
                db=self._db_para_ingresso(transferencias_realizadas=1),
            )

        self.assertEqual(409, erro.exception.status_code)
        self.assertIn("já atingiu o limite", erro.exception.detail)


if __name__ == "__main__":
    unittest.main()
