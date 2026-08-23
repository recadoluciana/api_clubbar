import unittest
from datetime import date, datetime

from app.routers.superadmin import _limites_data_utc


class SuperadminVendasDataTest(unittest.TestCase):
    def test_data_local_e_convertida_para_intervalo_utc(self):
        inicio, fim = _limites_data_utc(date(2026, 8, 22))

        self.assertEqual(datetime(2026, 8, 22, 3), inicio)
        self.assertEqual(datetime(2026, 8, 23, 3), fim)


if __name__ == '__main__':
    unittest.main()
