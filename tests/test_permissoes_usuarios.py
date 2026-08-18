import unittest

from fastapi import HTTPException

from app.core.permissoes_loja import (
    validar_edicao_organizacao,
    validar_mutacao_loja,
)
from app.routers.usuarios import _validar_vinculo_cargo_loja


def payload(cargo: str, loja_id: int | None = None) -> dict:
    return {
        "role": "usuario",
        "dscargo": cargo,
        "organizacao_id": 10,
        "loja_id": loja_id,
    }


class PermissoesOrganizacaoTest(unittest.TestCase):
    def test_superadmin_pode_editar_organizacao(self):
        validar_edicao_organizacao(payload("SUPERADMIN"), 10)

    def test_admin_nao_pode_editar_organizacao(self):
        with self.assertRaises(HTTPException) as erro:
            validar_edicao_organizacao(payload("ADMIN"), 10)
        self.assertEqual(erro.exception.status_code, 403)

    def test_admin_pode_alterar_qualquer_loja_da_organizacao(self):
        validar_mutacao_loja(payload("ADMIN"), 10, 999)

    def test_gerente_so_pode_alterar_sua_loja(self):
        validar_mutacao_loja(payload("GERENTE", 20), 10, 20)
        with self.assertRaises(HTTPException) as erro:
            validar_mutacao_loja(payload("GERENTE", 20), 10, 21)
        self.assertEqual(erro.exception.status_code, 403)


class VinculoCargoLojaTest(unittest.TestCase):
    def test_cargos_globais_nao_podem_ter_loja(self):
        for cargo in ("SUPERADMIN", "ADMIN"):
            with self.subTest(cargo=cargo), self.assertRaises(HTTPException):
                _validar_vinculo_cargo_loja(cargo, 1)

    def test_cargos_operacionais_e_gerente_exigem_loja(self):
        for cargo in ("GERENTE", "CAIXA", "TOTEM", "BARMAN", "GARCOM", "PORTEIRO"):
            with self.subTest(cargo=cargo), self.assertRaises(HTTPException):
                _validar_vinculo_cargo_loja(cargo, None)
            _validar_vinculo_cargo_loja(cargo, 1)


if __name__ == "__main__":
    unittest.main()
