from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

ROOT = Path(__file__).resolve().parent.parent
GUIDES = {
    "EN": {"source": ROOT/"docs"/"USER_GUIDE_EN.md", "output": ROOT/"docs"/"Nenolink-AI-Marker-User-Guide-EN.pdf", "guide": "User Guide", "version": "Application version: 0.4.0", "language": "Document language: English", "updated": "Updated: 2 September 2026", "publisher": "Publisher: Nenolink", "intro": "A practical guide to visible AI disclosure badges for images and video.", "page": "Page", "font_size": 9.0, "leading": 12.8, "space_after": 5.5},
    "DA": {"source": ROOT/"docs"/"USER_GUIDE_DA.md", "output": ROOT/"docs"/"Nenolink-AI-Marker-User-Guide-DA.pdf", "guide": "Brugervejledning", "version": "Applikationsversion: 0.4.0", "language": "Dokumentsprog: Dansk", "updated": "Opdateret: 2. september 2026", "publisher": "Udgiver: Nenolink", "intro": "En praktisk vejledning til synlige AI-oplysningsbadges på billeder og video.", "page": "Side", "font_size": 8.7, "leading": 12.1, "space_after": 5.0},
}

def inline(text):
    text=text.replace("&","&amp;")
    text=re.sub(r"\*\*(.+?)\*\*",r"<b>\1</b>",text)
    return re.sub(r"`(.+?)`",r"<font name='Courier'>\1</font>",text)

def build_guide(config):
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle",parent=styles["Title"],fontName="Helvetica-Bold",fontSize=28,leading=34,textColor=colors.HexColor("#B81424"),alignment=TA_CENTER,spaceAfter=14))
    styles.add(ParagraphStyle(name="H1x",parent=styles["Heading1"],fontSize=17,leading=21,textColor=colors.HexColor("#B81424"),spaceBefore=12,spaceAfter=7,keepWithNext=True))
    styles.add(ParagraphStyle(name="H2x",parent=styles["Heading2"],fontSize=13,leading=16,textColor=colors.HexColor("#7A0D18"),spaceBefore=9,spaceAfter=5,keepWithNext=True))
    styles.add(ParagraphStyle(name="Bodyx",parent=styles["BodyText"],fontSize=config["font_size"],leading=config["leading"],spaceAfter=config["space_after"]))
    styles.add(ParagraphStyle(name="Bulletx",parent=styles["Bodyx"],leftIndent=12,firstLineIndent=-7,bulletIndent=3))
    styles.add(ParagraphStyle(name="Notice",parent=styles["Bodyx"],leftIndent=10,rightIndent=10,borderColor=colors.HexColor("#B81424"),borderWidth=1,borderPadding=8,backColor=colors.HexColor("#FFF3F4"),spaceBefore=5,spaceAfter=10))
    centered=ParagraphStyle(name="Centered",parent=styles["Bodyx"],alignment=TA_CENTER,fontSize=10.5,leading=16)
    subtitle=ParagraphStyle(name="Subtitle",parent=styles["Heading2"],alignment=TA_CENTER,fontSize=18,textColor=colors.HexColor("#555555"))
    intro=ParagraphStyle(name="Intro",parent=centered,fontSize=12,leading=18)
    story=[Spacer(1,42*mm),Paragraph("Nenolink AI Marker",styles["CoverTitle"]),Paragraph(config["guide"],subtitle),Spacer(1,10*mm),Paragraph(config["version"],centered),Paragraph(config["language"],centered),Paragraph(config["updated"],centered),Paragraph(config["publisher"],centered),Paragraph("Denmark",centered),Spacer(1,13*mm),Paragraph(config["intro"],intro),Spacer(1,48*mm),Paragraph("(c) Henrik Nielsen - nenolink.com",centered),PageBreak()]
    started=False
    for raw in config["source"].read_text(encoding="utf-8").splitlines():
        line=raw.strip()
        if line.startswith("## "):started=True
        if not started or not line:continue
        if line.startswith("> "):story.append(Paragraph(inline(line[2:]),styles["Notice"]))
        elif line.startswith("### "):story.append(Paragraph(inline(line[4:]),styles["H2x"]))
        elif line.startswith("## "):story.append(Paragraph(inline(line[3:]),styles["H1x"]))
        elif line.startswith("- "):story.append(Paragraph("- "+inline(line[2:]),styles["Bulletx"]))
        else:story.append(Paragraph(inline(line),styles["Bodyx"]))
    def header_footer(canvas,doc):
        canvas.saveState(); canvas.setStrokeColor(colors.HexColor("#B81424")); canvas.line(18*mm,282*mm,192*mm,282*mm)
        canvas.setFont("Helvetica",8); canvas.setFillColor(colors.HexColor("#666666")); canvas.drawString(18*mm,10*mm,f"Nenolink AI Marker - {config['guide']}"); canvas.drawRightString(192*mm,10*mm,f"{config['page']} {doc.page}"); canvas.restoreState()
    doc=SimpleDocTemplate(str(config["output"]),pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=19*mm,bottomMargin=17*mm,title=f"Nenolink AI Marker {config['guide']}",author="Nenolink")
    doc.build(story,onFirstPage=header_footer,onLaterPages=header_footer)

def main():
    for config in GUIDES.values():build_guide(config)

if __name__=="__main__":main()
