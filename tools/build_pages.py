#!/usr/bin/env python3
"""Regenerate the GitHub Pages index.html from design/mockup.html.

design/mockup.html is the source and deliberately carries no HTML skeleton
(Claude-artifact format). This script wraps it with the doctype/head that
GitHub Pages needs (charset, mobile viewport, title, favicon).

Run from the repo root after any mockup change:  python3 tools/build_pages.py
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "design" / "mockup.html"
OUT = ROOT / "index.html"

HEAD = """<!DOCTYPE html>
<html lang="zh-Hant-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BeatCount — 設計原型</title>
<meta name="description" content="BeatCount iOS App 互動設計原型：匯入歌曲、自動偵測節拍、真人語音數拍。">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E%F0%9F%92%83%3C/text%3E%3C/svg%3E">
</head>
<body>
"""

src = SRC.read_text()
lines = src.split("\n")
# the source's leading <title> is superseded by the wrapper's head
if lines[0].strip().startswith("<title>"):
    src = "\n".join(lines[1:])

OUT.write_text(HEAD + src + "\n</body>\n</html>\n")
print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes)")
