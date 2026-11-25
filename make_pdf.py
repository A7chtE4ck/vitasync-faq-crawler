import json, collections
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.platypus.tableofcontents import TableOfContents

pdfmetrics.registerFont(TTFont("DV", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVB", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
d = json.load(open("faqs_clean.json", encoding="utf-8"))
by = collections.OrderedDict()
for e in d: by.setdefault(e["source"], []).append(e)

H1 = ParagraphStyle("h1", fontName="DVB", fontSize=16, spaceAfter=8, leading=20, textColor=colors.HexColor("#0b5c4a"))
Q = ParagraphStyle("q", fontName="DVB", fontSize=9.5, leading=12.5, spaceBefore=7)
A = ParagraphStyle("a", fontName="DV", fontSize=8.6, leading=11.5, spaceBefore=2)
M = ParagraphStyle("m", fontName="DV", fontSize=6.8, leading=8.5, textColor=colors.grey, spaceBefore=2)
T = ParagraphStyle("t", fontName="DVB", fontSize=22, leading=28, spaceAfter=10)

class Doc(BaseDocTemplate):
    def __init__(s, fn):
        super().__init__(fn, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm,
                         title="VitaSync – Gesundheits-FAQs", author="VitaSync")
        s.addPageTemplates([PageTemplate(id="p", frames=[Frame(s.leftMargin, s.bottomMargin, s.width, s.height, id="f")], onPage=s.foot)])
    def foot(s, c, doc):
        c.setFont("DV", 7); c.setFillColor(colors.grey)
        c.drawRightString(A4[0]-18*mm, 9*mm, f"Seite {doc.page}")
        c.drawString(18*mm, 9*mm, "VitaSync · Gesundheits-FAQs")
    def afterFlowable(s, f):
        if getattr(f, "_toc", None):
            lvl, text, key = f._toc
            s.notify("TOCEntry", (lvl, text, s.page)); s.canv.bookmarkPage(key); s.canv.addOutlineEntry(text, key, lvl, 0)

story = [Paragraph("VitaSync – Gesundheits-FAQs", T),
         Paragraph(f"{len(d)} geprüfte Frage-Antwort-Paare · {sum(e['lang']=='de' for e in d)} deutsch, {sum(e['lang']=='en' for e in d)} englisch<br/>"
                   "Stand: 25.11.2026 · Inhalte stammen von den jeweils genannten Quellen; Lizenzen vor kommerzieller Nutzung prüfen.", A),
         Spacer(1, 10)]
toc = TableOfContents(); toc.levelStyles = [ParagraphStyle("t0", fontName="DV", fontSize=10, leading=14)]
story += [Paragraph("Inhalt", H1), toc, PageBreak()]
for i, (src, items) in enumerate(by.items()):
    h = Paragraph(f"{escape(src)} ({len(items)})", H1); h._toc = (0, f"{src} ({len(items)})", f"s{i}")
    story.append(h)
    for e in items:
        story.append(KeepTogether([
            Paragraph(f"{e['id']}. {escape(e['question'])}", Q),
            Paragraph(escape(e["answer"]), A),
            Paragraph(f"{e['lang'].upper()} · {escape(e['license'])} · {escape(e['url'])}", M)]))
    story.append(PageBreak())
Doc("/home/claude/VitaSync_Gesundheits-FAQs.pdf").multiBuild(story)
