from types import SimpleNamespace
import unittest

from fastapi import HTTPException

from app.schemas.auth import ClienteRegister
from app.services.asaas_service import validar_endereco_cobranca_para_cartao


class EnderecoPagamentoTest(unittest.TestCase):
    def test_cadastro_cliente_aceita_endereco_ausente(self):
        cliente = ClienteRegister(
            nmcliente="Cliente Teste",
            emailcliente="cliente@teste.com",
            senhahashcli="senha-segura",
            nrcpfcliente="52998224725",
        )

        self.assertIsNone(cliente.endcliente)
        self.assertIsNone(cliente.cepcliente)

    def test_cartao_exige_endereco_completo(self):
        cliente = SimpleNamespace(
            endcliente=None,
            nrendcliente=None,
            bairrocliente=None,
            cidadecliente=None,
            ufcliente=None,
            cepcliente=None,
        )

        with self.assertRaises(HTTPException) as erro:
            validar_endereco_cobranca_para_cartao(cliente)

        self.assertEqual(erro.exception.status_code, 422)

    def test_cartao_aceita_endereco_completo(self):
        cliente = SimpleNamespace(
            endcliente="Rua das Flores",
            nrendcliente="123",
            bairrocliente="Centro",
            cidadecliente="Três Pontas",
            ufcliente="MG",
            cepcliente="37190000",
        )

        validar_endereco_cobranca_para_cartao(cliente)


if __name__ == "__main__":
    unittest.main()
