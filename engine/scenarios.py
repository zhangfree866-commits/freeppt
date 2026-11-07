"""Scenario registry: palettes and per-layout text minimums."""

SCENARIOS = {
    "consulting": {
        "palette": {
            "#061F32", "#001965", "#08A6F6", "#99BDED", "#5A0E13",
            "#177B57", "#F47B39", "#44546A", "#808080", "#E5E7EB", "#FFFFFF",
        },
        "font": 'Arial,"PingFang SC","Microsoft YaHei","Noto Sans SC",sans-serif',
        "min_body": 18,
        "layout_min_chars": {
            "cover": 20, "toc": 80, "section": 14, "closing": 0,
        },
        "no_footer": {"cover", "toc", "section", "closing"},
    },
    "general": {
        # permissive fallback: still enforces geometry, not a strict palette
        "palette": None,
        "font": '"PingFang SC","Microsoft YaHei","Noto Sans SC",Arial,sans-serif',
        "min_body": 18,
        "layout_min_chars": {},
        "no_footer": {"cover", "toc", "section", "closing"},
    },
}


def get(name):
    return SCENARIOS.get(name or "general", SCENARIOS["general"])
