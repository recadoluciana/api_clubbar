import unittest

from fastapi import HTTPException

from app.routers.entregas import _validar_cargo_leitura_qr


class PermissoesQrCodeTest(unittest.TestCase):
    def test_barman_e_garcom_podem_baixar_produto(self):
        for cargo in ("BARMAN", "GARCOM"):
            with self.subTest(cargo=cargo):
                _validar_cargo_leitura_qr(cargo, "P")

    def test_porteiro_nao_pode_baixar_produto(self):
        with self.assertRaises(HTTPException) as erro:
            _validar_cargo_leitura_qr("PORTEIRO", "P")
        self.assertEqual(erro.exception.status_code, 403)

    def test_porteiro_pode_baixar_ingresso(self):
        _validar_cargo_leitura_qr("PORTEIRO", "I")

    def test_barman_e_garcom_nao_podem_baixar_ingresso(self):
        for cargo in ("BARMAN", "GARCOM"):
            with self.subTest(cargo=cargo), self.assertRaises(HTTPException):
                _validar_cargo_leitura_qr(cargo, "I")


if __name__ == "__main__":
    unittest.main()
