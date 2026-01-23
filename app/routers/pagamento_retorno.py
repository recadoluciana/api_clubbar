from fastapi.responses import HTMLResponse
from fastapi import APIRouter

router = APIRouter(tags=["retorno"])

@router.get("/pagamentos/retorno", response_class=HTMLResponse)
def retorno_pagamento():
    return """
    <html>
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Balada$ - Pagamento</title>
      </head>
      <body style="font-family: Arial; text-align:center; padding:40px;">
        <h2>✅ Pagamento finalizado</h2>
        <p>Agora volte para o aplicativo Balada$.</p>
        <p>Você já pode fechar esta página.</p>
      </body>
    </html>
    """
