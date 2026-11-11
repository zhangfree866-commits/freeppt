#!/usr/bin/env python3
"""版式账本（Layout Ledger）：全局唯一版式的分配契约与重复检测硬闸。

账本 JSON 形如：
    {
      "family_gap": 4,
      "entries": [
        {"index": 0, "pn": "P1", "layout_id": "cover__...",
         "family": "cover", "chrome": "cover", "special": true, ...},
        ...
      ]
    }

硬闸（任一不满足即 ok=false）：
  1) layout_id 全局唯一；
  2) 相邻两页不同 family、不同 chrome（避免相邻同族/同皮）；
  3) 同一 family 两次出现的页码间隔 >= family_gap。
特型页（special=true）只参与 layout_id 唯一性，不参与间隔/相邻判断。
这层与几何解耦：只要账本声明，就能拦住"版式周期性轮播"。
"""


def _entry(e, key, default=None):
    return e.get(key, default)


def validate(ledger):
    entries = ledger.get("entries") or []
    gap = int(ledger.get("family_gap", 0) or 0)
    errors = []

    # 1) layout_id 唯一
    ids = [_entry(e, "layout_id") for e in entries]
    seen_id = set()
    for e, lid in zip(entries, ids):
        if lid is None:
            errors.append(f"{_entry(e, 'pn', '?')}: missing layout_id")
        elif lid in seen_id:
            errors.append(f"{_entry(e, 'pn', '?')}: duplicate layout_id {lid}")
        seen_id.add(lid)

    # 通用页序列（按 index 排序更稳妥）
    generic = sorted([e for e in entries if not _entry(e, "special", False)],
                     key=lambda e: _entry(e, "index", 0))

    # 2) 相邻不同 family / chrome
    for a, b in zip(generic, generic[1:]):
        pa, pb = _entry(a, "pn", "?"), _entry(b, "pn", "?")
        if _entry(a, "family") == _entry(b, "family"):
            errors.append(f"adjacent same family {pa}-{pb}: "
                          f"{_entry(a, 'family')}")
        if _entry(a, "chrome") == _entry(b, "chrome"):
            errors.append(f"adjacent same chrome {pa}-{pb}: "
                          f"{_entry(a, 'chrome')}")

    # 3) family 页码间隔
    last = {}
    for e in generic:
        fam = _entry(e, "family")
        idx = int(_entry(e, "index", 0))
        if fam in last and idx - last[fam] < gap:
            errors.append(f"{_entry(e, 'pn', '?')}: family {fam} gap "
                          f"{idx - last[fam]} < {gap}")
        last[fam] = idx

    return {"ok": not errors, "errors": errors,
            "total": len(entries), "generic": len(generic)}


def validate_file(path):
    import json
    with open(path, "r", encoding="utf-8") as f:
        ledger = json.load(f)
    return validate(ledger)
