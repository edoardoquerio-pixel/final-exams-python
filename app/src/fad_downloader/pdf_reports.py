"""ReportLab: report personale dei download letti dal database SQLite."""

from collections import Counter
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import reportlab

from .observability import event, monitored
from .storage import SafeRoot


def display_text(value):
    return escape(str(value))


@monitored("report.pdf")
def export_user_report(archive, session, destination):
    rows = archive.history(session)
    output = BytesIO()
    fonts = Path(reportlab.__file__).parent / "fonts"
    pdfmetrics.registerFont(TTFont("FadSans", str(fonts / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont("FadSansBold", str(fonts / "VeraBd.ttf")))
    pdfmetrics.registerFontFamily(
        "FadSans", normal="FadSans", bold="FadSansBold", italic="FadSans", boldItalic="FadSansBold"
    )
    styles = getSampleStyleSheet()
    for name in ("Normal", "Title", "Heading2"):
        styles[name].fontName = "FadSansBold" if name in {"Title", "Heading2"} else "FadSans"
    styles.add(
        ParagraphStyle(name="Cell", fontName="FadSans", fontSize=8, leading=11, wordWrap="CJK")
    )
    styles.add(
        ParagraphStyle(
            name="Caption",
            fontName="FadSans",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#536275"),
        )
    )
    story = [
        Paragraph("FAD Downloader", styles["Title"]),
        Paragraph("Report personale dei download", styles["Heading2"]),
        Paragraph("Utente DB: <b>" + display_text(session.username) + "</b>", styles["Normal"]),
        Paragraph(
            "Generato il " + datetime.now().astimezone().strftime("%d/%m/%Y alle %H:%M %Z"),
            styles["Caption"],
        ),
        Spacer(1, 6 * mm),
    ]
    successes = [
        r for r in rows if r["status"] in {"scaricato", "aggiornato", "invariato", "importato"}
    ]
    story.append(
        Paragraph(
            f"Operazioni registrate: {len(rows)}. Risorse archiviate: {len(successes)}. File associati: {sum(r['file_count'] for r in successes)}.",
            styles["Normal"],
        )
    )
    story.append(
        Paragraph(
            "Lo storico comprende anche aggiornamenti e ripetizioni. Gli esiti non riusciti sono indicati separatamente. I contenuti BLOB non sono incorporati nel PDF.",
            styles["Caption"],
        )
    )
    for status, count in sorted(Counter(r["status"] for r in rows).items()):
        story.append(Paragraph(display_text(status) + ": " + str(count), styles["Caption"]))
    story.append(Spacer(1, 6 * mm))
    if not rows:
        story.append(Paragraph("Nessun download registrato per questo utente.", styles["Normal"]))
    else:

        def cell(value):
            return Paragraph(display_text(value), styles["Cell"])

        data = [[cell(v) for v in ("Data UTC", "Corso / risorsa", "Esito", "File / byte")]]
        for row in rows:
            # Limita una cella: il titolo completo resta nel DB; una riga non supera una pagina.
            title = row["course"][:200] + "\n" + row["name"][:300]
            data.append(
                [
                    cell(row["created"][:19].replace("T", " ")),
                    cell(title),
                    cell(row["status"]),
                    cell(f"{row['file_count']} / {row['size']}"),
                ]
            )
        table = Table(
            data, colWidths=[33 * mm, 84 * mm, 33 * mm, 26 * mm], repeatRows=1, hAlign="LEFT"
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e3eaf3")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f4f7fb")],
                    ),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#9eafc5")),
                ]
            )
        )
        story.append(table)

    def page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#536275"))
        canvas.drawString(17 * mm, 12 * mm, "FAD Downloader - report utente DB")
        canvas.drawRightString(193 * mm, 12 * mm, "Pagina " + str(doc.page))
        canvas.restoreState()

    SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=17 * mm,
        rightMargin=17 * mm,
        topMargin=16 * mm,
        bottomMargin=21 * mm,
        title="Report download utente",
        author="FAD Downloader",
    ).build(story, onFirstPage=page, onLaterPages=page)
    destination = Path(destination).absolute()
    SafeRoot(destination.parent).write(destination.name, [output.getvalue()], expected=None)
    event("report.pdf_created", resources=len(rows))
    return destination
