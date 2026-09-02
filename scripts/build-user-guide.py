from pathlib import Path
import re
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/"docs"/"USER_GUIDE_EN.md"
OUTPUT=ROOT/"docs"/"Nenolink-AI-Marker-User-Guide-EN.pdf"

def header_footer(canvas,doc):
    canvas.saveState(); canvas.setStrokeColor(colors.HexColor("#B81424")); canvas.line(18*mm,282*mm,192*mm,282*mm)
    canvas.setFont("Helvetica",8); canvas.setFillColor(colors.HexColor("#666666")); canvas.drawString(18*mm,10*mm,"Nenolink AI Marker - User Guide")
    canvas.drawRightString(192*mm,10*mm,f"Page {doc.page}"); canvas.restoreState()

def inline(text):
    text=re.sub(r"\*\*(.+?)\*\*",r"<b>\1</b>",text); text=re.sub(r"`(.+?)`",r"<font name='Courier'>\1</font>",text)
    return text.replace("&","&amp;").replace("&amp;lt;","&lt;") if "&" in text else text

def main():
    styles=getSampleStyleSheet(); styles.add(ParagraphStyle(name="CoverTitle",parent=styles["Title"],fontName="Helvetica-Bold",fontSize=28,leading=34,textColor=colors.HexColor("#B81424"),alignment=TA_CENTER,spaceAfter=14))
    styles.add(ParagraphStyle(name="H1x",parent=styles["Heading1"],fontSize=17,leading=21,textColor=colors.HexColor("#B81424"),spaceBefore=12,spaceAfter=7,keepWithNext=True))
    styles.add(ParagraphStyle(name="H2x",parent=styles["Heading2"],fontSize=13,leading=16,textColor=colors.HexColor("#7A0D18"),spaceBefore=9,spaceAfter=5,keepWithNext=True))
    styles.add(ParagraphStyle(name="Bodyx",parent=styles["BodyText"],fontSize=9.2,leading=13.2,spaceAfter=6))
    styles.add(ParagraphStyle(name="Bulletx",parent=styles["Bodyx"],leftIndent=12,firstLineIndent=-7,bulletIndent=3))
    story=[Spacer(1,55*mm),Paragraph("Nenolink AI Marker",styles["CoverTitle"]),Paragraph("User Guide - Version 0.3",ParagraphStyle(name="Sub",parent=styles["Heading2"],alignment=TA_CENTER,textColor=colors.HexColor("#555555"))),Spacer(1,12*mm),Paragraph("A practical guide to visible AI disclosure badges for images and video.",ParagraphStyle(name="Intro",parent=styles["Bodyx"],alignment=TA_CENTER,fontSize=12,leading=18)),Spacer(1,70*mm),Paragraph("(c) Henrik Nielsen - nenolink.com",ParagraphStyle(name="Credit",parent=styles["Bodyx"],alignment=TA_CENTER)),PageBreak()]
    for raw in SOURCE.read_text(encoding="utf-8").splitlines()[4:]:
        line=raw.strip()
        if not line: continue
        if line.startswith("### "): story.append(Paragraph(inline(line[4:]),styles["H2x"]))
        elif line.startswith("## "): story.append(Paragraph(inline(line[3:]),styles["H1x"]))
        elif line.startswith("- "): story.append(Paragraph("- "+inline(line[2:]),styles["Bulletx"]))
        else: story.append(Paragraph(inline(line),styles["Bodyx"]))
    doc=SimpleDocTemplate(str(OUTPUT),pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=19*mm,bottomMargin=17*mm,title="Nenolink AI Marker User Guide",author="Henrik Nielsen")
    doc.build(story,onFirstPage=header_footer,onLaterPages=header_footer)

if __name__=="__main__":main()
