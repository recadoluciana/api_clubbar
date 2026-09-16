import inspect
import unittest
from fastapi import HTTPException

from app.models.leadparceiro import LeadParceiro
from app.models.leadestabelecimento import LeadEstabelecimento

from app.routers.leadparceiro import (
    CATEGORIAS_PADRAO,
    _senha_inicial_superadmin,
    _nomes_para_conversao,
    converter_lead_em_parceiro,
)


class ConversaoLeadParceiroTest(unittest.TestCase):
    def test_usa_nome_do_lead_para_organizacao_e_do_estabelecimento_para_loja(self):
        lead = LeadParceiro(nmorganizacao=" Grupo Binatto ")
        estabelecimento = LeadEstabelecimento(nmestabelecimento=" Angela Bar ")
        self.assertEqual(
            ("Grupo Binatto", "Angela Bar"),
            _nomes_para_conversao(lead, estabelecimento),
        )

    def test_rejeita_nome_de_organizacao_ausente_ou_longo(self):
        estabelecimento = LeadEstabelecimento(nmestabelecimento="Angela Bar")
        for nome in (None, "  ", "X" * 121):
            with self.subTest(nome=nome), self.assertRaises(HTTPException) as erro:
                _nomes_para_conversao(
                    LeadParceiro(nmorganizacao=nome), estabelecimento
                )
            self.assertEqual(422, erro.exception.status_code)

    def test_senha_usa_seis_digitos_e_seis_caracteres_do_responsavel(self):
        self.assertEqual(
            "123456Carlos",
            _senha_inicial_superadmin("12.345.678/0001-90", "Carlos da Silva"),
        )

    def test_nome_composto_ignora_espacos_na_senha(self):
        self.assertEqual(
            "987654AnaMar",
            _senha_inicial_superadmin("98.765.432/0001-10", "Ana Maria"),
        )

    def test_onboarding_possui_oito_categorias_ordenadas(self):
        self.assertEqual(8, len(CATEGORIAS_PADRAO))
        self.assertEqual("Cervejas", CATEGORIAS_PADRAO[0])
        self.assertIn("Combo", CATEGORIAS_PADRAO)
        self.assertEqual("Outros", CATEGORIAS_PADRAO[-1])
        self.assertEqual(8, len(set(CATEGORIAS_PADRAO)))

    def test_convite_e_enviado_somente_depois_do_commit(self):
        fonte = inspect.getsource(converter_lead_em_parceiro)

        self.assertLess(
            fonte.index("db.commit()"),
            fonte.index("enviar_convite_parceiro("),
        )
        self.assertNotIn("acesso_portal", fonte)
        self.assertNotIn("import traceback", fonte)

    def test_usuario_criado_com_nome_do_responsavel_pelo_lead(self):
        fonte = inspect.getsource(converter_lead_em_parceiro)

        self.assertIn("nmusuario=lead.nmresponsavel.strip()", fonte)
        self.assertNotIn('nmusuario=f"SUPERADMIN', fonte)


if __name__ == "__main__":
    unittest.main()
