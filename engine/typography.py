"""CJK typography helpers for FreePPT (deterministic, no platform probing).

Implements:
1. Kinsoku (避头尾): closing punctuation must not start a line; opening
   punctuation must not end a line. Closing punctuation is *hung* into the
   previous line, which is the standard CJK composition behaviour.
2. Atomic pairs (破折号 —— / 省略号 ……) must not be split across lines.
3. latin_cjk_spacing(): optional thin space between CJK and Latin/digit runs.
4. font_stack(): a declarative fallback stack. FreePPT never probes installed
   fonts at build time, because that would make output machine-dependent and
   break the determinism guarantee. The stack is documentation + metadata and
   is recorded in the deck spec; the actual face written into OOXML stays the
   theme's declared font.

Public rule checker `find_kinsoku_violations()` is consumed by lint.py.
"""

import re

# Characters that must NOT begin a line.
NO_START = set("，。、；：？！）》」』】〕〉”’…·％‰℃")
# Characters that must NOT end a line.
NO_END = set("（《「『【〔〈“‘")
ATOMIC_PAIRS = ("——", "……")
ATOMIC_HEADS = {p[0] for p in ATOMIC_PAIRS}

# Runtime switch. layout_deck() sets it from deck["typography"]["kinsoku"].
KINSOKU_ENABLED = True


def set_enabled(value=True):
    global KINSOKU_ENABLED
    KINSOKU_ENABLED = bool(value)


def is_enabled():
    return KINSOKU_ENABLED


def _is_cjk(ch):
    return ord(ch) >= 0x2E80


def apply_kinsoku(lines):
    """Move illegal line-edge punctuation. Input/output: list[str].

    Hanging a closing mark into the previous line may make that line one
    character wider; lint still checks overflow on the wrapped text height,
    not on a per-line pixel width, so this stays within the layout contract.
    """
    out = [list(str(ln)) for ln in lines]
    if not out:
        return [""]
    # A lone glyph (e.g. a decorative opening quote) is not a paragraph.
    # Kinsoku only applies where a real line break exists.
    if len(out) == 1 and len(out[0]) <= 1:
        return ["".join(out[0])]

    # pass 1: pull NO_START characters back onto the previous line
    for i in range(1, len(out)):
        while out[i] and out[i][0] in NO_START:
            out[i - 1].append(out[i].pop(0))

    # pass 2: push NO_END characters forward onto the next line. The last
    # line has no next line, so append one (an opening mark at a line head is
    # legal; leaving it at a line tail is not).
    for i in range(len(out) - 1, -1, -1):
        while len(out[i]) > 1 and out[i][-1] in NO_END:
            ch = out[i].pop()
            if i + 1 < len(out):
                out[i + 1].insert(0, ch)
            else:
                out.append([ch])

    # pass 3: re-join atomic pairs split by the wrap (—— / ……)
    for i in range(len(out) - 1):
        if out[i] and out[i][-1] in ATOMIC_HEADS and out[i + 1]:
            pair = out[i][-1] + out[i + 1][0]
            if pair in ATOMIC_PAIRS:
                out[i].append(out[i + 1].pop(0))

    # pass 1 again: pass 2/3 may have created a new illegal line head
    for i in range(1, len(out)):
        while out[i] and out[i][0] in NO_START:
            out[i - 1].append(out[i].pop(0))

    result = ["".join(ln) for ln in out]
    return result or [""]


def find_kinsoku_violations(lines):
    """Return [(line_index, code, char)] for any remaining illegal edges."""
    issues = []
    # Single-glyph decorative nodes are exempt: there is no line break to
    # apply a prohibition rule to.
    if len(lines) == 1 and len(str(lines[0])) <= 1:
        return issues
    for i, ln in enumerate(lines):
        s = str(ln)
        if s and s[0] in NO_START:
            issues.append((i, "NO_START", s[0]))
        if s and s[-1] in NO_END:
            issues.append((i, "NO_END", s[-1]))
        if i and lines[i - 1]:
            pair = str(lines[i - 1])[-1] + (s[0] if s else "")
            if pair in ATOMIC_PAIRS:
                issues.append((i, "ATOMIC_SPLIT", pair))
    return issues


THIN_SPACE = "\u2009"


def latin_cjk_spacing(text):
    """Insert a thin space at CJK <-> Latin/digit boundaries (opt-in).

    Not enabled by default: it changes string length and therefore the
    deterministic layout of every existing deck. Use `cli.py make
    --cjk-spacing` or call it explicitly on new content.
    """
    s = str(text)
    # CJK followed by latin/digit, or latin/digit followed by CJK
    s = re.sub(r"([\u2E80-\u9FFF])([A-Za-z0-9])",
               rf"\1{THIN_SPACE}\2", s)
    s = re.sub(r"([A-Za-z0-9])([\u2E80-\u9FFF])",
               rf"\1{THIN_SPACE}\2", s)
    return s


# Declarative fallback stacks. Order = preference; no runtime probing.
FONT_FALLBACK = {
    "sans": ["PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC",
             "Source Han Sans SC", "Hiragino Sans GB", "Arial", "sans-serif"],
    "serif": ["Songti SC", "SimSun", "Noto Serif CJK SC",
              "Source Han Serif SC", "Georgia", "Times New Roman", "serif"],
    "latin": ["Inter", "Helvetica Neue", "Arial", "Liberation Sans",
              "DejaVu Sans", "sans-serif"],
}


def font_stack(kind="sans", declared=None):
    """Return [declared?, ...fallback] without duplicates."""
    stack = list(FONT_FALLBACK.get(kind, FONT_FALLBACK["sans"]))
    if declared:
        stack = [declared] + [f for f in stack if f != declared]
    return stack


def metadata(deck_font=None):
    """Attachable, deterministic typography metadata for a deck spec."""
    return {
        "kinsoku": True,
        "no_start_chars": "".join(sorted(NO_START)),
        "no_end_chars": "".join(sorted(NO_END)),
        "atomic_pairs": list(ATOMIC_PAIRS),
        "font_stack_sans": font_stack("sans", deck_font),
        "font_stack_serif": font_stack("serif"),
        "note": "Declarative only; FreePPT does not probe installed fonts at build time.",
    }
