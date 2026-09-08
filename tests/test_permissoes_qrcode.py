import unittest

from fastapi import HTTPException

from app.routers.entregas import _validar_cargo_leitura_qr


class PermissoesQrCodeTest(unittest.TestCase):
    def test_barman_e_waiter_podem_baixar_produto(self):
        for cargo in ("BARMAN", "WAITER"):
            with self.subTest(cargo=cargo):
                _validar_cargo_leitura_qr(cargo, "P")

    def test_ticketman_nao_pode_baixar_produto(self):
        with self.assertRaises(HTTPException) as erro:
            _validar_cargo_leitura_qr("TICKETMAN", "P")
        self.assertEqual(erro.exception.status_code, 403)

    def test_ticketman_pode_baixar_ingresso(self):
        _validar_cargo_leitura_qr("TICKETMAN", "I")

    def test_barman_e_waiter_nao_podem_baixar_ingresso(self):
        for cargo in ("BARMAN", "WAITER"):
            with self.subTest(cargo=cargo), self.assertRaises(HTTPException):
                _validar_cargo_leitura_qr(cargo, "I")


if __name__ == "__main__":
    unittest.main()
