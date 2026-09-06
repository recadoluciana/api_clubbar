import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv

load_dotenv(PROJECT_DIR / ".env", override=False)

from app.database import SessionLocal
from app.models.contratopadrao import ContratoPadrao


CONTRATO_V1 = """TERMO DE PARCERIA COMERCIAL CLUBBAR
Versão {{VERSAO}}

ESTABELECIMENTO PARCEIRO
Nome: {{NOME_ESTABELECIMENTO}}
CPF/CNPJ: {{CPF_CNPJ}}
Responsável: {{RESPONSAVEL}}
Telefone: {{TELEFONE}}
E-mail: {{EMAIL}}
Endereço: {{ENDERECO}}
Atividade: {{ATIVIDADE}}
Modalidade de venda: {{MODALIDADE_VENDA}}

1. OBJETO E LICENÇA DE USO
O presente contrato estabelece a parceria comercial e concede ao ESTABELECIMENTO PARCEIRO licença limitada, não exclusiva e intransferível para utilizar a plataforma Clubbar na divulgação e comercialização dos produtos e/ou ingressos indicados em seu cadastro.

2. IMPLANTAÇÃO
Pela ativação da conta financeira, configuração inicial da organização e do estabelecimento, treinamento de acesso, configuração inicial de produtos ou eventos, acompanhamento da primeira venda e suporte assistido durante a implantação, será cobrada uma única taxa de implantação de R$ {{TAXA_IMPLANTACAO}}. A implantação e a publicação das vendas poderão permanecer bloqueadas até a confirmação desse pagamento.

3. COMISSÃO SOBRE AS VENDAS
Pelas vendas realizadas por meio da plataforma serão aplicadas as seguintes taxas Clubbar:
- Produtos: {{TAXA_PRODUTOS}}% sobre o valor definido para incidência.
- Ingressos: {{TAXA_INGRESSOS}}% sobre o valor definido para incidência.
As regras de cálculo, split e repasse observarão as condições apresentadas no momento da contratação e da venda.

4. CUSTOS DO MEIO DE PAGAMENTO
Tarifas de Pix, cartão, antecipação, saque, subconta, análise, chargeback ou outros serviços cobrados pelo Asaas ou por outro meio de pagamento não constituem comissão Clubbar e serão suportados pela parte indicada nas condições comerciais, podendo ser descontados do recebimento.

5. SUPORTE BÁSICO INCLUÍDO
Enquanto o parceiro estiver ativo, estão incluídas orientações rápidas, dúvidas comuns de utilização e tratamento de problemas técnicos da plataforma, pelos canais e horários divulgados pelo Clubbar.

6. SUPORTE PREMIUM E SERVIÇOS ADICIONAIS
Atendimento prioritário, suporte completo, cadastro assistido de cardápio, montagem de eventos, configuração de lotes, treinamento adicional, importação de produtos, alteração visual, atendimento fora do horário e outros serviços operacionais são opcionais e poderão ser contratados e cobrados separadamente, mediante aceite prévio do parceiro.

7. RESPONSABILIDADES DO ESTABELECIMENTO
O ESTABELECIMENTO PARCEIRO declara que os dados fornecidos são verdadeiros e manterá atualizadas as informações, preços, estoque, capacidade, programação, atendimento ao consumidor e demais obrigações relativas aos produtos, serviços e eventos oferecidos. É responsável por suas credenciais e pelo conteúdo publicado.

8. REPASSES, CANCELAMENTOS, ESTORNOS E CHARGEBACKS
Os repasses financeiros observarão os prazos do meio de pagamento. Cancelamentos, reembolsos, estornos e contestações poderão reverter valores anteriormente creditados. O parceiro responderá pelos valores decorrentes da entrega dos produtos, realização dos eventos, descumprimento das políticas publicadas, fraude atribuível à sua operação e demais hipóteses previstas em lei.

9. ATIVAÇÃO FINANCEIRA E PUBLICAÇÃO
A criação ou aprovação da subconta e a liberação para publicar vendas poderão depender do aceite deste contrato, do pagamento da implantação, do fornecimento dos dados e documentos exigidos e da aprovação cadastral pelo meio de pagamento.

10. PROTEÇÃO DE DADOS
As partes tratarão dados pessoais apenas para as finalidades da parceria e observarão a legislação aplicável de proteção de dados. Documentos e selfies exigidos para validação financeira serão enviados diretamente ao ambiente seguro do meio de pagamento quando aplicável.

11. SUSPENSÃO E ENCERRAMENTO
O Clubbar poderá suspender o acesso em caso de fraude, risco operacional, obrigação legal, inadimplência ou descumprimento contratual. Este contrato vigora por prazo indeterminado e pode ser encerrado por qualquer parte, sem prejuízo das obrigações já constituídas.

12. ACEITE ELETRÔNICO
O responsável declara ter lido e concordado com o conteúdo integral. O aceite eletrônico, acompanhado da versão, cópia do documento, hash, identificação do signatário, data, hora e registro técnico, será armazenado como comprovação.

Ao aceitar, {{RESPONSAVEL}} confirma sua concordância em nome do estabelecimento {{NOME_ESTABELECIMENTO}}.
"""


def main() -> None:
    db = SessionLocal()
    try:
        if not db.query(ContratoPadrao).filter(ContratoPadrao.versao == "1").first():
            db.add(ContratoPadrao(
                versao="1",
                titulo="Termo de Parceria Comercial Clubbar",
                conteudomodelo=CONTRATO_V1.strip(),
                vrimplantacao=99.00,
                sitcontrato="ATIVO",
            ))
            db.commit()
            print("Contrato padrão versão 1 criado.")
        else:
            print("Contrato padrão versão 1 já existe.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
