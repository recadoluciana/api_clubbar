import unittest
from datetime import date, datetime

from app.routers.superadmin import _limites_data_brasilia


class SuperadminVendasDataTest(unittest.TestCase):
    def test_data_local_usa_intervalo_de_brasilia(self):
        inicio, fim = _limites_data_brasilia(date(2026, 8, 22))

        self.assertEqual(datetime(2026, 8, 22, 0), inicio)
        self.assertEqual(datetime(2026, 8, 23, 0), fim)


if __name__ == '__main__':
    unittest.main()
