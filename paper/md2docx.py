"""Convert paper/PAPER.md into a .docx laid out like the Apart hackathon template.

  uv run --no-project --with python-docx --with markdown-it-py python paper/md2docx.py paper/PAPER.md paper/Quiet_Revocations_Leak.docx
"""
import re, sys, copy
from pathlib import Path
from markdown_it import MarkdownIt
from docx import Document
from docx.shared import Pt, Inches, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.part import Part
from docx.opc.packuri import PackURI

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
BASE = SRC.parent
SERIF = "Old Standard TT"
BODY = "Libre Baskerville"
GRAY = RGBColor(0x43, 0x43, 0x43)
LIGHT = RGBColor(0x66, 0x66, 0x66)

text = SRC.read_text()
text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
# drop the internal change list (marked "delete before submitting")
text = re.split(r"\n### Changes made to Mae's draft", text)[0]
lines = text.strip().splitlines()
title = lines[0].lstrip("# ").strip()
# front matter up to the Abstract heading
abs_i = next(i for i, l in enumerate(lines) if l.strip() == "## Abstract")
front = "\n".join(lines[1:abs_i])
body = "\n".join(lines[abs_i:])
subtitle = re.search(r"^\*(.+)\*$", front, re.M).group(1)
authors_line = next(l for l in front.splitlines() if l.startswith("**"))
caveat = re.search(r"^> \*(.+)\*$", front, re.M).group(1)
authors = []
for chunk in authors_line.split(" · "):
    m = re.match(r"\*\*(.+?)\*\*,\s*(.+)", chunk.strip())
    name, aff = m.group(1), m.group(2)
    note = re.search(r"\[.+?\]", aff)
    aff = re.sub(r"\s*\[.+?\]", "", aff)
    authors.append((name + (" " + note.group(0) if note else ""), aff))

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.5), Inches(11)
for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
    setattr(sec, side, Inches(1))

def set_font(style, name, size=None, bold=None, italic=None, color=None):
    f = style.font
    f.name = name
    rpr = style.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts"); rpr.append(rf)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(a), name)
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
        rf.attrib.pop(qn(a), None)
    if size: f.size = Pt(size)
    if bold is not None: f.bold = bold
    if italic is not None: f.italic = italic
    if color is not None: f.color.rgb = color

st = doc.styles
set_font(st["Normal"], BODY, 10)
st["Normal"].paragraph_format.space_after = Pt(6)
st["Normal"].paragraph_format.line_spacing = 1.15
for name, size, color, before, after in (("Heading 1", 14, GRAY, 16, 6), ("Heading 2", 12, LIGHT, 12, 4),
                                         ("Heading 3", 11, GRAY, 10, 4)):
    s = st[name]
    set_font(s, SERIF, size, True, False, color)
    pf = s.paragraph_format
    pf.space_before, pf.space_after, pf.keep_with_next = Pt(before), Pt(after), True
for name in ("List Bullet", "List Bullet 2", "List Number"):
    set_font(st[name], BODY, 10)
    st[name].paragraph_format.space_after = Pt(3)

def border(p, edge, sz, space=1):
    ppr = p._p.get_or_add_pPr()
    bdr = ppr.find(qn("w:pBdr"))
    if bdr is None:
        bdr = OxmlElement("w:pBdr"); ppr.append(bdr)
    e = OxmlElement(f"w:{edge}")
    for k, v in (("val", "single"), ("sz", str(sz)), ("space", str(space)), ("color", "000000")):
        e.set(qn(f"w:{k}"), v)
    bdr.append(e)

def hyperlink(p, url, txt, bold=False, italic=False):
    rid = p.part.relate_to(url, RT.HYPERLINK, is_external=True)
    h = OxmlElement("w:hyperlink"); h.set(qn("r:id"), rid)
    r = OxmlElement("w:r"); rpr = OxmlElement("w:rPr")
    c = OxmlElement("w:color"); c.set(qn("w:val"), "1155CC"); rpr.append(c)
    u = OxmlElement("w:u"); u.set(qn("w:val"), "single"); rpr.append(u)
    if bold: rpr.append(OxmlElement("w:b"))
    if italic: rpr.append(OxmlElement("w:i"))
    r.append(rpr); t = OxmlElement("w:t"); t.text = txt; t.set(qn("xml:space"), "preserve"); r.append(t)
    h.append(r); p._p.append(h)

def add_text(p, s, bold=False, italic=False, code=False, size=None):
    # highlight [square-bracket] to-dos so they are easy to find
    for part in re.split(r"(\[[^\]]+\])", s):
        if not part:
            continue
        r = p.add_run(part)
        r.bold, r.italic = bold or None, italic or None
        if code:
            r.font.name = "Courier New"; r.font.size = Pt((size or 10) - 1)
        elif size:
            r.font.size = Pt(size)
        if re.fullmatch(r"\[[^\]]+\]", part) and not re.fullmatch(r"\[\d+(,\s*\d+)*\]", part):
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW

def inline(p, tok, size=None, base_italic=False):
    bold, italic, link = False, base_italic, None
    for c in tok.children or []:
        t = c.type
        if t == "strong_open": bold = True
        elif t == "strong_close": bold = False
        elif t == "em_open": italic = True
        elif t == "em_close": italic = base_italic
        elif t == "link_open": link = c.attrs.get("href")
        elif t == "link_close": link = None
        elif t == "text":
            if link: hyperlink(p, link, c.content, bold, italic)
            else: add_text(p, c.content, bold, italic, size=size)
        elif t == "code_inline": add_text(p, c.content, bold, italic, code=True, size=size)
        elif t in ("softbreak", "hardbreak"): p.add_run(" ")
        elif t == "image":
            img = BASE / c.attrs["src"]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(str(img), width=Inches(5.2))
        elif t in ("html_inline",): pass

# ---------- title block ----------
tp = doc.add_paragraph(); tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
border(tp, "top", 24, 18); tp.paragraph_format.space_before = Pt(24)
r = tp.add_run(title); r.bold = True; r.font.name = SERIF; r.font.size = Pt(18)
footnote_anchor = tp  # footnote reference goes here
sp = doc.add_paragraph(); sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sp.add_run(subtitle); r.italic = True; r.font.name = SERIF; r.font.size = Pt(12)
border(sp, "bottom", 6, 12); sp.paragraph_format.space_after = Pt(18)

tbl = doc.add_table(rows=1, cols=len(authors)); tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
for cell, (name, aff) in zip(tbl.rows[0].cells, authors):
    cell.width = Inches(6.5 / len(authors))
    p = cell.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after = Pt(0)
    add_text(p, name, size=10.5)
    p2 = cell.add_paragraph(); p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_text(p2, aff, size=10)
for txt, b in (("With", True), ("Apart Research", False)):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0); p.paragraph_format.space_before = Pt(8 if b else 0)
    r = p.add_run(txt); r.bold = b; r.font.size = Pt(10.5)

# ---------- footnote part ----------
FN_XML = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
          '<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>'
          '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>'
          '<w:footnote w:id="1"><w:p><w:pPr><w:spacing w:after="0"/></w:pPr>'
          '<w:r><w:rPr><w:vertAlign w:val="superscript"/><w:sz w:val="16"/></w:rPr><w:footnoteRef/></w:r>'
          '<w:r><w:rPr><w:sz w:val="16"/></w:rPr><w:t xml:space="preserve"> Research conducted at the </w:t></w:r>'
          '<w:hyperlink r:id="rIdHack"><w:r><w:rPr><w:color w:val="1155CC"/><w:u w:val="single"/><w:sz w:val="16"/></w:rPr>'
          '<w:t>Swarm Alignment Hackathon</w:t></w:r></w:hyperlink>'
          '<w:r><w:rPr><w:sz w:val="16"/></w:rPr><w:t xml:space="preserve">, November 2026. Track 4 (Multi-Agent Oversight and Control).</w:t></w:r>'
          '</w:p></w:footnote></w:footnotes>')
fn_part = Part(PackURI("/word/footnotes.xml"),
               "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml",
               FN_XML.encode(), doc.part.package)
doc.part.relate_to(fn_part, RT.FOOTNOTES)
r = footnote_anchor.add_run(); rpr = r._r.get_or_add_rPr()
va = OxmlElement("w:vertAlign"); va.set(qn("w:val"), "superscript"); rpr.append(va)
ref = OxmlElement("w:footnoteReference"); ref.set(qn("w:id"), "1"); r._r.append(ref)
# hyperlink relationship inside the footnote part
rid = fn_part.rels.get_or_add_ext_rel(RT.HYPERLINK, "https://apartresearch.com/sprints")
fn_part._blob = FN_XML.replace("rIdHack", rid).encode()

# ---------- body ----------
md = MarkdownIt("commonmark").enable("table")
toks = md.parse(body)
i, list_stack, quote, pending_caption = 0, [], 0, None
ABSTRACT = False

def para_style():
    if list_stack:
        kind, depth = list_stack[-1][0], len(list_stack)
        if kind == "bullet":
            return "List Bullet 2" if depth > 1 else "List Bullet"
    return None

while i < len(toks):
    t = toks[i]
    ty = t.type
    if ty == "heading_open":
        lvl = int(t.tag[1]); txt = toks[i + 1].content
        if txt == "Abstract":
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(16)
            r = p.add_run("Abstract"); r.bold = True; r.font.name = SERIF; r.font.size = Pt(13)
            ABSTRACT = True
        else:
            if ABSTRACT:
                # hackathon caveat closes the front page, then the body starts on a new page
                p = doc.add_paragraph(); p.paragraph_format.left_indent = p.paragraph_format.right_indent = Inches(1.0)
                p.paragraph_format.space_before = Pt(10)
                add_text(p, caveat, italic=True, size=9)
                ABSTRACT = False
            style = {2: "Heading 1", 3: "Heading 2", 4: "Heading 3"}[lvl]
            if lvl == 2 and txt in ("Limitations", "Future Work"):
                style = "Heading 2"
            if txt == "5. Discussion":
                txt = "5. Discussion and Limitations"
            h = doc.add_paragraph(style=style); inline(h, toks[i + 1])
            if txt != toks[i + 1].content:
                for r in h.runs: r.text = ""
                h.runs[0].text = txt
        i += 3; continue
    if ty in ("bullet_list_open", "ordered_list_open"):
        list_stack.append(["bullet" if ty.startswith("bullet") else "ordered", int(t.attrs.get("start", 1) or 1)])
    elif ty in ("bullet_list_close", "ordered_list_close"):
        list_stack.pop()
    elif ty == "blockquote_open": quote += 1
    elif ty == "blockquote_close": quote -= 1
    elif ty == "hr": pass
    elif ty == "paragraph_open":
        inl = toks[i + 1]
        style = para_style()
        p = doc.add_paragraph(style=style) if style else doc.add_paragraph()
        pf = p.paragraph_format
        if list_stack and list_stack[-1][0] == "ordered" and toks[i - 1].type == "list_item_open":
            depth = len(list_stack)
            pf.left_indent, pf.first_line_indent = Inches(0.3 * depth), Inches(-0.25)
            pf.space_after = Pt(3)
            p.add_run(f"{list_stack[-1][1]}. ")
            list_stack[-1][1] += 1
        elif list_stack and toks[i - 1].type != "list_item_open":
            pf.left_indent = Inches(0.3 * len(list_stack))
        if quote:
            pf.left_indent = Inches(0.4); pf.right_indent = Inches(0.3)
        if ABSTRACT:
            pf.left_indent = pf.right_indent = Inches(0.9)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        is_caption = bool(re.match(r"\*\*(Table|Figure) \d+\.\*\*", inl.content))
        inline(p, inl, size=9 if (quote or is_caption) else None)
        if is_caption:
            pf.keep_with_next = inl.content.startswith("**Table")
        i += 3; continue
    elif ty == "table_open":
        # gather rows
        rows, j, cur = [], i + 1, None
        while toks[j].type != "table_close":
            if toks[j].type == "tr_open": cur = []
            elif toks[j].type == "tr_close": rows.append(cur)
            elif toks[j].type == "inline": cur.append(toks[j])
            j += 1
        ncol = len(rows[0])
        lens = [max(len(r[c].content) for r in rows) for c in range(ncol)]
        lens = [min(max(l, 6), 60) for l in lens]
        widths = [6.5 * l / sum(lens) for l in lens]
        tb = doc.add_table(rows=len(rows), cols=ncol); tb.style = "Table Grid"
        tb.alignment = WD_TABLE_ALIGNMENT.CENTER
        for ri, row in enumerate(rows):
            for ci, tok in enumerate(row):
                cell = tb.cell(ri, ci); cell.width = Inches(widths[ci])
                cp = cell.paragraphs[0]; cp.paragraph_format.space_after = Pt(0)
                cp.paragraph_format.line_spacing = 1.0
                inline(cp, tok, size=8.5)
                if ri == 0:
                    for r in cp.runs: r.bold = True
                    tcpr = cell._tc.get_or_add_tcPr(); shd = OxmlElement("w:shd")
                    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), "EFEFEF")
                    tcpr.append(shd)
        doc.add_paragraph().paragraph_format.space_after = Pt(2)
        i = j + 1; continue
    i += 1

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)
print("wrote", OUT)
