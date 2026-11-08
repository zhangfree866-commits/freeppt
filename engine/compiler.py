"""Render laid-out tree to native .pptx via python-pptx."""

from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.oxml.ns import qn
from .layout import _img_path
from . import themes as _themes
from . import icons as _icons

EMU_PER_PX = 914400 / 96.0
ALIGN = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
VALIGN = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE,
          "bottom": MSO_ANCHOR.BOTTOM}
CHART_TYPES = {
    "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "bar": XL_CHART_TYPE.BAR_CLUSTERED,
    "line": XL_CHART_TYPE.LINE,
    "pie": XL_CHART_TYPE.PIE,
}


def E(px):
    return Emu(int(round(px * EMU_PER_PX)))


def rgb(hx):
    hx = hx.lstrip("#")
    return RGBColor(int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16))


def _vis():
    return _themes.get_active()["visual"]


def _sem(role, default):
    return _themes.get_active()["semantic"].get(role, default)


def _is_heading(node, size=None):
    """Heuristic for heading typeface: explicit title role or large bold run."""
    if node.get("role") == "title":
        return True
    s = size if size is not None else node.get("size", 0)
    return node.get("weight") == "bold" and s >= 28


def _apply_typeface(run, heading=False):
    """Set latin + east-asian + complex-script typefaces from the active theme."""
    vis = _vis()
    if heading:
        latin, ea = vis["latin_heading"], vis["ea_heading"]
    else:
        latin, ea = vis["latin_body"], vis["ea_body"]
    run.font.name = latin
    rPr = run._r.get_or_add_rPr()
    ea_el = rPr.find(qn("a:ea"))
    if ea_el is None:
        ea_el = rPr.makeelement(qn("a:ea"), {})
        rPr.append(ea_el)
    ea_el.set("typeface", ea)
    cs = rPr.find(qn("a:cs"))
    if cs is None:
        cs = rPr.makeelement(qn("a:cs"), {})
        rPr.append(cs)
    cs.set("typeface", latin)


def set_ea(run, font=None):
    # Backward-compatible wrapper; body typeface by default.
    _apply_typeface(run, heading=False)


def add_text(slide, node, color_default):
    x, y, w, h = node["_rect"]
    tb = slide.shapes.add_textbox(E(x), E(y), E(w), E(max(h, 10)))
    if node.get("rotate") is not None:
        tb.rotation = float(node["rotate"])
    tf = tb.text_frame
    tf.word_wrap = node.get("wrap", True)
    tf.vertical_anchor = VALIGN.get(node.get("valign", "top"), MSO_ANCHOR.TOP)
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    size = node.get("size", 20)
    color = node.get("color", color_default)
    bold = node.get("weight") == "bold"
    align = ALIGN.get(node.get("align", "left"), PP_ALIGN.LEFT)
    lines = node.get("_lines") or [node.get("text", "")]
    heading = _is_heading(node, size)
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = _vis()["line_spacing"]
        r = p.add_run()
        r.text = line
        r.font.size = Pt(size * 72 / 96.0)
        r.font.bold = bold
        r.font.color.rgb = rgb(color)
        _apply_typeface(r, heading=heading)
        if node.get("opacity") is not None:
            _set_run_alpha(r, node["opacity"])


def _text_w_px(text, size):
    """Estimate rendered width: CJK ~1.02em, latin/digit ~0.56em."""
    return sum(size * (1.02 if ord(ch) >= 0x2E80 else 0.56)
               for ch in str(text))


def _fit_size(text, size, avail_w, floor=36):
    """Shrink a font size until the text fits avail_w (px), with a floor."""
    if _text_w_px(text, size) <= avail_w:
        return size
    scaled = size * avail_w / _text_w_px(text, size)
    return max(floor, int(scaled))


def add_kpi(slide, node, color_default):
    x, y, w, h = node["_rect"]
    tb = slide.shapes.add_textbox(E(x), E(y), E(w), E(max(h, 10)))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    vs = node.get("vsize", node.get("size", 96))
    vs = _fit_size(node.get("value", ""), vs, w * 0.92)  # long values auto-shrink
    vcolor = node.get("color", color_default)
    p = tf.paragraphs[0]
    p.alignment = ALIGN.get(node.get("align", "left"), PP_ALIGN.LEFT)
    r = p.add_run()
    r.text = str(node.get("value", ""))
    r.font.size = Pt(vs * 72 / 96.0)
    r.font.bold = True
    r.font.color.rgb = rgb(vcolor)
    _apply_typeface(r, heading=True)
    label = node.get("label")
    if label:
        p2 = tf.add_paragraph()
        p2.alignment = p.alignment
        r2 = p2.add_run()
        r2.text = label
        r2.font.size = Pt(node.get("lsize", 18) * 72 / 96.0)
        r2.font.color.rgb = rgb(node.get("lcolor", _sem("body", "#44546A")))
        _apply_typeface(r2, heading=False)


def _effective_radius(node):
    """Explicit node radius wins; else the theme card radius (cards only)."""
    if node.get("radius") is not None:
        return node["radius"]
    if node.get("t") == "card":
        return _vis().get("radius", 0)
    return 0


def add_rect(slide, node):
    x, y, w, h = node["_rect"]
    radius = _effective_radius(node)
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius and radius > 0 else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(kind, E(x), E(y), E(w), E(max(h, 1)))
    _apply_fill(shape, node)
    border = node.get("border")
    if border:
        shape.line.color.rgb = rgb(border)
        shape.line.width = Pt(1)
        if node.get("border_opacity") is not None:
            _set_line_alpha(shape, node["border_opacity"])
    else:
        shape.line.fill.background()
    shape.shadow.inherit = False
    if kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        # adjustment is a fraction of the shorter edge; cap to keep corners sane
        shape.adjustments[0] = min(0.16, radius / max(min(w, h), 1))
    if node.get("rotate") is not None:
        shape.rotation = float(node["rotate"])
    return shape


def add_divider(slide, node):
    x, y, w, h = node["_rect"]
    if node.get("vertical"):
        conn = slide.shapes.add_connector(1, E(x), E(y), E(x), E(y + h))
    else:
        conn = slide.shapes.add_connector(1, E(x), E(y), E(x + w), E(y))
    conn.line.color.rgb = rgb(node.get("color", _sem("ink", "#061F32")))
    conn.line.width = Pt(node.get("thickness", 1.25))
    return conn


def _set_fill_alpha(shape, pct):
    """pct = opacity 0..100. Injects a:alpha into the solidFill srgbClr."""
    spPr = shape.fill._xPr.find(qn("a:solidFill"))
    if spPr is None:
        return
    clr = spPr.find(qn("a:srgbClr"))
    if clr is None:
        return
    for old in clr.findall(qn("a:alpha")):
        clr.remove(old)
    alpha = clr.makeelement(qn("a:alpha"), {"val": str(int(pct * 1000))})
    clr.append(alpha)


_FILL_TAGS = ("a:noFill", "a:solidFill", "a:gradFill", "a:blipFill",
              "a:pattFill", "a:grpFill")


def _set_gradient(shape, grad):
    """Inject an OOXML gradFill.

    grad = {"stops": [{"color": "#RRGGBB", "pos": 0..100000,
                       "opacity": 0..100 (optional)}],
            "angle": degrees (0 = left-to-right, 90 = top-to-bottom)}
    Replaces any existing fill on the shape. Deterministic, no network.
    """
    spPr = shape._element.spPr
    for tag in _FILL_TAGS:
        for el in spPr.findall(qn(tag)):
            spPr.remove(el)
    grad_fill = spPr.makeelement(qn("a:gradFill"), {})
    gs_lst = grad_fill.makeelement(qn("a:gsLst"), {})
    stops = grad.get("stops") or []
    n = max(1, len(stops) - 1)
    for i, st in enumerate(stops):
        pos = st.get("pos")
        if pos is None:
            pos = int(100000 * i / n)
        gs = gs_lst.makeelement(qn("a:gs"), {"pos": str(int(pos))})
        clr = gs.makeelement(qn("a:srgbClr"),
                             {"val": str(st["color"]).lstrip("#").upper()})
        if st.get("opacity") is not None:
            clr.append(clr.makeelement(
                qn("a:alpha"), {"val": str(int(float(st["opacity"]) * 1000))}))
        gs.append(clr)
        gs_lst.append(gs)
    grad_fill.append(gs_lst)
    angle = int(grad.get("angle", 90))
    grad_fill.append(grad_fill.makeelement(
        qn("a:lin"), {"ang": str(angle * 60000), "scaled": "1"}))
    ln = spPr.find(qn("a:ln"))
    if ln is not None:
        ln.addprevious(grad_fill)
    else:
        spPr.append(grad_fill)
    try:
        shape.shadow.inherit = False
    except Exception:
        pass


def _apply_fill(shape, node):
    """Single fill entry point: gradient beats solid; opacity tunes solid."""
    grad = node.get("gradient")
    if grad:
        _set_gradient(shape, grad)
    elif node.get("fill"):
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb(node["fill"])
        if node.get("opacity") is not None:
            _set_fill_alpha(shape, max(0.0, min(100.0, float(node["opacity"]))))
    else:
        shape.fill.background()


def _set_run_alpha(run, pct):
    """Inject a:alpha into a text run's solidFill srgbClr (opacity 0..100)."""
    rPr = run._r.get_or_add_rPr()
    sf = rPr.find(qn("a:solidFill"))
    if sf is None:
        return
    clr = sf.find(qn("a:srgbClr"))
    if clr is None:
        return
    for old in clr.findall(qn("a:alpha")):
        clr.remove(old)
    clr.append(clr.makeelement(
        qn("a:alpha"), {"val": str(int(max(0.0, min(100.0, float(pct))) * 1000))}))


def _set_line_alpha(shape, pct):
    """Inject a:alpha into a shape outline solidFill (opacity 0..100)."""
    ln = shape._element.spPr.find(qn("a:ln"))
    if ln is None:
        return
    clr = ln.find(qn("a:solidFill") + "/" + qn("a:srgbClr"))
    if clr is None:
        return
    for old in clr.findall(qn("a:alpha")):
        clr.remove(old)
    clr.append(clr.makeelement(
        qn("a:alpha"), {"val": str(int(max(0.0, min(100.0, float(pct))) * 1000))}))


SHAPE_KINDS = {
    "oval": MSO_SHAPE.OVAL,
    "chevron": MSO_SHAPE.CHEVRON,
    "arrow": MSO_SHAPE.RIGHT_ARROW,
    "roundrect": MSO_SHAPE.ROUNDED_RECTANGLE,
}

# Logical grid shape names (engine.icons specs) -> native MSO autoshape.
# There is no literal shield in the MSO set; PLAQUE is the closest badge.
ICON_SHAPES = {
    "oval": MSO_SHAPE.OVAL,
    "rect": MSO_SHAPE.RECTANGLE,
    "roundrect": MSO_SHAPE.ROUNDED_RECTANGLE,
    "gear6": MSO_SHAPE.GEAR_6,
    "shield": MSO_SHAPE.PLAQUE,
    "triangle": MSO_SHAPE.ISOSCELES_TRIANGLE,
    "diamond": MSO_SHAPE.DIAMOND,
    "chevron": MSO_SHAPE.CHEVRON,
}


def add_icon(slide, node, color_default):
    """Render a native-shape icon, scaling the 100x100 logical grid to _rect.

    node: {"t": "icon", "name": <canonical or alias>, "color"? ,
           "stroke_w"? , "_rect": [x, y, w, h], ...}
    Every icon is a group of editable autoshapes/lines tinted with one accent
    color, so it stays fully offline and theme-driven (no bitmap/SVG assets).
    """
    from .icons import GRID
    specs = _icons.specs(node.get("name", ""))
    if not specs:
        return None
    x, y, w, h = node["_rect"]
    sx, sy = w / GRID, h / GRID
    color = node.get("color", _sem("accent", "#08A6F6"))
    # Real geometric subtraction is unavailable through OOXML autoshapes, so a
    # knock-out is painted solid in a surface-ish highlight color (white by
    # default, overridable per node) to read as a punched hub/porthole.
    knock_color = node.get("knock_color", "#FFFFFF")
    stroke_w = node.get("stroke_w", 1.75)
    group_shapes = []
    for sp in specs:
        if sp.get("k") == "line":
            conn = slide.shapes.add_connector(
                1,
                E(x + sp["x1"] * sx), E(y + sp["y1"] * sy),
                E(x + sp["x2"] * sx), E(y + sp["y2"] * sy))
            conn.line.color.rgb = rgb(color)
            conn.line.width = Pt(stroke_w)
            group_shapes.append(conn)
            continue
        kind = ICON_SHAPES.get(sp["k"], MSO_SHAPE.OVAL)
        sw, sh = max(1.0, sp["w"] * sx), max(1.0, sp["h"] * sy)
        autoshape = slide.shapes.add_shape(
            kind, E(x + sp["x"] * sx), E(y + sp["y"] * sy),
            E(sw), E(sh))
        autoshape.shadow.inherit = False
        if sp.get("rot") is not None:
            autoshape.rotation = float(sp["rot"])
        # knock-out: a highlight hub/porthole painted on the glyph beneath it
        if sp.get("knock"):
            autoshape.fill.solid()
            autoshape.fill.fore_color.rgb = rgb(knock_color)
            autoshape.line.fill.background()
        elif sp.get("mode") == "stroke":
            autoshape.fill.background()
            autoshape.line.color.rgb = rgb(color)
            autoshape.line.width = Pt(stroke_w)
        else:
            autoshape.fill.solid()
            autoshape.fill.fore_color.rgb = rgb(color)
            autoshape.line.fill.background()
        group_shapes.append(autoshape)
    return group_shapes


def add_richcard(slide, node):
    """One rounded/rect shape carrying several styled paragraphs (animatable)."""
    x, y, w, h = node["_rect"]
    radius = node.get("radius")
    if radius is None:
        radius = _vis().get("radius", 0)
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius and radius > 0 else MSO_SHAPE.RECTANGLE
    sh = slide.shapes.add_shape(kind, E(x), E(y), E(w), E(h))
    if kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = min(0.16, radius / max(min(w, h), 1))
    _apply_fill(sh, node)
    if node.get("border"):
        sh.line.color.rgb = rgb(node["border"])
        sh.line.width = Pt(1)
        if node.get("border_opacity") is not None:
            _set_line_alpha(sh, node["border_opacity"])
    else:
        sh.line.fill.background()
    sh.shadow.inherit = False
    if node.get("rotate") is not None:
        sh.rotation = float(node["rotate"])
    _name(sh, node)
    pad = node.get("padding", 24)
    avail_w = w - 2 * pad
    tf = sh.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = tf.margin_right = E(pad)
    tf.margin_top = tf.margin_bottom = E(16)
    for i, b in enumerate(node.get("blocks", [])):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = ALIGN.get(b.get("align", "left"), PP_ALIGN.LEFT)
        p.line_spacing = _vis()["line_spacing"]
        if i:
            p.space_before = Pt(b.get("space_before", 10))
        r = p.add_run()
        r.text = b.get("text", "")
        bsize = b.get("size", 18)
        if bsize >= 48:  # KPI-style display run: keep on one line, shrink to fit
            bsize = _fit_size(b.get("text", ""), bsize, avail_w, floor=36)
        r.font.size = Pt(bsize * 72 / 96.0)
        r.font.bold = b.get("weight") == "bold"
        r.font.color.rgb = rgb(b.get("color", _sem("body", "#44546A")))
        _apply_typeface(r, heading=_is_heading(b, bsize))
        if b.get("opacity") is not None:
            _set_run_alpha(r, b["opacity"])
    return sh


def add_shape_node(slide, node, color_default):
    x, y, w, h = node["_rect"]
    kind = node.get("kind", "oval")
    sh = slide.shapes.add_shape(SHAPE_KINDS.get(kind, MSO_SHAPE.OVAL),
                                E(x), E(y), E(w), E(max(h, 10)))
    eff = dict(node)
    if "fill" not in eff and "gradient" not in eff:
        eff["fill"] = color_default
    _apply_fill(sh, eff)
    if node.get("border"):
        sh.line.color.rgb = rgb(node["border"])
        sh.line.width = Pt(1)
        if node.get("border_opacity") is not None:
            _set_line_alpha(sh, node["border_opacity"])
    else:
        sh.line.fill.background()
    sh.shadow.inherit = False
    if node.get("rotate") is not None:
        sh.rotation = float(node["rotate"])
    _name(sh, node)
    label = node.get("text")
    if label:
        tf = sh.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 2
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = str(label)
        r.font.size = Pt(node.get("size_text", 18) * 72 / 96.0)
        r.font.bold = True
        r.font.color.rgb = rgb(node.get("text_color", _sem("ink_on_dark", "#FFFFFF")))
        _apply_typeface(r, heading=False)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE


def add_image(slide, node):
    x, y, w, h = node["_rect"]
    pic = slide.shapes.add_picture(_img_path(node), E(x), E(y),
                                   width=E(w), height=E(h))
    if node.get("fit", "cover") == "cover":
        # center-cover: crop source so it matches the box aspect ratio
        iw, ih = pic.image.size
        src_ar, box_ar = iw / ih, w / h
        if box_ar > src_ar:  # box wider -> crop top/bottom
            keep = src_ar / box_ar
            crop = (1 - keep) / 2
            pic.crop_top = crop
            pic.crop_bottom = crop
        else:  # box taller -> crop left/right
            keep = box_ar / src_ar
            crop = (1 - keep) / 2
            pic.crop_left = crop
            pic.crop_right = crop
    return pic


def add_chart(slide, node):
    x, y, w, h = node["_rect"]
    data = CategoryChartData()
    data.categories = node.get("categories", [])
    for s in node.get("series", []):
        data.add_series(s.get("name", ""), tuple(s.get("values", [])))
    ctype = CHART_TYPES.get(node.get("kind", "column"), XL_CHART_TYPE.COLUMN_CLUSTERED)
    gf = slide.shapes.add_chart(ctype, E(x), E(y), E(w), E(max(h, 60)), data)
    _name(gf, node)
    chart = gf.chart
    chart.has_legend = node.get("legend", True) and len(node.get("series", [])) > 1
    if chart.has_legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(12)
    colors = node.get("colors", _vis().get("chart_colors",
                                   ["#061F32", "#08A6F6", "#99BDED"]))
    plot = chart.plots[0]
    plot.gap_width = _vis().get("chart_gap_width", 80)
    for i, ser in enumerate(chart.series):
        c = colors[i % len(colors)]
        if node.get("kind") == "line":
            ser.format.line.color.rgb = rgb(c)
            ser.format.line.width = Pt(2.25)
        else:
            ser.format.fill.solid()
            ser.format.fill.fore_color.rgb = rgb(c)
    try:
        cat_ax = chart.category_axis
        cat_ax.tick_labels.font.size = Pt(12)
        val_ax = chart.value_axis
        val_ax.tick_labels.font.size = Pt(12)
        axis_c = _sem("muted", "#808080")
        val_ax.format.line.color.rgb = rgb(axis_c)
        cat_ax.format.line.color.rgb = rgb(axis_c)
    except Exception:
        pass
    return chart


def add_table(slide, node):
    """Render a native editable table; styling comes from DSL/theme tokens."""
    x, y, w, h = node["_rect"]
    headers = node.get("headers", [])
    rows = node.get("rows", [])
    ncols = len(headers)
    if ncols == 0:
        return None
    nrows = len(rows) + 1
    gf = slide.shapes.add_table(nrows, ncols, E(x), E(y), E(w), E(max(h, 60)))
    _name(gf, node)
    table = gf.table
    # disable the built-in banded style so our explicit fills are authoritative
    try:
        table.first_row = False
        table.horz_banding = False
    except Exception:
        pass
    hfill = node.get("header_fill", _sem("surface_dark", "#061F32"))
    hcolor = node.get("header_color", _sem("ink_on_dark", "#FFFFFF"))
    body_color = node.get("body_color", _sem("ink", "#061F32"))
    for j, head in enumerate(headers):
        cell = table.cell(0, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = rgb(hfill)
        cell.margin_left = cell.margin_right = E(10)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]
        r = p.add_run()
        r.text = str(head)
        r.font.size = Pt(16)
        r.font.bold = True
        r.font.color.rgb = rgb(hcolor)
        _apply_typeface(r, heading=True)
    for i, row in enumerate(rows, start=1):
        for j in range(ncols):
            val = row[j] if j < len(row) else ""
            cell = table.cell(i, j)
            if node.get("zebra") and i % 2 == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = rgb(node["zebra"])
            cell.margin_left = cell.margin_right = E(10)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.text_frame.word_wrap = True
            r = cell.text_frame.paragraphs[0].add_run()
            r.text = str(val)
            r.font.size = Pt(15)
            r.font.color.rgb = rgb(body_color)
            _apply_typeface(r, heading=False)
    return table


def _name(shape, node):
    if node.get("_name"):
        try:
            shape.name = node["_name"]
        except Exception:
            pass


def add_notes(slide, text):
    """Write speaker notes to the slide's notes master placeholder."""
    if not text:
        return
    notes_tf = slide.notes_slide.notes_text_frame
    notes_tf.text = str(text)
    for para in notes_tf.paragraphs:
        for r in para.runs:
            _apply_typeface(r, heading=False)


def render_node(slide, node, color_default, freeform=False):
    t = node["t"]
    if t in ("card", "box"):
        # Boxes are transparent in legacy masters; on a freeform canvas a
        # filled box IS a designed color block, so it must be rendered.
        if t == "card" or (freeform and node.get("fill")):
            _name(add_rect(slide, node), node)
        for k in node.get("children", []):
            render_node(slide, k, color_default, freeform)
    elif t == "text":
        _name(add_text(slide, node, color_default), node)
    elif t == "kpi":
        _name(add_kpi(slide, node, color_default), node)
    elif t == "divider":
        _name(add_divider(slide, node), node)
    elif t == "chart":
        add_chart(slide, node)  # name applied inside via graphicFrame
    elif t == "table":
        add_table(slide, node)
    elif t == "image":
        _name(add_image(slide, node), node)
    elif t == "shape":
        add_shape_node(slide, node, color_default)
    elif t == "richcard":
        add_richcard(slide, node)
    elif t == "icon":
        add_icon(slide, node, color_default)


def build_pptx(deck, out_path, force=False):
    from .animator import apply_animations
    prs = Presentation()
    prs.slide_width = E(1280)
    prs.slide_height = E(720)
    blank = prs.slide_layouts[6]
    metas = []
    for sdef in deck["slides"]:
        root = sdef["_root"]
        slide = prs.slides.add_slide(blank)
        # full-bleed background image (optional), then base fill / overlay
        pic_el = None
        if root.get("bg_image"):
            pic = slide.shapes.add_picture(_img_path({"src": root["bg_image"]}), 0, 0,
                                           width=prs.slide_width,
                                           height=prs.slide_height)
            pic_el = pic._element
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width,
                                    prs.slide_height)
        if root.get("gradient") and pic_el is None:
            _set_gradient(bg, root["gradient"])
        else:
            bg.fill.solid()
            bg.fill.fore_color.rgb = rgb(root.get("fill", _sem("surface_light", "#FFFFFF")))
            if pic_el is not None:
                # image cover: make the base rect a semi-transparent navy overlay
                _set_fill_alpha(bg, root.get("bg_overlay", 55))
        bg.line.fill.background()
        bg.shadow.inherit = False
        # send overlay rect and bg image to back
        for el in ([bg._element] + ([pic_el] if pic_el is not None else [])):
            el.getparent().remove(el)
            slide.shapes._spTree.insert(2, el)
        text_default = _sem("ink_on_dark", "#FFFFFF") if root["dark"] else _sem("ink", "#061F32")
        freeform = root.get("composition") == "freeform"
        for child in root.get("children", []):
            render_node(slide, child, text_default, freeform)
        # fixed skeleton nodes (title / title-rule / footer) on light slides
        for fl in root.get("_float", []):
            if fl["t"] == "divider":
                add_divider(slide, fl)
            elif fl["t"] == "text":
                add_text(slide, fl, text_default)
        # speaker notes (offline deliverable; never rendered on the slide)
        if sdef.get("notes"):
            add_notes(slide, sdef["notes"])
        metas.append({"anims": sdef.get("anims"),
                      "transition": sdef.get("transition")})
    apply_animations(prs, metas)
    if force and deck.get("composed"):
        # A forced build bypassed the lint gate on purpose. Stamp the artifact
        # so the bypass is visible in the file itself, not only in shell history.
        try:
            prs.core_properties.subject = "FreePPT forced build (lint --force)"
            first = prs.slides[0]
            box = first.shapes.add_textbox(E(24), E(692), E(760), E(22))
            box.name = "FreePPTForcedBuildMarker"
            run = box.text_frame.paragraphs[0].add_run()
            run.text = ("FORCED BUILD: lint diagnostics were bypassed with "
                        "--force; layout quality is not guaranteed.")
            run.font.size = Pt(10)
            run.font.color.rgb = rgb(_sem("muted", "#808080"))
            _apply_typeface(run, heading=False)
        except Exception:
            pass
    prs.save(out_path)
    return out_path
