import io
from django.http import FileResponse
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib import colors
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from ..models import FotoVideoNavio, DocumentoNavio

@login_required
def gerar_pdf_midia(request, pk):
    midia = get_object_or_404(FotoVideoNavio, pk=pk)
    documentos = DocumentoNavio.objects.filter(navio=midia.navio)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=1*cm, rightMargin=1*cm,
                            topMargin=1*cm, bottomMargin=1*cm)
    elements = []

    styles = getSampleStyleSheet()
    styleN = styles["Normal"]
    styleH = styles["Heading2"]

    navio = midia.navio

    # Cabeçalho
    header = Paragraph("<b>📑 RELATÓRIO DE MÍDIA DO NAVIO</b>", styleH)
    elements.append(header)
    elements.append(Spacer(1, 12))

    # Tabela com dados principais do navio
    dados_navio = [
        ["Navio", navio.navio or "---", "Boca", navio.boca or "---"],
        ["LOA", navio.loa or "---", "Armador", navio.armador or "---"],
        ["Agência", navio.agencia or "---", "Bordo", navio.bordo or "---"],
        ["ETA", navio.eta.strftime("%d/%m/%Y %H:%M") if navio.eta else "---",
         "POB", navio.pob.strftime("%d/%m/%Y %H:%M") if navio.pob else "---"],
        ["Início Operação", navio.inicio_operacao.strftime("%d/%m/%Y %H:%M") if navio.inicio_operacao else "---",
         "Fim Operação", navio.fim_operacao.strftime("%d/%m/%Y %H:%M") if navio.fim_operacao else "---"],
        ["Ternos", navio.ternos or "---", "Tempo Operação", navio.tempo_operacao or "---"],
        ["Volume Descarga", navio.volume_descarga or "---", "Peso Descarga", navio.peso_descarga or "---"],
        ["Volume Embarque", navio.volume_embarque or "---", "Peso Embarque", navio.peso_embarque or "---"],
    ]

    tabela = Table(dados_navio, colWidths=[4*cm, 5*cm, 4*cm, 5*cm])
    tabela.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elements.append(tabela)
    elements.append(Spacer(1, 12))

    # Observação
    obs = Table([["Observação", midia.observacao or "---"]], colWidths=[4*cm, 14*cm])
    obs.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.black),
        ("BACKGROUND", (0, 0), (0, 0), colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(obs)
    elements.append(Spacer(1, 12))

    # Imagem ou aviso de vídeo
    if midia.is_image():
        try:
            img = Image(midia.arquivo.path, width=12*cm, height=8*cm)
            elements.append(img)
            elements.append(Spacer(1, 12))
        except Exception:
            elements.append(Paragraph("⚠️ Erro ao carregar a imagem.", styleN))
    elif midia.is_video():
        elements.append(Paragraph("⚠️ Este arquivo é um vídeo e não pode ser inserido no PDF.", styleN))
        elements.append(Paragraph(f"Acesse pelo link: {request.build_absolute_uri(midia.arquivo.url)}", styleN))
        elements.append(Spacer(1, 12))

    # Documentos anexados
    if documentos.exists():
        elements.append(Paragraph("<b>📎 Documentos do Navio</b>", styleH))
        lista_docs = [[f"{doc.arquivo.name}"] for doc in documentos]
        docs_table = Table(lista_docs, colWidths=[18*cm])
        docs_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        elements.append(docs_table)

    doc.build(elements)
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"midia_{midia.id}.pdf")
