import unittest
from datetime import datetime

from app.utils.datetime_utils import formatar_data_br, iso_utc


class DateTimeUtilsTest(unittest.TestCase):
    def test_data_utc_do_banco_e_exibida_no_fuso_brasileiro(self):
        self.assertEqual(formatar_data_br(datetime(2026, 8, 23, 5, 0)), "23/08/2026 02:00")

    def test_datetime_ingenuo_do_banco_e_serializado_como_utc(self):
        self.assertEqual(iso_utc(datetime(2026, 8, 23, 5, 0)), "2026-08-23T05:00:00Z")


if __name__ == "__main__":
    unittest.main()
