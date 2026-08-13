import unittest
from types import SimpleNamespace

from app.routers.asaas_webhook import atualizar_cliente_com_customer_asaas


class QueryFalsa:
    def __init__(self, resultado=None):
        self.resultado = resultado

    def filter(self, *args):
        return self

    def first(self):
        return self.resultado


class BancoFalso:
    def __init__(self, cpf_em_uso=None):
        self.cpf_em_uso = cpf_em_uso

    def query(self, *args):
        return QueryFalsa(self.cpf_em_uso)


def cliente(**kwargs):
    valores = {
        "cliente_id": 1,
        "cliente_padrao": "N",
        "nrcpfcliente": None,
        "nrtelcliente": None,
        "endcliente": None,
        "nrendcliente": None,
        "complcliente": None,
        "bairrocliente": None,
        "cepcliente": None,
        "cidadecliente": None,
        "ufcliente": None,
    }
    valores.update(kwargs)
    return SimpleNamespace(**valores)


class AtualizarClienteAsaasTest(unittest.TestCase):
    def test_cliente_padrao_nao_recebe_dados_pessoais_do_pagador(self):
        registro = cliente(cliente_padrao="S")
        atualizar_cliente_com_customer_asaas(
            BancoFalso(),
            registro,
            {"cpfCnpj": "294.197.818-60", "mobilePhone": "35999999999"},
        )
        self.assertIsNone(registro.nrcpfcliente)
        self.assertIsNone(registro.nrtelcliente)

    def test_cpf_ja_usado_nao_sobrescreve_cliente(self):
        registro = cliente(nrcpfcliente="11111111111")
        atualizar_cliente_com_customer_asaas(
            BancoFalso(cpf_em_uso=(99,)),
            registro,
            {"cpfCnpj": "294.197.818-60", "mobilePhone": "35999999999"},
        )
        self.assertEqual("11111111111", registro.nrcpfcliente)
        self.assertEqual("35999999999", registro.nrtelcliente)

    def test_cpf_livre_e_normalizado_antes_de_salvar(self):
        registro = cliente()
        atualizar_cliente_com_customer_asaas(
            BancoFalso(),
            registro,
            {"cpfCnpj": "294.197.818-60"},
        )
        self.assertEqual("29419781860", registro.nrcpfcliente)


if __name__ == "__main__":
    unittest.main()
