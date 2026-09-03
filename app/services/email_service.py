import os
from html import escape
import httpx
from fastapi import HTTPException
from app.services.email_templates import template_email_clubbar


BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_FROM_EMAIL = os.getenv("BREVO_FROM_EMAIL")
BREVO_FROM_NAME = os.getenv("BREVO_FROM_NAME", "Clubbar")


def _enviar_email(destinatario: str, assunto: str, html: str) -> None:
    if not BREVO_API_KEY:
        raise HTTPException(status_code=500, detail="BREVO_API_KEY não configurada.")
    response = httpx.post(
        "https://api.brevo.com/v3/smtp/email",
        json={
            "sender": {"name": BREVO_FROM_NAME, "email": BREVO_FROM_EMAIL},
            "to": [{"email": destinatario}],
            "subject": assunto,
            "htmlContent": html,
        },
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": BREVO_API_KEY,
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Não foi possível enviar o e-mail.")


def enviar_convite_parceiro(
    destinatario: str,
    nome_responsavel: str,
    nome_organizacao: str,
    senha_inicial: str,
) -> None:
    portal = os.getenv("PARTNER_PORTAL_URL", "https://parceiro.clubbar.com.br")
    conteudo = f"""
    <p>Olá, <b>{nome_responsavel}</b>.</p>
    <p>A organização <b>{nome_organizacao}</b> foi aprovada no Clubbar.</p>
    <p>Acesse <a href="{portal}">{portal}</a> usando:</p>
    <p><b>E-mail:</b> {destinatario}<br><b>Senha inicial:</b> {senha_inicial}</p>
    <p>Depois de entrar, complete a organização, a loja e o onboarding financeiro.</p>
    """
    _enviar_email(
        destinatario,
        "Seu acesso ao Clubbar Partner",
        template_email_clubbar(
            titulo="Bem-vindo ao Clubbar Partner",
            subtitulo="Seu cadastro comercial foi aprovado.",
            conteudo_html=conteudo,
        ),
    )


def enviar_acesso_portal_lead(destinatario: str, nome: str, token: str) -> None:
    ambiente = os.getenv('APP_ENV', 'development').strip().lower()
    site_padrao = (
        'https://clubbarsite-desenvolvimento.up.railway.app'
        if ambiente in {'dev', 'development'}
        else 'https://clubbar.com.br'
    )
    site = os.getenv('PUBLIC_SITE_URL', site_padrao).rstrip('/')
    link = f'{site}/portal-lead.html#acesso={token}'
    conteudo = f'''
    <p>Olá, <b>{nome}</b>.</p>
    <p>Use o botão abaixo para acompanhar sua proposta, conversar com a equipe Clubbar e responder agendamentos.</p>
    <p><a href='{link}' style='display:inline-block;padding:14px 22px;background:#ffc107;color:#000;text-decoration:none;border-radius:10px;font-weight:bold'>Acessar meu atendimento</a></p>
    <p>Este link é pessoal e tem validade de 30 dias.</p>
    '''
    _enviar_email(
        destinatario,
        'Acesso ao seu atendimento Clubbar',
        template_email_clubbar(
            titulo='Seu atendimento Clubbar',
            subtitulo='Acompanhe a conversa com nossa equipe.',
            conteudo_html=conteudo,
        ),
    )


def enviar_dados_portal_lead(destinatario: str, leads: list[dict[str, str]]) -> None:
    itens = "".join(
        f"<li style='margin-bottom:12px'><b>{escape(item['nome'])}</b><br>"
        f"E-mail: {escape(destinatario)}<br>Telefone: {escape(item['telefone'])}</li>"
        for item in leads
    )
    conteudo = f"""
    <p>Estes são os dados de acesso encontrados para o seu e-mail:</p>
    <ul>{itens}</ul>
    <p>Na tela “Acompanhar meu atendimento”, informe o e-mail e o telefone correspondentes ao lead que deseja acessar.</p>
    <p>Se você não solicitou estes dados, ignore esta mensagem.</p>
    """
    _enviar_email(
        destinatario,
        "Seus dados de acesso ao atendimento Clubbar",
        template_email_clubbar(
            titulo="Dados do seu atendimento",
            subtitulo="Acesse o lead correto no Portal Clubbar.",
            conteudo_html=conteudo,
        ),
    )


def enviar_confirmacao_cadastro_lead(
    destinatario: str,
    lead: dict,
    estabelecimentos: list[dict],
) -> None:
    nomes_tipo = {
        "BAR": "Bar",
        "CASA_NOTURNA": "Casa noturna",
        "PRODUTOR_EVENTOS": "Produtor de eventos",
        "CASA_EVENTOS": "Casa de eventos",
    }
    nomes_venda = {
        "PRODUTOS": "Somente produtos",
        "INGRESSOS": "Somente ingressos",
        "AMBOS": "Produtos e ingressos",
    }

    cards = []
    for indice, item in enumerate(estabelecimentos, start=1):
        endereco = ", ".join(
            parte
            for parte in [
                item.get("endereco"),
                item.get("numero"),
                item.get("bairro"),
                item.get("complemento"),
            ]
            if parte
        )
        localidade = " - ".join(
            parte for parte in [item.get("cidade"), item.get("estado")] if parte
        )
        linhas = [
            ("Nome", item.get("nmestabelecimento")),
            ("Tipo", nomes_tipo.get(item.get("tipo"), item.get("tipo"))),
            ("O que deseja vender", nomes_venda.get(item.get("tipovenda"), item.get("tipovenda"))),
            ("Responsável", item.get("nmresponsavel")),
            ("Telefone do responsável", item.get("telefone_responsavel")),
            ("E-mail do responsável", item.get("email_responsavel")),
            ("CPF/CNPJ", item.get("cpfcnpj")),
            ("CEP", item.get("cep")),
            ("Endereço", endereco or None),
            ("Cidade/Estado", localidade or None),
        ]
        detalhes = "".join(
            f"<b>{escape(rotulo)}:</b> {escape(str(valor))}<br>"
            for rotulo, valor in linhas
            if valor
        )
        cards.append(
            f"<div style='margin:16px 0;padding:16px;border:1px solid #ddd;border-radius:12px'>"
            f"<h3 style='margin-top:0'>Estabelecimento {indice}</h3>{detalhes}</div>"
        )

    organizacao = lead.get("nmorganizacao") or "Não informada"
    conteudo = f"""
    <p>Olá, <b>{escape(str(lead.get('nmresponsavel') or ''))}</b>.</p>
    <p>Seu interesse no Clubbar foi cadastrado com sucesso. Confira os dados enviados:</p>
    <div style='margin:16px 0;padding:16px;background:#f6f6f6;border-radius:12px'>
      <b>Responsável:</b> {escape(str(lead.get('nmresponsavel') or ''))}<br>
      <b>Organização:</b> {escape(str(organizacao))}<br>
      <b>E-mail:</b> {escape(str(lead.get('email') or ''))}<br>
      <b>Telefone:</b> {escape(str(lead.get('telefone') or ''))}
    </div>
    {''.join(cards)}
    <p>A equipe Clubbar entrará em contato para dar continuidade ao atendimento.</p>
    """
    _enviar_email(
        destinatario,
        "Confirmação do seu cadastro no Clubbar",
        template_email_clubbar(
            titulo="Cadastro recebido",
            subtitulo="Confira os dados enviados para a equipe Clubbar.",
            conteudo_html=conteudo,
        ),
    )
def enviar_email_codigo(destinatario: str, codigo: str):
    if not BREVO_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="BREVO_API_KEY não configurada.",
        )

    conteudo_html = f"""
    <p style="font-size:16px;color:#444;">
      Utilize o código abaixo para redefinir sua senha:
    </p>

    <div style="
      margin:35px auto;
      background:#FFC107;
      border-radius:10px;
      padding:20px;
      text-align:center;
      font-size:42px;
      font-weight:bold;
      letter-spacing:8px;
      color:#000;
    ">
      {codigo}
    </div>

    <p style="font-size:15px;color:#555;">
      Este código é válido por <b>15 minutos</b>.
    </p>

    <p style="font-size:15px;color:#555;">
      Volte ao aplicativo Clubbar e digite este código para criar sua nova senha.
    </p>

    <p style="font-size:15px;color:#555;">
      Caso você não tenha solicitado esta recuperação,
      basta ignorar este e-mail.
    </p>
    """

    html = template_email_clubbar(
        titulo="Recuperação de senha",
        subtitulo="Recebemos uma solicitação para redefinir sua senha no Clubbar.",
        conteudo_html=conteudo_html,
    )

    body = {
        "sender": {
            "name": BREVO_FROM_NAME,
            "email": BREVO_FROM_EMAIL,
        },
        "to": [{"email": destinatario}],
        "subject": "Recuperação de senha - Clubbar",
        "htmlContent": html,
    }

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": BREVO_API_KEY,
    }

    response = httpx.post(
        "https://api.brevo.com/v3/smtp/email",
        json=body,
        headers=headers,
        timeout=30,
    )

    print("[BREVO]", response.status_code)
    print(response.text)

    if response.status_code >= 400:
        resposta = response.text.lower()
        if response.status_code == 401 and (
            'unrecognised ip address' in resposta
            or 'unauthorized ip' in resposta
            or 'authorised_ips' in resposta
        ):
            raise HTTPException(
                status_code=503,
                detail=(
                    'O serviço de e-mail está temporariamente indisponível. '
                    'Tente novamente em alguns minutos.'
                ),
            )
        raise HTTPException(
            status_code=502,
            detail='Não foi possível enviar o e-mail de recuperação.',
        )
