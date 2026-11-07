"""FreePPT visual theme registry.

A theme is the visual superset of the old `scenario`. Every theme carries:
  - lint contract keys: palette / font / min_body / layout_min_chars / no_footer
  - semantic colors used by layout + templates + compiler
  - visual tokens: typeface pairing, radius, shadow level, line spacing,
    chart color sequence, accent-area budget, density strategy, grid columns

The `consulting` theme is pinned to the exact legacy hard-coded values so
existing decks render identically (zero regression). New themes unlock
distinct visual languages while reusing the same deterministic engine.

All hex values are normalized to upper-case inside `palette` for lint matching.
"""

# ---- legacy palette (pinned; do not change without a migration) -------------
_CONSULTING = {
    "navy": "#061F32", "royal": "#001965", "cyan": "#08A6F6",
    "light": "#99BDED", "wine": "#5A0E13", "green": "#177B57",
    "orange": "#F47B39", "gray": "#44546A", "mid": "#808080",
    "line": "#E5E7EB", "white": "#FFFFFF",
}


def _palette(*hexes):
    return {h.upper() for h in hexes}


def _theme(name, label, semantic, visual, extra_palette=None,
           min_body=18, layout_min_chars=None, no_footer=None, font=None):
    """Build a normalized theme dict.

    semantic: role -> hex (lower-case in source, roles documented below).
    visual: non-color tokens (fonts, radius, shadow, spacing...).
    """
    layout_min_chars = layout_min_chars or {
        "cover": 20, "toc": 80, "section": 14, "closing": 0}
    no_footer = no_footer or {"cover", "toc", "section", "closing"}
    palette = _palette(*list(semantic.values()) + list(extra_palette or []))
    return {
        "name": name,
        "label": label,
        "palette": palette,
        "font": font or visual.get("font_body"),
        "min_body": min_body,
        "layout_min_chars": layout_min_chars,
        "no_footer": no_footer,
        "semantic": semantic,
        "visual": visual,
    }


# Visual token defaults shared unless a theme overrides.
_BASE_VISUAL = {
    "font_heading": 'Arial,"PingFang SC","Microsoft YaHei",sans-serif',
    "font_body": 'Arial,"PingFang SC","Microsoft YaHei",sans-serif',
    "latin_heading": "Arial",       # concrete OOXML latin typeface
    "ea_heading": "PingFang SC",    # east-asian typeface
    "latin_body": "Arial",
    "ea_body": "PingFang SC",
    "serif_heading": False,
    "radius": 8,                    # card corner radius (px); 0 = square
    "shadow": "none",               # none | soft | medium
    "line_spacing": 1.15,
    "accent_budget": 0.08,          # max share of canvas for accent fills
    "density": "strict",            # strict | relaxed
    "grid_columns": 12,
    "chart_gap_width": 80,
}


def _vis(**overrides):
    v = dict(_BASE_VISUAL)
    v.update(overrides)
    return v


THEMES = {}

# 1) consulting — legacy look, pinned for zero regression.
THEMES["consulting"] = _theme(
    "consulting", "咨询商务（经典蓝）",
    semantic={
        "surface_dark": _CONSULTING["navy"], "surface_light": _CONSULTING["white"],
        "card_fill": _CONSULTING["white"], "ink": _CONSULTING["navy"],
        "ink_on_dark": _CONSULTING["white"], "body": _CONSULTING["gray"],
        "muted": _CONSULTING["mid"], "line": _CONSULTING["line"],
        "accent": _CONSULTING["cyan"], "accent_2": _CONSULTING["royal"],
        "accent_soft": _CONSULTING["light"],
    },
    visual=_vis(radius=0,  # legacy cards are square; keep pixel-identical
                chart_colors=[_CONSULTING["navy"], _CONSULTING["cyan"],
                              _CONSULTING["light"]]),
    extra_palette=list(_CONSULTING.values()),
    font='Arial,"PingFang SC","Microsoft YaHei","Noto Sans SC",sans-serif',
)

# 2) general — permissive fallback (no locked palette), same geometry.
_general = dict(THEMES["consulting"])
_general.update({
    "name": "general", "label": "通用（不锁色）", "palette": None,
    "font": '"PingFang SC","Microsoft YaHei","Noto Sans SC",Arial,sans-serif',
})
THEMES["general"] = _general

# 3) magazine — editorial: warm paper, ink black, terracotta, serif headings.
_mag_sem = {
    "surface_dark": "#1C1917", "surface_light": "#FAF7F2",
    "card_fill": "#FFFFFF", "ink": "#1C1917", "ink_on_dark": "#FAF7F2",
    "body": "#3F3A35", "muted": "#8A8178", "line": "#E3DCD2",
    "accent": "#9A3412", "accent_2": "#1E3A5F", "accent_soft": "#E7D8C9",
}
THEMES["magazine"] = _theme(
    "magazine", "杂志编辑风（暖纸·衬线·赤陶）",
    semantic=_mag_sem,
    visual=_vis(
        font_heading='"Songti SC","SimSun",Georgia,serif',
        latin_heading="Georgia", ea_heading="Songti SC", serif_heading=True,
        radius=2, shadow="none", line_spacing=1.32,
        density="relaxed", accent_budget=0.06,
        chart_colors=["#9A3412", "#1E3A5F", "#C8A27C"],
    ),
    extra_palette=["#C8A27C", "#FFFFFF"],
)

# 4) tech — dark covers with neon cyan on cool light-grey content pages.
_tech_sem = {
    "surface_dark": "#0A1628", "surface_light": "#F4F7FB",
    "card_fill": "#FFFFFF", "ink": "#0F1B2D", "ink_on_dark": "#EAF2FF",
    "body": "#334155", "muted": "#64748B", "line": "#D8E2EF",
    "accent": "#0891B2", "accent_2": "#2563EB", "accent_soft": "#BAE6FD",
}
THEMES["tech"] = _theme(
    "tech", "深色科技（霓虹青·冷灰）",
    semantic=_tech_sem,
    visual=_vis(
        radius=10, shadow="soft", line_spacing=1.18,
        accent_budget=0.10,
        chart_colors=["#0891B2", "#2563EB", "#7DD3FC"],
    ),
    extra_palette=["#7DD3FC", "#FFFFFF"],
)

# 5) swiss — international typographic style: B/W/grey + one red, square.
_swiss_sem = {
    "surface_dark": "#111111", "surface_light": "#FFFFFF",
    "card_fill": "#FFFFFF", "ink": "#111111", "ink_on_dark": "#FFFFFF",
    "body": "#2B2B2B", "muted": "#767676", "line": "#E0E0E0",
    "accent": "#E63312", "accent_2": "#111111", "accent_soft": "#F0F0F0",
}
THEMES["swiss"] = _theme(
    "swiss", "瑞士极简（黑白网格·单点红）",
    semantic=_swiss_sem,
    visual=_vis(
        radius=0, shadow="none", line_spacing=1.2,
        density="strict", accent_budget=0.05,
        chart_colors=["#111111", "#767676", "#E63312"],
    ),
    extra_palette=["#FFFFFF"],
)

# 6) oriental — new-Chinese humanistic: rice paper, cinnabar + dai blue, serif.
_ori_sem = {
    "surface_dark": "#22303C", "surface_light": "#F7F3EC",
    "card_fill": "#FDFBF6", "ink": "#2B2B2B", "ink_on_dark": "#F3ECE0",
    "body": "#4A4239", "muted": "#8C8275", "line": "#E0D7C8",
    "accent": "#8C2F28", "accent_2": "#2F4858", "accent_soft": "#E8DDCB",
}
THEMES["oriental"] = _theme(
    "oriental", "新中式人文（宣纸·朱砂·黛蓝）",
    semantic=_ori_sem,
    visual=_vis(
        font_heading='"Songti SC","SimSun",Georgia,serif',
        latin_heading="Georgia", ea_heading="Songti SC", serif_heading=True,
        radius=4, shadow="none", line_spacing=1.34,
        density="relaxed", accent_budget=0.06,
        chart_colors=["#8C2F28", "#2F4858", "#B89B5E"],
    ),
    extra_palette=["#B89B5E", "#FFFFFF", "#FDFBF6", "#F3ECE0"],
)


# ===========================================================================
# Enterprise style themes — stylistic homages, NOT official brand guidelines.
# Palettes use industry-common approximate colors; no trademark/logo assets.
# Consulting houses: square corners, strict density, low accent-area budget.
# ===========================================================================

# 7) mckinsey — deep navy, restrained blue accent, rigorous square grid.
THEMES["mckinsey"] = _theme(
    "mckinsey", "麦肯锡风（深海军蓝·严谨）",
    semantic={
        "surface_dark": "#051C2C", "surface_light": "#FFFFFF",
        "card_fill": "#FFFFFF", "ink": "#051C2C", "ink_on_dark": "#FFFFFF",
        "body": "#33424F", "muted": "#7A8791", "line": "#D9DEE3",
        "accent": "#235BA8", "accent_2": "#051C2C", "accent_soft": "#D6E2F2",
    },
    visual=_vis(radius=0, shadow="none", line_spacing=1.18, density="strict",
                accent_budget=0.06,
                chart_colors=["#051C2C", "#235BA8", "#D6E2F2"]),
    extra_palette=["#FFFFFF"],
)

# 8) bcg — deep editorial green, square, calm and analytical.
THEMES["bcg"] = _theme(
    "bcg", "波士顿咨询风（墨绿·分析感）",
    semantic={
        "surface_dark": "#003B2C", "surface_light": "#FFFFFF",
        "card_fill": "#FFFFFF", "ink": "#003B2C", "ink_on_dark": "#FFFFFF",
        "body": "#2F3D38", "muted": "#6E7D76", "line": "#D8E0DC",
        "accent": "#007352", "accent_2": "#003B2C", "accent_soft": "#CDE4DA",
    },
    visual=_vis(radius=0, shadow="none", line_spacing=1.18, density="strict",
                accent_budget=0.06,
                chart_colors=["#003B2C", "#007352", "#CDE4DA"]),
    extra_palette=["#FFFFFF"],
)

# 9) pwc — neutral graphite with a small-budget orange-red accent.
THEMES["pwc"] = _theme(
    "pwc", "普华永道风（石墨灰·橙红点缀）",
    semantic={
        "surface_dark": "#2D2D2D", "surface_light": "#FFFFFF",
        "card_fill": "#FFFFFF", "ink": "#2D2D2D", "ink_on_dark": "#FFFFFF",
        "body": "#404040", "muted": "#808080", "line": "#E0E0E0",
        "accent": "#D04A02", "accent_2": "#2D2D2D", "accent_soft": "#FBE3D3",
    },
    visual=_vis(radius=0, shadow="none", line_spacing=1.18, density="strict",
                accent_budget=0.05,
                chart_colors=["#2D2D2D", "#D04A02", "#FBE3D3"]),
    extra_palette=["#FFFFFF"],
)

# 10) rolandberger — teal-tinged corporate blue, precise and structured.
THEMES["rolandberger"] = _theme(
    "rolandberger", "罗兰贝格风（青蓝·结构化）",
    semantic={
        "surface_dark": "#003A5D", "surface_light": "#FFFFFF",
        "card_fill": "#FFFFFF", "ink": "#003A5D", "ink_on_dark": "#FFFFFF",
        "body": "#2E4353", "muted": "#6E8294", "line": "#D6E0E8",
        "accent": "#0091CA", "accent_2": "#003A5D", "accent_soft": "#D0E8F4",
    },
    visual=_vis(radius=0, shadow="none", line_spacing=1.18, density="strict",
                accent_budget=0.06,
                chart_colors=["#003A5D", "#0091CA", "#D0E8F4"]),
    extra_palette=["#FFFFFF"],
)

# 11) microsoft — Fluent feel: light neutral surface, soft radius, blue.
THEMES["microsoft"] = _theme(
    "microsoft", "微软风（Fluent 中性灰·蓝）",
    semantic={
        "surface_dark": "#1A1A1A", "surface_light": "#FAFAFA",
        "card_fill": "#FFFFFF", "ink": "#1A1A1A", "ink_on_dark": "#FFFFFF",
        "body": "#3C3C3C", "muted": "#707070", "line": "#E1E1E1",
        "accent": "#0078D4", "accent_2": "#1A1A1A", "accent_soft": "#CFE3F7",
    },
    visual=_vis(radius=4, shadow="soft", line_spacing=1.2, density="strict",
                accent_budget=0.08,
                chart_colors=["#0078D4", "#1A1A1A", "#CFE3F7"]),
    extra_palette=["#FFFFFF"],
)

# 12) apple — near-black/grey minimalism, generous whitespace, tiny accent.
THEMES["apple"] = _theme(
    "apple", "苹果风（极简黑白灰·大留白）",
    semantic={
        "surface_dark": "#1D1D1F", "surface_light": "#FFFFFF",
        "card_fill": "#FFFFFF", "ink": "#1D1D1F", "ink_on_dark": "#F5F5F7",
        "body": "#424245", "muted": "#86868B", "line": "#D2D2D7",
        "accent": "#0071E3", "accent_2": "#1D1D1F", "accent_soft": "#F0F0F2",
    },
    visual=_vis(radius=6, shadow="none", line_spacing=1.34, density="relaxed",
                accent_budget=0.04,
                chart_colors=["#1D1D1F", "#86868B", "#0071E3"]),
    extra_palette=["#F5F5F7", "#FFFFFF"],
)

# ===========================================================================
# Data-driven themes — numeric tokens imported from VoltAgent/awesome-design-md
# (MIT, Stitch DESIGN.md frontmatter). Each hex is traceable through
# references/imported/theme_mapping.json -> design_tokens.json -> source SHA256.
# Extracted CSS tokens are NOT official brand guidelines; no logos or assets.
# ===========================================================================

# 13) stripe — electric indigo primary on navy ink + near-white canvas.
THEMES["stripe"] = _theme(
    "stripe", "靛紫金融风（Stripe 令牌）",
    semantic={
        "surface_dark": "#1C1E54", "surface_light": "#FFFFFF",
        "card_fill": "#F6F9FC", "ink": "#0D253D", "ink_on_dark": "#FFFFFF",
        "body": "#273951", "muted": "#64748D", "line": "#E3E8EE",
        "accent": "#533AFD", "accent_2": "#4434D4", "accent_soft": "#B9B9F9",
    },
    visual=_vis(
        latin_heading="Inter", latin_body="Inter",
        radius=8, shadow="soft", line_spacing=1.28,
        accent_budget=0.08,
        chart_colors=["#0D253D", "#533AFD", "#665EFD"],
    ),
    extra_palette=["#665EFD", "#FFFFFF"],
)

# 14) vercel — black/white duet with a single link-blue accent.
THEMES["vercel"] = _theme(
    "vercel", "黑白极简风（Vercel 令牌）",
    semantic={
        "surface_dark": "#171717", "surface_light": "#FFFFFF",
        "card_fill": "#F5F5F5", "ink": "#171717", "ink_on_dark": "#FFFFFF",
        "body": "#4D4D4D", "muted": "#888888", "line": "#EBEBEB",
        "accent": "#0070F3", "accent_2": "#0761D1", "accent_soft": "#D3E5FF",
    },
    visual=_vis(
        latin_heading="Inter", latin_body="Inter",
        radius=6, shadow="none", line_spacing=1.25,
        accent_budget=0.06,
        chart_colors=["#171717", "#0070F3", "#A1A1A1"],
    ),
    extra_palette=["#A1A1A1", "#FFFFFF"],
)

# 15) wired — magazine black/white, serif display, ink-blue links.
THEMES["wired"] = _theme(
    "wired", "黑白杂志风（WIRED 令牌·衬线）",
    semantic={
        "surface_dark": "#000000", "surface_light": "#FFFFFF",
        "card_fill": "#F5F5F5", "ink": "#000000", "ink_on_dark": "#FFFFFF",
        "body": "#1A1A1A", "muted": "#757575", "line": "#E0E0E0",
        "accent": "#057DBC", "accent_2": "#000000", "accent_soft": "#F5F5F5",
    },
    visual=_vis(
        font_heading='"Songti SC","SimSun",Georgia,serif',
        latin_heading="Georgia", ea_heading="Songti SC", serif_heading=True,
        radius=0, shadow="none", line_spacing=1.34,
        density="relaxed", accent_budget=0.05,
        chart_colors=["#000000", "#757575", "#057DBC"],
    ),
    extra_palette=["#FFFFFF"],
)

# 16) ibm — Carbon-style structured blue, 4px corners, IBM Plex Sans.
THEMES["ibm"] = _theme(
    "ibm", "Carbon 企业蓝（IBM 令牌）",
    semantic={
        "surface_dark": "#161616", "surface_light": "#FFFFFF",
        "card_fill": "#F4F4F4", "ink": "#161616", "ink_on_dark": "#FFFFFF",
        "body": "#525252", "muted": "#8C8C8C", "line": "#E0E0E0",
        "accent": "#0F62FE", "accent_2": "#0043CE", "accent_soft": "#E0E0E0",
    },
    visual=_vis(
        latin_heading="IBM Plex Sans", latin_body="IBM Plex Sans",
        radius=4, shadow="none", line_spacing=1.2, density="strict",
        accent_budget=0.06,
        chart_colors=["#161616", "#0F62FE", "#0043CE"],
    ),
    extra_palette=["#FFFFFF"],
)

# ---- resolution + active-theme global --------------------------------------
_ALIASES = {
    # allow both `theme` and legacy `scenario` names
    "consulting": "consulting", "general": "general",
    "magazine": "magazine", "editorial": "magazine",
    "tech": "tech", "dark-tech": "tech",
    "swiss": "swiss", "minimal": "swiss",
    "oriental": "oriental", "chinese": "oriental",
    # enterprise style themes
    "mckinsey": "mckinsey", "mck": "mckinsey",
    "bcg": "bcg", "bgc": "bcg",  # tolerate the common BGC typo
    "pwc": "pwc",
    "rolandberger": "rolandberger", "roland": "rolandberger", "rb": "rolandberger",
    "microsoft": "microsoft", "msft": "microsoft",
    "apple": "apple",
    # data-driven themes (imported DESIGN.md tokens)
    "stripe": "stripe", "stripi": "stripe",
    "vercel": "vercel", "geist": "vercel",
    "wired": "wired", "editorial-bw": "wired",
    "ibm": "ibm", "carbon": "ibm",
}

_ACTIVE = THEMES["consulting"]


def resolve_name(deck):
    """Pick a theme name from a deck dict; theme wins over legacy scenario."""
    key = deck.get("theme") or deck.get("scenario") or "general"
    return _ALIASES.get(str(key).lower(), "general")


def get_theme(name):
    return THEMES.get(_ALIASES.get(str(name).lower(), name),
                      THEMES["general"])


def build_derived(spec):
    """Build a one-off theme from a reference image (see cover_style.py).

    The derived spec carries semantic colors + optional visual overrides; the
    base theme supplies typefaces/spacing. Palette is recomputed so lint still
    enforces color self-consistency on freeform decks.
    """
    base = get_theme(spec.get("base", "magazine"))
    sem = dict(base["semantic"])
    sem.update({k: str(v).upper() for k, v in spec.get("semantic", {}).items()})
    vis = dict(base["visual"])
    vis.update(spec.get("visual", {}))
    th = _theme(spec.get("name", "cover-derived"),
                spec.get("label", "封面派生主题"), sem, vis,
                extra_palette=spec.get("palette_extra"),
                min_body=spec.get("min_body", 16))
    th["source"] = spec.get("source")
    return th


def activate(name_or_deck):
    """Set the process-wide active theme; returns the resolved theme."""
    global _ACTIVE
    if isinstance(name_or_deck, dict):
        derived = name_or_deck.get("derived_theme")
        _ACTIVE = build_derived(derived) if derived else get_theme(resolve_name(name_or_deck))
    else:
        _ACTIVE = get_theme(name_or_deck)
    return _ACTIVE


def get_active():
    return _ACTIVE


def semantic(role, default=None):
    return get_active()["semantic"].get(role, default)


def visual(key, default=None):
    return get_active()["visual"].get(key, default)
