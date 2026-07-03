def template_email_clubbar(
    *,
    titulo: str,
    subtitulo: str | None = None,
    conteudo_html: str,
    botao_texto: str | None = None,
    botao_link: str | None = None,
):
    bloco_botao = ""

    if botao_texto and botao_link:
        bloco_botao = f"""
        <div align="center" style="margin-top:40px;">
          <a href="{botao_link}"
             style="
               background:#000;
               color:#fff;
               padding:15px 28px;
               text-decoration:none;
               font-weight:bold;
               border-radius:8px;
               display:inline-block;
             ">
            {botao_texto}
          </a>
        </div>
        """

    bloco_subtitulo = ""

    if subtitulo:
        bloco_subtitulo = f"""
        <p style="font-size:16px;color:#444;line-height:26px;">
          {subtitulo}
        </p>
        """

    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
</head>

<body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,Helvetica,sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:30px 0;">
    <tr>
      <td align="center">

        <table width="600" cellpadding="0" cellspacing="0"
               style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.15);">

          <tr>
            <td align="center" style="background:#000;padding:30px;">
              <img
                src="https://app.clubbar.com.br/assets/images/logo_copa.png"
                height="70"
                alt="Clubbar"
              >
            </td>
          </tr>

          <tr>
            <td style="padding:40px;">

              <h2 style="margin-top:0;color:#222;">
                {titulo}
              </h2>

              {bloco_subtitulo}

              {conteudo_html}

              {bloco_botao}

            </td>
          </tr>

          <tr>
            <td align="center"
                style="
                  background:#fafafa;
                  padding:25px;
                  border-top:1px solid #eee;
                  font-size:13px;
                  color:#777;
                  line-height:20px;
                ">
              <b>Clubbar</b><br>
              Compras inteligentes para bares, restaurantes e eventos.<br><br>
              📧 suporte@clubbar.com.br
            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>

</body>
</html>
"""