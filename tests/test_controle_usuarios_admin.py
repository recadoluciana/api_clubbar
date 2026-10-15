import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.routers.superadmin import (
    _ALFABETO_SENHA_TEMPORARIA,
    _gerar_senha_temporaria,
    resetar_senha_usuario,
)


class _ConsultaUsuario:
    def __init__(self, usuario):
        self.usuario = usuario

    def filter(self, *args):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.usuario


class _BancoFake:
    def __init__(self, usuario):
        self.usuario = usuario
        self.commitado = False

    def query(self, modelo):
        return _ConsultaUsuario(self.usuario)

    def commit(self):
        self.commitado = True


class ControleUsuariosAdminTest(unittest.TestCase):
    def test_senha_temporaria_tem_tamanho_e_caracteres_seguros(self):
        senha = _gerar_senha_temporaria()

        self.assertEqual(len(senha), 10)
        self.assertTrue(all(caractere in _ALFABETO_SENHA_TEMPORARIA for caractere in senha))

    def test_resetar_senha_atualiza_hash_e_retorna_senha_somente_na_resposta(self):
        usuario = SimpleNamespace(
            usuario_id=27,
            nmusuario="Usuária de teste",
            emailuser="teste@clubbar.com.br",
            senhahashuser="hash-antigo",
        )
        banco = _BancoFake(usuario)

        with patch("app.routers.superadmin._gerar_senha_temporaria", return_value="NovaSenha2"), patch(
            "app.routers.superadmin.hash_senha", side_effect=lambda senha: f"hash:{senha}"
        ) as hash_mock:
            resposta = resetar_senha_usuario(27, {}, banco)

        self.assertTrue(banco.commitado)
        self.assertEqual(usuario.senhahashuser, "hash:NovaSenha2")
        hash_mock.assert_called_once_with("NovaSenha2")
        self.assertEqual(resposta["senha_temporaria"], "NovaSenha2")
        self.assertEqual(resposta["usuario_id"], 27)


if __name__ == "__main__":
    unittest.main()
