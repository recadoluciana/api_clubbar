import unittest
from unittest.mock import Mock

from app.services.reserva_ingresso_service import (
    capacidade_restante_setor,
    quantidade_disponivel_configuracao,
)


class CapacidadeRestanteSetorTest(unittest.TestCase):
    def _db(self, vendidos: int, reservados: int):
        query_vendas = Mock()
        query_vendas.filter.return_value.scalar.return_value = vendidos
        query_reservas = Mock()
        query_reservas.join.return_value.filter.return_value.scalar.return_value = reservados
        db = Mock()
        db.query.side_effect = [query_vendas, query_reservas]
        return db

    def test_desconta_vendas_e_reservas_ativas(self):
        self.assertEqual(capacidade_restante_setor(self._db(3, 2), 1, 1, 15), 10)

    def test_nunca_exibe_capacidade_negativa(self):
        self.assertEqual(capacidade_restante_setor(self._db(12, 4), 1, 1, 15), 0)

    def test_lote_posterior_reutiliza_estoque_restante_do_setor(self):
        reserva_do_lote = Mock()
        reserva_do_lote.filter.return_value.scalar.return_value = 0
        vendas_do_setor = Mock()
        vendas_do_setor.filter.return_value.scalar.return_value = 2
        reservas_do_setor = Mock()
        reservas_do_setor.join.return_value.filter.return_value.scalar.return_value = 0
        db = Mock()
        db.query.side_effect = [vendas_do_setor, reservas_do_setor, reserva_do_lote]

        lote = Mock(qtlimite=5, qtvendidalote=0, lote_id=10, evento_id=1)
        lote.setor = Mock(eventosetor_id=2, qtcapacidade=3)

        self.assertEqual(quantidade_disponivel_configuracao(db, lote), 1)


if __name__ == '__main__':
    unittest.main()
