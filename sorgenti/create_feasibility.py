"""Rigenera il documento e le anteprime dal testo salvato nella stessa cartella.
Dipendenze: pip install reportlab pymupdf
"""
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'QUERIOGIANETTOEDOARDO.pdf'
styles = getSampleStyleSheet()
for name, font, size, leading, after, color in [
    ('BodyIT', 'Helvetica', 10.5, 14, 8, '#202020'),
    ('TitleIT', 'Helvetica-Bold', 32, 37, 18, '#202020'),
    ('SubIT', 'Helvetica', 15, 21, 14, '#606060'),
    ('SmallIT', 'Helvetica', 9, 12, 0, '#606060'),
    ('SectionIT', 'Helvetica-Bold', 17, 22, 11, '#303030'),
]:
    styles.add(ParagraphStyle(name=name, fontName=font, fontSize=size, leading=leading,
                             spaceAfter=after, textColor=colors.HexColor(color),
                             spaceBefore=14 if name == 'SectionIT' else 0))
story = []
def p(text, style='BodyIT'):
    story.append(Paragraph(text, styles[style]))
def heading(text):
    p(text, 'SectionIT')
def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor('#303030'))
    canvas.setLineWidth(.6)
    canvas.line(48, 45, A4[0]-48, 45)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor('#606060'))
    canvas.drawString(48, 31, 'FAD Downloader | Studio di fattibilità | 2026/2027')
    canvas.drawRightString(A4[0]-48, 31, str(doc.page))
    canvas.restoreState()
p('ITS-ICT PIEMONTE', 'SubIT')
story.append(Spacer(1,70))
p('FAD Downloader', 'TitleIT')
p('Download e organizzazione dei materiali<br/>didattici da Moodle', 'SubIT')
story.append(Spacer(1,24))
p('ANALISI DI FATTIBILITÀ<br/>Progetto per la prova finale', 'SectionIT')
story.append(Spacer(1,45))
rows = [('Studente','Edoardo Querio Gianetto'), ('Scuola','ITS-ICT Piemonte'),
        ('Anno formativo','2026/2027'), ('Materia','Python'), ('Docente','Massimo Papa')]
table = Table([[Paragraph(a,styles['SmallIT']),Paragraph(b,styles['BodyIT'])] for a,b in rows], colWidths=[120,360])
table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),0), ('BOTTOMPADDING',(0,0),(-1,-1),10)]))
story.append(table)
story.append(PageBreak())
source = Path(__file__).with_name('body_natural.txt')
exec(compile(source.read_text(encoding='utf-8-sig'), str(source), 'exec'))
SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=48, leftMargin=48, topMargin=43,
                  bottomMargin=60, title='FAD Downloader - Analisi di fattibilità',
                  author='Edoardo Querio Gianetto').build(story, onFirstPage=footer, onLaterPages=footer)
preview = ROOT / 'anteprime'
preview.mkdir(exist_ok=True)
with pymupdf.open(OUT) as doc:
    for index, page in enumerate(doc,1):
        page.get_pixmap(matrix=pymupdf.Matrix(1.25,1.25)).save(preview / f'fattibilita-{index}.png')
    print(f'PDF generato: {OUT} ({len(doc)} pagine)')
