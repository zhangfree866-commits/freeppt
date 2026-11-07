"""Portability guards for committed example decks.

A deck that bakes in the author's absolute filesystem path passes lint on the
author's machine but fails with ASSET_MISSING in CI and every other checkout.
"""

import glob
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(ROOT, "examples")


def _image_refs(node):
    if isinstance(node, dict):
        for key in ("src", "bg_image"):
            if isinstance(node.get(key), str):
                yield node[key]
        bg = node.get("background")
        if isinstance(bg, dict) and isinstance(bg.get("image"), str):
            yield bg["image"]
        for value in node.values():
            yield from _image_refs(value)
    elif isinstance(node, list):
        for value in node:
            yield from _image_refs(value)


def _decks():
    for path in sorted(glob.glob(os.path.join(EXAMPLES, "*.json"))):
        with open(path, encoding="utf-8") as f:
            try:
                doc = json.load(f)
            except json.JSONDecodeError:
                continue
        if isinstance(doc, dict) and "slides" in doc:
            yield path, doc


class TestRepoPortability(unittest.TestCase):
    def test_no_absolute_assets_base(self):
        decks = list(_decks())
        self.assertTrue(decks, "no example decks found")
        for path, doc in decks:
            base = doc.get("assets_base")
            if base:
                self.assertFalse(
                    os.path.isabs(base),
                    "%s pins an absolute assets_base: %s" %
                    (os.path.basename(path), base),
                )

    def test_all_image_refs_resolve_from_repo_root(self):
        decks = list(_decks())
        self.assertTrue(decks)
        checked = 0
        for path, doc in decks:
            base = doc.get("assets_base") or "examples/assets"
            for ref in sorted(set(_image_refs(doc))):
                resolved = (os.path.join(ROOT, base, ref)
                            if not os.path.isabs(ref) else ref)
                self.assertTrue(
                    os.path.exists(resolved),
                    "%s references a missing asset: %s" %
                    (os.path.basename(path), ref),
                )
                checked += 1
        self.assertGreater(checked, 0, "no image references were checked")

    def test_compose_emits_relative_assets_base(self):
        from engine import art_direction
        notes_path = os.path.join(EXAMPLES, "notes_renqing_mianzi.json")
        with open(notes_path, encoding="utf-8") as f:
            notes = json.load(f)
        deck, _ = art_direction.compose(notes, EXAMPLES)
        self.assertTrue(deck["assets_base"],
                        "a usable cover image should set assets_base")
        self.assertFalse(os.path.isabs(deck["assets_base"]),
                         "compose must not bake in a machine-specific path")


if __name__ == "__main__":
    unittest.main()
