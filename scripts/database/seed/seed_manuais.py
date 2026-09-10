"""Carga inicial idempotente. Nunca sobrescreve versões editadas pelo Admin."""
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_DIR))

from app.database import SessionLocal
from app.models.manual import Manual, ManualVersao


def etapa(titulo, responsavel, ambiente, caminho, orientacoes, resultado, aviso=""):
    return dict(titulo=titulo, responsavel=responsavel, ambiente=ambiente,
                caminho=caminho, orientacoes=orientacoes, resultado=resultado, aviso=aviso)


MANUAIS = [
    dict(slug="negociacao-venda", titulo="Negociação e Venda", descricao=
         "Do primeiro interesse à contratação. O Lead é o interessado; a equipe Clubbar conduz o atendimento. Cada estabelecimento tem sua própria negociação, contrato e conversão. As etapas identificam separadamente quem deve agir.", etapas=[
        etapa("Cadastrar o interesse", "LEAD", "SITE", "Quero conhecer o Clubbar > Confirmar cadastro",
              "Preencha nome do responsável, telefone, e-mail e os dados do estabelecimento. Informe o nome do grupo ou empresa, se houver.\n\nUse Adicionar outro estabelecimento quando houver mais de uma unidade. Revise os dados e selecione Confirmar cadastro. Guarde as orientações de acesso ao portal.",
              "Lead cadastrado e disponível para atendimento."),
        etapa("Iniciar o atendimento", "CLUBBAR", "ADMIN", "Leads > selecionar o lead > Abrir atendimento",
              "Confira os contatos e os estabelecimentos informados. Identifique se a operação venderá produtos, ingressos ou ambos. Registre a conversa e acompanhe a situação de cada estabelecimento.\n\nUse o atendimento para trocar mensagens, disponibilizar materiais e propor agendamento de demonstração, ligação, reunião online ou visita.",
              "Necessidades identificadas e próximo contato combinado."),
        etapa("Acompanhar a proposta", "LEAD", "SITE", "Acompanhar atendimento > selecionar o estabelecimento",
              "Use Mensagens para conversar com a equipe, Materiais para consultar os arquivos e Agendamentos para acompanhar os compromissos.\n\nConfira as condições de implantação, as taxas, a modalidade de venda e as responsabilidades antes de decidir.",
              "Interessado orientado sobre a proposta e as condições da parceria.",
              "Confira sempre o estabelecimento selecionado. Uma decisão sobre uma unidade não substitui a decisão das demais."),
        etapa("Gerar e disponibilizar o contrato", "CLUBBAR", "ADMIN", "Leads > lead > estabelecimento > Gerar e disponibilizar contrato",
              "Complete e confira os dados contratuais do estabelecimento. Revise as condições comerciais, use Pré-visualizar e confira o documento. Confirme em Gerar e disponibilizar.\n\nO modelo geral é administrado em Contrato padrão; o documento gerado para o estabelecimento contém os dados daquela contratação.",
              "Contrato disponível no portal do interessado.",
              "Se o botão estiver indisponível, confira os dados contratuais e a situação do estabelecimento."),
        etapa("Ler e aceitar o contrato", "LEAD", "SITE", "Acompanhar atendimento > estabelecimento > Aceitar parceria",
              "Consulte Visualizar contrato. Para avançar, selecione Aceitar parceria, leia o documento, marque Li e aceito o contrato e confirme. Em seguida, selecione Concluir parceria.\n\nUse Baixar ou compartilhar contrato em PDF para guardar uma cópia.",
              "Contrato aceito e estabelecimento com a parceria aceita.",
              "O aceite do contrato e Concluir parceria são ações distintas. Conclua as duas para a equipe poder converter o cadastro."),
        etapa("Converter em parceiro e entregar o acesso", "CLUBBAR", "ADMIN", "Leads > lead > estabelecimento > Converter [nome do estabelecimento]",
              "Com a parceria aceita, confira nome da empresa, estabelecimento, tipo de atividade, e-mail do responsável e as condições do contrato. Confirme a conversão.\n\nNa primeira conversão são criados a empresa e o acesso do responsável. As próximas unidades do mesmo lead são vinculadas à empresa existente. Acompanhe a entrega do convite e use Reenviar convite de acesso quando necessário.\n\nConsulte a cobrança em Consultar taxa de implantação, conforme as condições contratadas. Encaminhe ao responsável o Manual do Parceiro e siga internamente o Roteiro de Implantação.",
              "Estabelecimento convertido, acesso encaminhado e implantação iniciada.",
              "Aceitar a parceria não faz a conversão automaticamente; a equipe executa a conversão no Admin."),
    ]),
    dict(slug="roteiro-implantacao", titulo="Roteiro de Implantação", descricao=
         "Checklist de trabalho da equipe Clubbar após a contratação. Este guia contém as ações da equipe interna. Os cadastros executados pelo responsável do estabelecimento estão detalhados separadamente no Manual do Parceiro.", etapas=[
        etapa("Conferir a passagem da venda", "CLUBBAR", "ADMIN", "Leads > lead > estabelecimento",
              "Confira contrato aceito, parceria concluída e conversão do estabelecimento. Revise contatos e condições de implantação. Consulte a taxa de implantação para acompanhar a situação da cobrança; uma eventual isenção deve ser registrada com justificativa pela equipe responsável.",
              "Condições da contratação conferidas e responsável pelo início da implantação definido."),
        etapa("Garantir o primeiro acesso", "CLUBBAR", "ADMIN", "Leads > estabelecimento convertido > Reenviar convite de acesso",
              "Confirme com o responsável se recebeu o convite e conseguiu entrar no Partner. Caso necessário, utilize Reenviar convite de acesso.\n\nExplique que Site é o canal da contratação, Admin é a ferramenta da equipe Clubbar e Partner é o aplicativo de gestão do estabelecimento. Entregue o PDF Manual do Parceiro.",
              "Responsável com acesso ao Partner e material de orientação recebido.",
              "O reenvio do convite pode gerar nova senha. Oriente o responsável a utilizar os dados do convite mais recente."),
        etapa("Conferir empresa e unidades", "CLUBBAR", "ADMIN", "Empresas Parceiras / Estabelecimentos Parceiros",
              "Confira se a empresa e cada unidade convertida aparecem nos cadastros. Oriente o responsável a revisar Minha empresa e Meus estabelecimentos no Partner.\n\nAcompanhe a conclusão de dados cadastrais, identificação visual, horários, conteúdo de apresentação e regras de produtos ou ingressos.",
              "Estrutura da empresa conferida e unidades identificadas corretamente."),
        etapa("Acompanhar a ativação financeira", "CLUBBAR", "ADMIN", "Estabelecimentos Parceiros / Gerenciar repasses ao parceiro",
              "Combine com o parceiro a conclusão de Titular financeiro e Integração Asaas no Partner. Peça que acompanhe a situação em Verificar situação no Asaas e resolva as pendências apresentadas pelo provedor.\n\nA aprovação de recebimentos é uma etapa diferente da conversão do lead. Acompanhe os registros financeiros disponíveis no Admin.",
              "Parceiro orientado a concluir a validação financeira antes de publicar vendas.",
              "Documentos e selfie são enviados pelo próprio parceiro no ambiente do Asaas. Não peça que ele os envie por mensagens do atendimento."),
        etapa("Orientar os cadastros operacionais", "CLUBBAR", "ADMIN", "Roteiro de Implantação e Manual do Parceiro > Manual do Parceiro",
              "Use o manual para acompanhar o responsável na preparação dos produtos e cardápios ou dos eventos e ingressos. Confirme qual unidade está sendo configurada.\n\nPara produtos, confira categorias, itens, preços e publicação. Para eventos, confira modelo, data na agenda, atrações, capacidade, ingressos e preços. Revise também os acessos da equipe de operação.",
              "Cadastros preparados e responsável capaz de repetir os procedimentos no Partner."),
        etapa("Acompanhar a primeira operação", "CLUBBAR", "ADMIN", "Vendas e faturamento hoje / Gerenciar repasses ao parceiro",
              "Combine a primeira operação com o parceiro e acompanhe a venda, a confirmação do pagamento e o uso do ticket ou ingresso. Oriente o responsável a conferir os registros no Partner.\n\nVerifique se a equipe sabe validar os QR Codes e se o responsável sabe consultar Acompanhamento de vendas, Painel Gerencial, Painel Financeiro e Extrato Asaas.",
              "Primeiro ciclo acompanhado e parceiro orientado para operar com autonomia."),
        etapa("Manter os manuais atualizados", "CLUBBAR", "ADMIN", "Roteiro de Implantação e Manual do Parceiro > guia > Editar e publicar nova versão",
              "Ao criar ou alterar uma funcionalidade, revise as etapas afetadas: responsável, aplicativo, caminho, instruções, resultado e observações. Adicione ou reordene etapas quando necessário.\n\nRegistre um resumo da alteração e publique uma nova versão. Confira o fluxograma e o PDF antes de distribuir. O histórico preserva as versões anteriores; uma nova execução do seed não substitui edições realizadas no Admin.",
              "Documentação alinhada ao sistema e nova versão pronta para distribuição."),
    ]),
    dict(slug="manual-parceiro", titulo="Manual do Parceiro", descricao=
         "Guia do responsável pelo estabelecimento e de sua equipe, desde o primeiro acesso até o acompanhamento das vendas. Empresa é o cadastro que reúne o negócio; estabelecimento é cada unidade. Execute as etapas compatíveis com sua modalidade de venda.", etapas=[
        etapa("Entrar e conferir a empresa", "PARCEIRO", "PARTNER", "Login > Minha empresa",
              "Entre com os dados do convite de acesso recebido após a contratação. Confira os dados gerais em Minha empresa.\n\nSe não conseguir acessar, solicite apoio à equipe Clubbar. As opções do aplicativo dependem do perfil e das permissões do usuário.",
              "Responsável conectado e dados gerais conferidos."),
        etapa("Configurar cada estabelecimento", "PARCEIRO", "PARTNER", "Meus estabelecimentos > Ações do estabelecimento",
              "Use Editar estabelecimento para conferir os dados da unidade. Complete Logo e foto da fachada, Horários de funcionamento e Conteúdo do estabelecimento.\n\nRevise Configuração de produtos para operações com produtos e Política de ingressos quando trabalhar com ingressos.",
              "Unidade identificada e configurações básicas concluídas.",
              "Confira a unidade selecionada antes de salvar qualquer alteração."),
        etapa("Informar o titular financeiro", "PARCEIRO", "PARTNER", "Titular financeiro > Salvar dados financeiros",
              "Informe se o titular é pessoa física ou jurídica e preencha documento, identificação, contato, endereço e demais dados obrigatórios. Confira tudo antes de usar Salvar dados financeiros.",
              "Titular dos recebimentos cadastrado."),
        etapa("Ativar e validar os recebimentos", "PARCEIRO", "PARTNER", "Integração Asaas > Ativar recebimentos",
              "Selecione Ativar recebimentos. Siga as instruções e, quando disponível, use Enviar documentos e selfie. Complete a validação diretamente no ambiente do Asaas.\n\nVolte ao Partner e use Verificar situação no Asaas para acompanhar. Se houver pendências, siga as orientações apresentadas.",
              "Situação financeira APROVADO para permitir a publicação das vendas.",
              "Subconta criada não significa subconta aprovada. A validação e os recebimentos são diferentes da contratação e de sua taxa de implantação."),
        etapa("Preparar produtos e cardápios", "PARCEIRO", "PARTNER", "Cardápio Digital > selecionar estabelecimento",
              "Organize categorias, produtos e preços. Na gestão de cardápios, use Adicionar cardápio e prepare o conteúdo que será oferecido ao consumidor. Revise o rascunho antes de Publicar.\n\nPara aproveitar um cardápio da empresa, use Meus estabelecimentos > Importar Cardápio Digital da empresa. Confira os itens e preços da unidade após a importação.",
              "Cardápio da unidade preparado e publicado para a operação com produtos.",
              "Execute esta etapa se vender produtos. Cadastrar um item não substitui a conferência e publicação do cardápio."),
        etapa("Cadastrar atrações e eventos padrão", "PARCEIRO", "PARTNER", "Estilos musicais > Atrações > Gerenciar eventos",
              "Organize os estilos musicais utilizados. Em Atrações, cadastre artistas, bandas, DJs ou outras atrações.\n\nEm Gerenciar eventos, use Adicionar evento padrão para criar o modelo da programação e Atrações padrão para associar as atrações.",
              "Modelos de eventos e atrações preparados.",
              "O evento padrão é um modelo. Ele precisa ser associado a uma data e a um estabelecimento."),
        etapa("Programar datas e configurar ingressos", "PARCEIRO", "PARTNER", "Gerenciar eventos > Adicionar à agenda / Agenda Mensal",
              "Use Adicionar à agenda para escolher estabelecimento, data e as configurações da ocorrência. Confira a programação em Agenda Mensal.\n\nNa data selecionada, use Gerenciar ingressos e preços para configurar os ingressos e valores. Revise atrações, horários, capacidade e preços antes de publicar a agenda.\n\nExemplo: Sexta do Samba é um modelo; a apresentação em uma sexta-feira às 20h, em uma unidade específica, é uma ocorrência.",
              "Programação conferida e publicada com ingressos e preços adequados."),
        etapa("Preparar os acessos da equipe", "PARCEIRO", "PARTNER", "Usuários e permissões",
              "Cadastre ou revise os usuários da equipe. Atribua as permissões conforme as funções de gestão, retirada de produtos e validação de ingressos.\n\nConfira se cada pessoa consegue acessar as funções necessárias antes de começar a operação.",
              "Equipe com acesso adequado às tarefas do estabelecimento."),
        etapa("Validar tickets e ingressos", "PARCEIRO", "PARTNER", "Acesso operacional de retirada de produtos ou validação de ingressos",
              "O consumidor compra no Clubbar Client. Após a confirmação do pagamento, o ticket ou ingresso fica na carteira e pode ser apresentado à equipe.\n\nPara produtos, valide o QR Code antes da entrega do item. Para ingressos, valide antes de liberar a entrada. Confira o resultado mostrado pelo aplicativo antes de concluir o atendimento.",
              "Compra utilizada e validação registrada na operação.",
              "Se a validação não for confirmada, confira a mensagem exibida e peça orientação ao responsável. Não trate apenas a imagem do QR Code como comprovação de uso válido."),
        etapa("Acompanhar vendas e recebimentos", "PARCEIRO", "PARTNER", "Acompanhamento de vendas / Painel Gerencial / Painel Financeiro / Extrato Asaas",
              "Use Acompanhamento de vendas para consultar a operação e Painel Gerencial para os indicadores do negócio.\n\nConsulte Painel Financeiro para repasses e recebimentos por estabelecimento. Em Extrato Asaas, confira saldo e transações da subconta. Utilize Auditoria para consultar os registros das ações realizadas no sistema.",
              "Responsável acompanhando a operação e os resultados."),
        etapa("Conferir antes da primeira venda", "PARCEIRO", "PARTNER", "Minha empresa / Meus estabelecimentos / Integração Asaas / Cardápio Digital / Agenda Mensal",
              "Confira: acesso funcionando; empresa e unidade corretas; recebimentos aprovados; cardápio e/ou agenda publicados; preços e horários revisados; equipe com permissões e orientação para validar QR Codes.\n\nNa primeira operação, acompanhe a compra, o pagamento, a apresentação do ticket e a validação. Em caso de dúvida, informe à equipe Clubbar a unidade, a função utilizada e a mensagem apresentada.",
              "Primeiro ciclo conferido e estabelecimento pronto para continuar a operação."),
    ]),
]


def seed(db):
    for ordem, dados in enumerate(MANUAIS, 1):
        if db.query(Manual).filter(Manual.slug == dados["slug"]).first():
            continue
        manual = Manual(slug=dados["slug"], ordem=ordem)
        db.add(manual)
        db.flush()
        db.add(ManualVersao(manual_id=manual.manual_id, versao=1, titulo=dados["titulo"],
                           descricao=dados["descricao"], etapas=dados["etapas"],
                           resumo_alteracao="Carga inicial do roteiro do ecossistema Clubbar."))
    db.commit()


def main():
    with SessionLocal() as db:
        seed(db)
        print("Três manuais disponíveis. Versões existentes preservadas.")


if __name__ == "__main__":
    main()
