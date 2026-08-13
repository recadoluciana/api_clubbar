import unittest

import main  # Carrega todos os modelos e relacionamentos SQLAlchemy.
from types import SimpleNamespace

from app.routers.asaas_webhook import (
    atualizar_cliente_com_customer_asaas,
    registrar_pagador_asaas,
)


class QueryFalsa:
    def __init__(self, resultado=None):
        self.resultado = resultado

    def filter(self, *args):
        return self

    def first(self):
        return self.resultado


class BancoPagadorFalso:
    def __init__(self, resultado=None):
        self.resultado = resultado
        self.adicionados = []

    def query(self, *args):
        return QueryFalsa(self.resultado)

    def add(self, item):
        self.adicionados.append(item)


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

    def test_pagador_e_criado_por_checkout(self):
        banco = BancoPagadorFalso()
        checkout = SimpleNamespace(checkout_asaas_id=15, venda_id=10)
        pagador = registrar_pagador_asaas(
            banco,
            checkout,
            {
                "id": "cus_123",
                "name": "Pessoa Pagadora",
                "cpfCnpj": "294.197.818-60",
                "email": "pagador@example.com",
            },
            "pay_123",
        )
        self.assertEqual(1, len(banco.adicionados))
        self.assertEqual(15, pagador.checkout_asaas_id)
        self.assertEqual(10, pagador.venda_id)
        self.assertEqual("29419781860", pagador.cpf_cnpj)
        self.assertEqual("pay_123", pagador.payment_id)

    def test_reenvio_atualiza_pagador_sem_duplicar(self):
        existente = SimpleNamespace(
            checkout_asaas_id=15,
            venda_id=None,
            payment_id=None,
            asaas_customer_id=None,
            nome=None,
            cpf_cnpj=None,
            email=None,
            telefone=None,
            endereco=None,
            numero=None,
            complemento=None,
            bairro=None,
            cep=None,
            cidade=None,
            uf=None,
        )
        banco = BancoPagadorFalso(existente)
        checkout = SimpleNamespace(checkout_asaas_id=15, venda_id=10)
        pagador = registrar_pagador_asaas(
            banco, checkout, {"id": "cus_123", "name": "Pagador"}, "pay_123"
        )
        self.assertEqual([], banco.adicionados)
        self.assertIs(existente, pagador)
        self.assertEqual(10, pagador.venda_id)
        self.assertEqual("Pagador", pagador.nome)
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
