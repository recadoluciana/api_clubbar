import unittest
from datetime import datetime, timezone

from app.utils.datetime_utils import formatar_data_br, iso_utc, iso_utc_de_horario_brasil


class DateTimeUtilsTest(unittest.TestCase):
    def test_data_utc_do_banco_e_exibida_no_fuso_brasileiro(self):
        self.assertEqual(formatar_data_br(datetime(2026, 8, 23, 5, 0)), "23/08/2026 02:00")

    def test_datetime_ingenuo_do_banco_e_serializado_como_utc(self):
        self.assertEqual(iso_utc(datetime(2026, 8, 23, 5, 0)), "2026-08-23T05:00:00Z")

    def test_horario_de_entrega_em_brasilia_e_serializado_como_instante_utc(self):
        despacho = datetime(2026, 11, 4, 21, 20)
        serializado = iso_utc_de_horario_brasil(despacho)
        self.assertEqual(serializado, "2026-11-05T00:20:00Z")
        self.assertEqual(formatar_data_br(serializado), "04/11/2026 21:20")
        self.assertIsNone(iso_utc_de_horario_brasil(None))
        self.assertEqual(
            iso_utc_de_horario_brasil(datetime(2026, 11, 5, 0, 20, tzinfo=timezone.utc)),
            "2026-11-05T00:20:00Z",
        )


if __name__ == "__main__":
    unittest.main()
