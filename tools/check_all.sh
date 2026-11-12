#!/usr/bin/env bash
# Full local gate. Used by CONTRIBUTING.md and CI-equivalent local runs.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== 1/4 unit tests =="
python3 -m unittest discover -s tests -q

echo "== 2/4 lint every example deck =="
for f in examples/*.json; do
  case "$(basename "$f")" in
    web_manifest.json|notes_*.json|briefs_*.json|style_*.json|structure_*.json|edits_*.json) continue ;;
  esac
  printf "  %-40s" "$(basename "$f")"
  python3 engine/cli.py lint "$f" > /dev/null
  echo "ok"
done

echo "== 3/4 compose -> lint -> build smoke =="
# 必须带 --briefs：六维规格是编译前提，不传会被 design_spec 闸门拦死（rc=1）。
# 这份示例同时充当「逐页设计」的参照写法，别改成兜底原型池跑通就算了。
python3 engine/cli.py compose examples/notes_renqing_mianzi.json \
  --briefs examples/briefs_renqing_mianzi.json \
  --out /tmp/freeppt_check_deck.json --ledger /tmp/freeppt_check_style.json
python3 engine/cli.py lint /tmp/freeppt_check_deck.json > /dev/null
python3 engine/cli.py build /tmp/freeppt_check_deck.json /tmp/freeppt_check.pptx

# 第二本逐页设计实例：《11枚戒指》10 页。同样必须带 --briefs，
# 且不许给封面硬塞错图（曾因 book.cover 照搬 demo 而配成《人情与面子》书封）。
python3 engine/cli.py compose examples/notes_eleven_rings.json \
  --briefs examples/briefs_eleven_rings.json \
  --out /tmp/freeppt_rings_deck.json
python3 engine/cli.py lint /tmp/freeppt_rings_deck.json > /dev/null

echo "== 4/4 pure CLI smoke =="
python3 engine/cli.py make "本周完成 3 项交付；客户满意度提升到 92%；上线新版引导流程" \
  --type weekly --out /tmp/freeppt_brief.pptx

echo "ALL CHECKS PASSED"
