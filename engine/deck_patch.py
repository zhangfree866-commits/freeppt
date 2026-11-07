"""Single-node revision of a FreePPT deck DSL ("conversational local edit").

Instead of regenerating a whole deck, callers change one value by a dotted
path (`slides.3.data.title`) and re-run the stage-4 lint gate. This keeps the
five-stage pipeline intact while making small edits cheap.
"""

import json


def parse_value(raw):
    """Numbers/booleans/JSON objects are parsed; everything else stays a string."""
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw


def set_path(doc, path, value):
    """Set a dotted path with numeric list indices. Returns (old, new path)."""
    parts = [p for p in str(path).split(".") if p]
    if not parts:
        raise KeyError("empty path")
    cur = doc
    for p in parts[:-1]:
        if isinstance(cur, list):
            cur = cur[_as_index(p, len(cur))]
        elif isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            raise KeyError(f"path segment not found: {p}")
    last = parts[-1]
    if isinstance(cur, list):
        i = _as_index(last, len(cur))
        old = cur[i]
        cur[i] = value
    elif isinstance(cur, dict):
        old = cur.get(last)
        cur[last] = value
    else:
        raise KeyError(f"cannot set inside {type(cur).__name__}")
    return old


def _as_index(part, length):
    try:
        i = int(part)
    except ValueError:
        raise KeyError(f"expected list index, got {part!r}")
    if not (0 <= i < length):
        raise KeyError(f"index {i} out of range (len={length})")
    return i


def apply_sets(doc, assignments):
    """assignments: iterable of "path=value" strings. Returns a change log."""
    log = []
    for raw in assignments:
        if "=" not in raw:
            raise ValueError(f"--set expects path=value, got {raw!r}")
        path, value = raw.split("=", 1)
        old = set_path(doc, path.strip(), parse_value(value))
        log.append({"path": path.strip(), "old": old,
                    "new": parse_value(value)})
    return log
