#!/usr/bin/env python3
"""Render an SVG to PNG with headless Chrome (Playwright).

    python3 docs/diagrams/render.py docs/img/architecture.svg docs/img/architecture.png
"""

import os
import sys

from playwright.sync_api import sync_playwright

src, dst = sys.argv[1], sys.argv[2]
svg = open(src, encoding="utf-8").read()
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    pg = b.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=2)
    pg.set_content(f"<html><body style='margin:0;background:#fff'>{svg}</body></html>")
    box = pg.eval_on_selector("svg", "e => { const r = e.getBoundingClientRect(); return [r.width, r.height]; }")
    pg.set_viewport_size({"width": int(box[0]), "height": int(box[1])})
    pg.locator("svg").screenshot(path=dst)
    b.close()
print("wrote", os.path.abspath(dst))
