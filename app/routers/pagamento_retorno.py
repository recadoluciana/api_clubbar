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
        <h2>✅ Pagamento finalizado, pode fechar esta tela.</h2>
        <p>Depois volte para o aplicativo ClubBar.</p>
      </body>
    </html>
    """

