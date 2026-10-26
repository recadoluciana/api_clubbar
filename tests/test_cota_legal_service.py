import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from app.services.cota_legal_service import cota_legal_total, cotas_legais_por_setor


class CotaLegalServiceTest(unittest.TestCase):
    def _db_com_setores(self, setores):
        query = Mock()
        query.filter.return_value.order_by.return_value.all.return_value = setores
        db = Mock()
        db.query.return_value = query
        return db

    def test_cota_total_arredonda_para_cima_para_preservar_o_percentual_legal(self):
        self.assertEqual(cota_legal_total(18, 40), 8)

    def test_distribui_cota_proporcionalmente_e_preserva_total_do_evento(self):
        db = self._db_com_setores(
            [
                SimpleNamespace(eventosetor_id=1, qtcapacidade=15),
                SimpleNamespace(eventosetor_id=2, qtcapacidade=3),
            ]
        )

        cotas = cotas_legais_por_setor(db, evento_id=10, percentual=40)

        self.assertEqual({1: 6, 2: 2}, cotas)
        self.assertEqual(8, sum(cotas.values()))

    def test_desempate_do_maior_resto_e_deterministico_por_setor(self):
        db = self._db_com_setores(
            [
                SimpleNamespace(eventosetor_id=8, qtcapacidade=1),
                SimpleNamespace(eventosetor_id=3, qtcapacidade=1),
            ]
        )

        self.assertEqual({8: 0, 3: 1}, cotas_legais_por_setor(db, 10, 40))


if __name__ == "__main__":
    unittest.main()
