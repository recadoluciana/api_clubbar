"""Publica novo modelo sem taxa, preservando modelos e contratos assinados."""
import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models.contratopadrao import ContratoPadrao


CLAUSULA_ANTIGA = (
    'Pela ativação da conta financeira, configuração inicial da organização e do estabelecimento, '
    'treinamento de acesso, configuração inicial de produtos ou eventos, acompanhamento da primeira '
    'venda e suporte assistido durante a implantação, será cobrada uma única taxa de implantação de '
    'R$ {{TAXA_IMPLANTACAO}}. A implantação e a publicação das vendas poderão permanecer bloqueadas '
    'até a confirmação desse pagamento.'
)
CLAUSULA_NOVA = 'Não há cobrança de taxa de implantação para iniciar a parceria.'
TEXTO_ANTIGO = 'do aceite deste contrato, do pagamento da implantação, do fornecimento'
TEXTO_NOVO = 'do aceite deste contrato, do fornecimento'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--versao', required=True)
    args = parser.parse_args()
    with SessionLocal() as db:
        ativos = db.query(ContratoPadrao).filter_by(sitcontrato='ATIVO').with_for_update().all()
        if len(ativos) != 1:
            raise RuntimeError('Esperado exatamente um modelo de contrato ativo.')
        atual = ativos[0]
        if db.query(ContratoPadrao).filter_by(versao=args.versao).first():
            raise RuntimeError('Esta versão já existe.')
        conteudo = atual.conteudomodelo
        if conteudo.count(CLAUSULA_ANTIGA) != 1 or conteudo.count(TEXTO_ANTIGO) != 1:
            raise RuntimeError('O modelo ativo é diferente do esperado; revise-o no Admin.')
        conteudo = conteudo.replace(CLAUSULA_ANTIGA, CLAUSULA_NOVA).replace(TEXTO_ANTIGO, TEXTO_NOVO)
        atual.sitcontrato = 'INATIVO'
        db.add(ContratoPadrao(versao=args.versao, titulo=atual.titulo, conteudomodelo=conteudo,
                              vrimplantacao=0, sitcontrato='ATIVO', dtvigencia=datetime.now()))
        db.commit()
        print(f'Contrato padrão {args.versao} publicado; versão anterior preservada.')


if __name__ == '__main__':
    main()
