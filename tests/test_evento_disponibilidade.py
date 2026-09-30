import unittest
from datetime import datetime
from types import SimpleNamespace

from fastapi import HTTPException

from app.services.evento_disponibilidade_service import (
    validar_evento_unico_por_loja_data_local,
)


class _ConsultaFalsa:
    def __init__(self, resultado):
        self.resultado = resultado
        self.filtros = []

    def filter(self, *filtros):
        self.filtros.extend(filtros)
        return self

    def first(self):
        return self.resultado


class _BancoFalso:
    def __init__(self, resultado):
        self.consulta = _ConsultaFalsa(resultado)

    def query(self, *_):
        return self.consulta


class EventoDisponibilidadeTest(unittest.TestCase):
    def test_permite_quando_nao_existe_evento_no_mesmo_local(self):
        banco = _BancoFalso(None)

        validar_evento_unico_por_loja_data_local(
            banco,
            loja_id=3,
            inicio=datetime(2026, 10, 11, 20),
            local="Salão Principal",
        )

        self.assertEqual(len(banco.consulta.filtros), 4)

    def test_rejeita_evento_existente_na_mesma_data_e_local(self):
        banco = _BancoFalso(SimpleNamespace(nmtituloevento="Forró do X"))

        with self.assertRaises(HTTPException) as erro:
            validar_evento_unico_por_loja_data_local(
                banco,
                loja_id=3,
                inicio=datetime(2026, 10, 11, 20),
                local="Salão Principal",
            )

        self.assertEqual(erro.exception.status_code, 409)
        self.assertIn("Forró do X", erro.exception.detail)
        self.assertIn("11/10/2026", erro.exception.detail)

    def test_ignora_o_proprio_evento_ao_validar_edicao(self):
        banco = _BancoFalso(None)

        validar_evento_unico_por_loja_data_local(
            banco,
            loja_id=3,
            inicio=datetime(2026, 10, 11, 20),
            local="Salão Principal",
            ignorar_evento_id=7,
        )

        self.assertEqual(len(banco.consulta.filtros), 5)


if __name__ == "__main__":
    unittest.main()
