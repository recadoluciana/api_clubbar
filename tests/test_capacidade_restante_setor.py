import unittest
from unittest.mock import Mock

from app.services.reserva_ingresso_service import capacidade_restante_setor


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


if __name__ == '__main__':
    unittest.main()
