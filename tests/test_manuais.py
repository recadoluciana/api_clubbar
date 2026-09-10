import unittest
from unittest.mock import patch
from copy import deepcopy
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import criar_jwt
from app.database import get_db
from app.models.manual import Manual, ManualVersao
from app.routers.manuais import router, PublicarManual
from app.services.manual_pdf import gerar_pdf
from scripts.database.seed.seed_manuais import seed, MANUAIS


class ManuaisTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Manual.__table__.create(self.engine)
        ManualVersao.__table__.create(self.engine)
        self.session = sessionmaker(bind=self.engine)
        with self.session() as db:
            seed(db)
        app = FastAPI()
        app.include_router(router)
        def database():
            with self.session() as db:
                yield db
        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        self.headers = {'Authorization': 'Bearer ' + criar_jwt({'sub': '1', 'role': 'operador'})}

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def get(self, path):
        return self.client.get('/manuais' + path, headers=self.headers)

    def payload(self):
        doc = deepcopy(MANUAIS[0])
        doc.pop('slug')
        return {**doc, 'versao_base': 1, 'resumo_alteracao': 'Atualização das orientações de cadastro.'}

    def test_seed_is_idempotent_and_preserves_edits(self):
        payload = self.payload()
        payload['etapas'][0]['orientacoes'] = 'Orientação editada pela equipe.'
        self.assertEqual(201, self.client.post('/manuais/negociacao-venda/versoes', headers=self.headers, json=payload).status_code)
        with self.session() as db:
            seed(db)
            self.assertEqual(3, db.query(Manual).count())
            self.assertEqual(4, db.query(ManualVersao).count())
        self.assertEqual('Orientação editada pela equipe.', self.get('/negociacao-venda').json()['etapas'][0]['orientacoes'])

    def test_access_requires_operator_for_read_write_and_pdf(self):
        partner = {'Authorization': 'Bearer ' + criar_jwt({'sub': '3', 'role': 'usuario'})}
        for headers in [{}, partner]:
            for path in ['', '/manual-parceiro', '/manual-parceiro/pdf']:
                self.assertEqual(403, self.client.get('/manuais' + path, headers=headers).status_code)
            self.assertEqual(403, self.client.post('/manuais/negociacao-venda/versoes', headers=headers, json=self.payload()).status_code)

    def test_publishing_preserves_history_and_rejects_stale_base(self):
        original = self.get('/negociacao-venda').json()
        payload = self.payload()
        payload['titulo'] = 'Negociação e Venda atualizada'
        url = '/manuais/negociacao-venda/versoes'
        self.assertEqual(201, self.client.post(url, headers=self.headers, json=payload).status_code)
        self.assertEqual(409, self.client.post(url, headers=self.headers, json=payload).status_code)
        self.assertEqual(original['titulo'], self.get('/negociacao-venda?versao=1').json()['titulo'])
        atual = self.get('/negociacao-venda').json()
        self.assertEqual(2, atual['versao_atual'])
        self.assertEqual(2, len(atual['historico']))

    def test_audience_boundaries_and_validation(self):
        payload = self.payload()
        payload['etapas'][0]['responsavel'] = 'PARCEIRO'
        self.assertEqual(422, self.client.post('/manuais/negociacao-venda/versoes', headers=self.headers, json=payload).status_code)
        payload['etapas'] = []
        self.assertEqual(422, self.client.post('/manuais/negociacao-venda/versoes', headers=self.headers, json=payload).status_code)
        self.assertEqual(404, self.get('/manual-parceiro/pdf?publico=CLUBBAR').status_code)
        self.assertEqual(404, self.get('/inexistente').status_code)
        self.assertEqual(404, self.get('/manual-parceiro?versao=999').status_code)

    def test_all_seed_content_is_valid_and_pdfs_generated(self):
        self.assertEqual(3, len(self.get('').json()))
        for doc in MANUAIS:
            PublicarManual(**{k: v for k, v in doc.items() if k != 'slug'}, versao_base=1, resumo_alteracao='Carga inicial')
            response = self.get('/' + doc['slug'] + '/pdf?versao=1')
            self.assertEqual(200, response.status_code)
            self.assertTrue(response.content.startswith(b'%PDF-'))
            self.assertIn('application/pdf', response.headers['content-type'])
        response = self.get('/negociacao-venda/pdf?publico=LEAD')
        self.assertEqual(200, response.status_code)
        self.assertIn('lead.pdf', response.headers['content-disposition'])

    def test_long_editable_text_and_xml_characters_render(self):
        doc = deepcopy(MANUAIS[0])
        doc['etapas'][0]['orientacoes'] = ('Texto longo com <tags> & caracteres especiais. ' * 220)
        doc.update(versao=2, criado_em=datetime.now())
        self.assertTrue(gerar_pdf(doc).startswith(b'%PDF-'))

    def test_backup_roundtrip_restores_all_versions_after_reset(self):
        payload = self.payload()
        payload['titulo'] = 'Versão personalizada para restauração'
        self.assertEqual(201, self.client.post('/manuais/negociacao-venda/versoes', headers=self.headers, json=payload).status_code)
        backup = self.get('/backup/exportar').json()
        with self.engine.begin() as conn:
            conn.exec_driver_sql('CREATE TABLE outro_cadastro (id INTEGER PRIMARY KEY, nome TEXT)')
            conn.exec_driver_sql("INSERT INTO outro_cadastro VALUES (1, 'Preservar')")
        with self.session() as db:
            db.query(ManualVersao).delete()
            db.query(Manual).delete()
            db.commit()
        response = self.client.post('/manuais/backup/importar', headers=self.headers, json=backup)
        self.assertEqual(200, response.status_code)
        self.assertEqual({'manuais': 3, 'versoes': 4}, response.json())
        self.assertEqual(backup['manuais'], self.get('/backup/exportar').json()['manuais'])
        self.assertEqual(payload['titulo'], self.get('/negociacao-venda').json()['titulo'])
        with self.engine.connect() as conn:
            self.assertEqual('Preservar', conn.exec_driver_sql('SELECT nome FROM outro_cadastro').scalar())
        self.assertEqual(200, self.client.post('/manuais/backup/importar', headers=self.headers, json=backup).status_code)
        self.assertEqual(backup['manuais'], self.get('/backup/exportar').json()['manuais'])

    def test_invalid_backup_does_not_change_existing_manuals(self):
        original = self.get('/backup/exportar').json()
        for change in ['tipo', 'duplicado', 'historico', 'publico']:
            bad = deepcopy(original)
            if change == 'tipo': bad['tipo'] = 'outro.sistema'
            elif change == 'duplicado': bad['manuais'][1] = bad['manuais'][0]
            elif change == 'historico': bad['manuais'][0]['versoes'][0]['versao'] = 3
            else: bad['manuais'][2]['versoes'][0]['etapas'][0]['responsavel'] = 'CLUBBAR'
            r = self.client.post('/manuais/backup/importar', headers=self.headers, json=bad)
            self.assertEqual(422, r.status_code)
            self.assertEqual(original['manuais'], self.get('/backup/exportar').json()['manuais'])

    def test_backup_requires_operator_and_failed_restore_rolls_back(self):
        backup = self.get('/backup/exportar').json()
        self.assertEqual(403, self.client.get('/manuais/backup/exportar').status_code)
        self.assertEqual(403, self.client.post('/manuais/backup/importar', json=backup).status_code)
        with patch('sqlalchemy.orm.Session.commit', side_effect=RuntimeError('Falha simulada')):
            with self.assertRaises(RuntimeError):
                self.client.post('/manuais/backup/importar', headers=self.headers, json=backup)
        self.assertEqual(backup['manuais'], self.get('/backup/exportar').json()['manuais'])


if __name__ == '__main__':
    unittest.main()
