"""Build the current technical review from maintained project documentation.

Usage: python generate_final_review_pdf.py [--output PATH] [--date YYYY-MM-DD]
Optional dependencies: python -m pip install -r requirements-docs.txt
No database access, model loading, network access or training is performed.
"""
from __future__ import annotations

import argparse
from datetime import date
from html import escape
import json
from pathlib import Path
import re
import textwrap

ROOT = Path(__file__).resolve().parent
CHAPTERS = [
    ('Project overview and workflow', 'README.md', ['Setup and first login', 'Repository map', 'Verification', 'Operations and recovery', 'Troubleshooting', 'Documentation', 'Contents']),
    ('System architecture', 'ARCHITECTURE.md', []),
    ('Borrower data contract', 'DATA_DICTIONARY.md', []),
    ('Database and accounting records', 'DATABASE_SCHEMA.md', []),
    ('API contracts', 'API_DOCUMENTATION.md', ['Worked local API journey']),
    ('Machine learning pipeline', 'ML_PIPELINE.md', []),
    ('Model evaluation and limitations', 'MODEL_CARD.md', []),
    ('OraAgent integration', 'INTEGRATION.md', []),
    ('Demonstration procedure', 'DEMO_GUIDE.md', []),
    ('Verification and evidence', 'TESTING.md', []),
    ('Remaining work and priorities', 'PROJECT_ANALYSIS.md', []),
]


def plain(text):
    """Use portable built-in PDF fonts without unsupported Unicode glyphs."""
    replacements = {'₹': 'INR ', '→': ' -> ', '–': '-', '—': ' - ', '−': '-',
                    '’': "'", '‘': "'", '“': '"', '”': '"', '≤': '<=', '≥': '>='}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode('ascii', 'replace').decode('ascii')


def inline(text):
    # Keep local references readable in print instead of linking to local paths.
    text = re.sub(r'\[([^]]+)\]\(([^)]+)\)', r'\1', plain(text))
    text = escape(text)
    text = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', text)
    return re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)


def selected_markdown(path, excluded):
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    result, skip = [], False
    for line in lines:
        if line.startswith('# '):
            continue
        if line.startswith('## '):
            skip = line[3:].strip() in excluded
        if not skip:
            result.append(line)
    return '\n'.join(result)


def build(output, report_date):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak,
            Table, TableStyle, Preformatted, Flowable, KeepTogether)
    except ImportError as exc:
        raise SystemExit('Install optional documentation dependencies: python -m pip install -r requirements-docs.txt') from exc

    navy, teal, grey = colors.HexColor('#16324F'), colors.HexColor('#087F8C'), colors.HexColor('#546575')
    width = A4[0] - 36 * mm
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('BodyDoc', fontName='Helvetica', fontSize=9, leading=13,
        spaceAfter=6, textColor=navy, splitLongWords=True))
    styles.add(ParagraphStyle('TitleDoc', fontName='Helvetica-Bold', fontSize=34, leading=40,
        textColor=navy, spaceAfter=16))
    styles.add(ParagraphStyle('ChapterDoc', fontName='Helvetica-Bold', fontSize=20, leading=25,
        textColor=navy, spaceAfter=14, keepWithNext=True))
    styles.add(ParagraphStyle('SubDoc', fontName='Helvetica-Bold', fontSize=13, leading=17,
        textColor=teal, spaceBefore=10, spaceAfter=7, keepWithNext=True))
    styles.add(ParagraphStyle('SmallHead', parent=styles['SubDoc'], fontSize=10, leading=14))
    styles.add(ParagraphStyle('CellDoc', parent=styles['BodyDoc'], fontSize=7.4, leading=10, spaceAfter=0))
    styles.add(ParagraphStyle('CodeDoc', fontName='Courier', fontSize=7, leading=9,
        spaceBefore=4, spaceAfter=8, textColor=navy))
    styles.add(ParagraphStyle('CaptionDoc', parent=styles['BodyDoc'], fontSize=8, leading=11, textColor=grey))
    styles.add(ParagraphStyle('BodyLead', parent=styles['BodyDoc'], keepWithNext=True))

    class WorkflowDiagram(Flowable):
        def __init__(self):
            super().__init__()
            self.width, self.height = width, 200
        def draw(self):
            c = self.canv
            labels = [('Reviewer login', 'Authenticated session'), ('Create / validate', 'Shared input schema'),
                      ('Assess risk', 'Model + quality rules'), ('Human review', 'Current assessment ID'),
                      ('Commit funding', 'Explicit approval gate'), ('Repayment schedule', 'Saved plan version'),
                      ('Record receipt', 'Exact-cent allocations'), ('Update exposure', 'Actual principal paid'),
                      ('Produce report', 'Saved case evidence')]
            boxw, boxh, gap = (width-24)/3, 48, 12
            for i,(title,subtitle) in enumerate(labels):
                row, col = divmod(i,3)
                x, y = col*(boxw+gap), 145-row*65
                c.setFillColor(colors.HexColor('#EDF5F7')); c.setStrokeColor(teal)
                c.roundRect(x,y,boxw,boxh,5,fill=1,stroke=1)
                c.setFillColor(navy); c.setFont('Helvetica-Bold',9)
                c.drawCentredString(x+boxw/2,y+29,title)
                c.setFont('Helvetica',7); c.drawCentredString(x+boxw/2,y+14,subtitle)
                if col<2:
                    c.line(x+boxw,y+24,x+boxw+gap,y+24)
                    c.line(x+boxw+gap-3,y+27,x+boxw+gap,y+24)
                    c.line(x+boxw+gap-3,y+21,x+boxw+gap,y+24)
            c.setFont('Helvetica',7); c.setFillColor(grey)
            c.drawString(0,0,'Read each row from left to right, then continue on the next row. All financial actions are simulated.')

    def paragraph(text, style='BodyDoc'):
        if style == 'BodyDoc' and text.rstrip().endswith(':'):
            style = 'BodyLead'
        return Paragraph(inline(text), styles[style])

    def markdown_blocks(content):
        lines, blocks, i = content.splitlines(), [], 0
        while i<len(lines):
            line=lines[i].strip()
            if not line:
                i+=1; continue
            if line.startswith('```'):
                language=line[3:].strip(); code=[]; i+=1
                while i<len(lines) and not lines[i].strip().startswith('```'):
                    code.append(plain(lines[i])); i+=1
                i+=1
                if language=='mermaid':
                    # The review uses the vector workflow above; source guides retain
                    # editable component/state/ER Mermaid diagrams for GitHub viewing.
                    continue
                wrapped=[]
                for row in code:
                    wrapped.extend(textwrap.wrap(row, width=94, replace_whitespace=False,
                        drop_whitespace=False) or [''])
                # Split long code blocks into individual rows for safe page breaks.
                for row in wrapped:
                    blocks.append(Preformatted(row, styles['CodeDoc']))
                continue
            if line.startswith('|'):
                rows=[]
                while i<len(lines) and lines[i].strip().startswith('|'):
                    cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                    if not all(re.fullmatch(r':?-+:?',x.replace(' ','')) for x in cells):
                        rows.append(cells)
                    i+=1
                columns=max(map(len,rows))
                rows=[row+['']*(columns-len(row)) for row in rows]
                # A wider first column helps schema names; table cells wrap naturally.
                weights=([1.5]+[1]*(columns-1)) if columns>=5 else [1]*columns
                colwidths=[width*w/sum(weights) for w in weights]
                table=Table([[paragraph(cell,'CellDoc') for cell in row] for row in rows],
                    colWidths=colwidths,repeatRows=1,hAlign='LEFT')
                table.setStyle(TableStyle([
                    ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#DCECEF')),
                    ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F5F8FA')]),
                    ('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#D4DFE5')),
                    ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
                    ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
                blocks.extend([table,Spacer(1,8)])
                continue
            if line.startswith('### '):
                blocks.append(paragraph(line[4:],'SmallHead')); i+=1; continue
            if line.startswith('## '):
                blocks.append(paragraph(line[3:],'SubDoc')); i+=1; continue
            if re.match(r'^(- |\d+\. )',line):
                blocks.append(paragraph(line)); i+=1; continue
            para=[line]; i+=1
            while i<len(lines) and lines[i].strip() and not re.match(r'^(#|\||```|- |\d+\. )',lines[i].strip()):
                para.append(lines[i].strip()); i+=1
            blocks.append(paragraph(' '.join(para)))
        return blocks

    metadata=json.loads((ROOT/'ml/artifacts/model_metrics.json').read_text(encoding='utf-8'))
    story=[Spacer(1,28*mm),paragraph('RISKORA','TitleDoc'),
        paragraph('AI-assisted micro-lending risk assessment and decision support','ChapterDoc'),
        paragraph('Integrated project technical review','SubDoc'),
        paragraph(f'Report date: {report_date.isoformat()} | Model: {metadata["model_metadata"]["model_version"]}'),
        Spacer(1,8*mm),paragraph('Scope and evidence','SubDoc'),
        paragraph('This report documents the integrated reviewer workflow, API, database, model, verification and remaining work. The model uses synthetic data. Funding and receipts represent application records, not bank transfers. Human review remains required.'),
        paragraph('Prepared from maintained repository documentation and the saved model metrics. No student, institution or guide identity has been invented.'),
        Spacer(1,8*mm),paragraph('Student name(s): ____________________________________'),
        paragraph('Registration number(s): ______________________________'),
        paragraph('Institution / course: _________________________________'),
        paragraph('Guide: _____________________________________________'),PageBreak(),
        paragraph('Reading guide','ChapterDoc')]
    for number,(title,source,_) in enumerate(CHAPTERS,1):
        story.append(paragraph(f'{number}. {title} - source: {source}'))
    story.extend([Spacer(1,8),paragraph('Workflow at a glance','SubDoc'),WorkflowDiagram(),
        paragraph('The following chapters are generated from the source guides. Detailed Mermaid component, state and relationship diagrams remain editable in ARCHITECTURE.md and DATABASE_SCHEMA.md. This PDF is a release snapshot; regenerate it when documentation or model metadata changes.','CaptionDoc')])
    for number,(title,source,excluded) in enumerate(CHAPTERS,1):
        story.extend([PageBreak(),paragraph(f'{number}. {title}','ChapterDoc'),
            paragraph(f'Source: {source}','CaptionDoc')])
        story.extend(markdown_blocks(selected_markdown(ROOT/source,excluded)))
    def decorate(canvas,doc):
        canvas.saveState(); canvas.setStrokeColor(colors.HexColor('#D4DFE5'))
        canvas.line(18*mm,17*mm,A4[0]-18*mm,17*mm)
        canvas.setFont('Helvetica',7); canvas.setFillColor(grey)
        canvas.drawString(18*mm,12*mm,'RISKORA | Integrated technical review | Synthetic-data prototype')
        canvas.drawRightString(A4[0]-18*mm,12*mm,f'{doc.page}')
        if doc.page>1:
            canvas.drawString(18*mm,A4[1]-12*mm,'RISKORA - Architecture, workflow, evidence and limitations')
        canvas.restoreState()
    output.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(output),pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,
        topMargin=23*mm,bottomMargin=24*mm,title='RISKORA Integrated Technical Review',
        author='RISKORA project',pageCompression=1)
    doc.build(story,onFirstPage=decorate,onLaterPages=decorate)
    print(f'Generated {output}')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'RISKORA_Final_Review_Document.pdf')
    parser.add_argument('--date',type=date.fromisoformat,default=date(2026,10,10),help='Visible report date (YYYY-MM-DD)')
    args=parser.parse_args(argv)
    build(args.output.resolve(),args.date)


if __name__=='__main__':
    main()
