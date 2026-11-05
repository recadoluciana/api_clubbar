import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.routers.portalparceiro import atualizar_estabelecimento_portal
from app.schemas.portalparceiro import PortalEstabelecimentoUpdate


def dados(**extra):
    return PortalEstabelecimentoUpdate(tipo='PRODUTOR_EVENTOS', tipovenda='AMBOS',
        estado_id=1, cidade_id=2, cep='37185000', endereco='Rua A', numero='1', bairro='Centro', **extra)


class EdicaoPortalTest(unittest.TestCase):
    def executar(self, update, assinado=False):
        item = SimpleNamespace(leadestabelecimento_id=3, nmestabelecimento='Nome antigo', email_responsavel='antigo@example.com')
        lead = SimpleNamespace(leadparceiro_id=1)
        loja_query, contrato_query, cidade_query = MagicMock(), MagicMock(), MagicMock()
        loja_query.filter.return_value.first.return_value = item
        contrato_query.filter.return_value.first.return_value = (10,) if assinado else None
        cidade_query.filter.return_value.first.return_value = SimpleNamespace(estado_id=1)
        db = MagicMock()
        db.query.side_effect = [loja_query, contrato_query, cidade_query]
        db.get.return_value = SimpleNamespace(estado_id=1)
        with patch('app.routers.portalparceiro.validar_cep_lead'), patch('app.routers.portalparceiro.atualizar_contrato_pendente') as contrato:
            try:
                atualizar_estabelecimento_portal(3, update, lead=lead, db=db)
            except HTTPException:
                self.assertTrue(assinado)
                db.commit.assert_not_called()
                raise
            contrato.assert_called_once_with(db, item)
        return item

    def test_salva_nome_e_email_da_unidade(self):
        item = self.executar(dados(nmestabelecimento='  Nova Produtora  ', email_responsavel='novo@example.com'))
        self.assertEqual(item.nmestabelecimento, 'Nova Produtora')
        self.assertEqual(item.email_responsavel, 'novo@example.com')

    def test_campos_omitidos_preservam_valores(self):
        item = self.executar(dados())
        self.assertEqual(item.nmestabelecimento, 'Nome antigo')
        self.assertEqual(item.email_responsavel, 'antigo@example.com')

    def test_contrato_assinado_impede_alteracao(self):
        with self.assertRaises(HTTPException) as erro:
            self.executar(dados(nmestabelecimento='Nova Produtora'), assinado=True)
        self.assertEqual(erro.exception.status_code, 409)

    def test_valida_email_e_nome(self):
        with self.assertRaises(ValidationError):
            dados(email_responsavel='email-invalido')
        with self.assertRaises(ValidationError):
            dados(nmestabelecimento='   ')


if __name__ == '__main__':
    unittest.main()
