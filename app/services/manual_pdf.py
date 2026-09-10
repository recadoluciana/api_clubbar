"""PDF vetorial: conteúdo e fluxograma derivados da mesma versão do manual."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak

AZUL = colors.HexColor("#162D46")
AMBAR = colors.HexColor("#F4B740")
PUBLICOS = {"CLUBBAR": "Equipe Clubbar", "LEAD": "Interessado / Lead", "PARCEIRO": "Parceiro"}


def gerar_pdf(manual: dict) -> bytes:
    buffer = BytesIO()
    styles = {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=27, leading=32, textColor=AZUL, spaceAfter=18),
        "h": ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=16, leading=21, textColor=AZUL, spaceAfter=12),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=10.5, leading=16, spaceAfter=10, textColor=AZUL),
        "small": ParagraphStyle("small", fontName="Helvetica", fontSize=9, leading=13, textColor=AZUL, spaceAfter=6),
        "flow": ParagraphStyle("flow", fontName="Helvetica", fontSize=9, leading=11, textColor=AZUL),
    }
    def p(value, style="body"):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), styles[style])

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=48, leftMargin=48,
                            topMargin=58, bottomMargin=48, title=manual["titulo"], author="Clubbar")
    width = A4[0] - 96
    def footer(canvas, document):
        canvas.saveState()
        canvas.setFillColor(AZUL)
        canvas.rect(0, A4[1] - 30, A4[0], 30, fill=1, stroke=0)
        canvas.setFillColor(AMBAR)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(48, A4[1] - 20, "CLUBBAR  /  CENTRAL DE CONHECIMENTO")
        canvas.setFillColor(AZUL)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(48, 27, f'Versão {manual["versao"]} - {manual["criado_em"].strftime("%d/%m/%Y")}')
        canvas.drawRightString(A4[0] - 48, 27, f"Página {document.page}")
        canvas.restoreState()

    story = [Spacer(1, 10), p(manual["titulo"], "title"), p(manual["descricao"])]
    publico = manual.get("publico_exportado")
    audience = PUBLICOS[publico] if publico else " / ".join(dict.fromkeys(PUBLICOS[e["responsavel"]] for e in manual["etapas"]))
    story += [p(f"Preparado para: {audience}", "small"),
              p("Cada etapa informa quem executa, qual aplicativo utilizar, o caminho e o resultado esperado. As opções disponíveis dependem das permissões do usuário.", "small"),
              Spacer(1, 18), p("Fluxo de trabalho", "h")]
    for i, etapa in enumerate(manual["etapas"], 1):
        label = Paragraph(f'<b>{i:02d}  {escape(etapa["titulo"])}</b><br/>'
                          f'{PUBLICOS[etapa["responsavel"]]} | {etapa["ambiente"]}', styles['flow'])
        card = Table([[label]], colWidths=[width])
        card.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF4F8")),
                                  ("LINEBEFORE", (0, 0), (0, -1), 4, AMBAR),
                                  ("LEFTPADDING", (0, 0), (-1, -1), 14),
                                  ("TOPPADDING", (0, 0), (-1, 0), 4),
                                  ("BOTTOMPADDING", (0, -1), (-1, -1), 4)]))
        group = [card]
        if i < len(manual["etapas"]):
            from reportlab.graphics.shapes import Drawing, Line, Polygon
            arrow = Drawing(width, 10)
            x = width / 2
            arrow.add(Line(x, 10, x, 3, strokeColor=AZUL, strokeWidth=1))
            arrow.add(Polygon([x-3, 4, x+3, 4, x, 0], fillColor=AZUL, strokeColor=AZUL))
            group.append(arrow)
        story.append(KeepTogether(group))
    story.append(PageBreak())
    for i, etapa in enumerate(manual["etapas"], 1):
        intro = [p(f'{i:02d}. {etapa["titulo"]}', "h"),
                 p(f'QUEM: {PUBLICOS[etapa["responsavel"]]}   |   ONDE: {etapa["ambiente"]}', "small"),
                 p(f'Caminho: {etapa["caminho"]}', "small")]
        # Keep the heading with the first paragraph; long sections may span pages.
        paragraphs = etapa["orientacoes"].split("\n\n")
        intro.extend(p(t) for t in paragraphs)
        intro.append(p("Resultado esperado: " + etapa["resultado"]))
        if etapa.get("aviso"):
            intro.append(p("Atenção: " + etapa["aviso"], "small"))
        story.append(KeepTogether(intro))
        if i < len(manual['etapas']):
            story.append(Spacer(1, 12))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
