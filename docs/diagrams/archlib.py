"""Tiny SVG architecture-diagram library (AWS-reference-architecture style).

Nested boundary boxes, colour-coded service tiles with a glyph, orthogonal connectors and numbered
flow badges. No dependencies: it writes plain SVG. Used by docs/diagrams/architecture.py.
"""

from __future__ import annotations

import html

FONT = "Inter, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

# category -> tile colour (loosely follows Google Cloud's product-category palette)
COLORS = {
    "compute": "#4285F4",
    "network": "#8E44AD",
    "data": "#00897B",
    "security": "#D93025",
    "ai": "#F29900",
    "ops": "#1E8E3E",
    "dev": "#5F6368",
    "actor": "#202124",
}

TILE = 60


def _e(s: str) -> str:
    return html.escape(s, quote=True)


def glyph(kind: str, cx: float, cy: float) -> str:
    """White line-art glyph drawn inside a tile, centred on (cx, cy), ~30px box."""
    s = 'fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"'
    f = 'fill="#fff"'
    g = {
        "user": f'<circle cx="{cx}" cy="{cy-6}" r="6" {s}/><path d="M{cx-12} {cy+13} q0 -11 12 -11 q12 0 12 11" {s}/>',
        "git": f'<circle cx="{cx-8}" cy="{cy-9}" r="3.2" {s}/><circle cx="{cx-8}" cy="{cy+9}" r="3.2" {s}/><circle cx="{cx+9}" cy="{cy-3}" r="3.2" {s}/><path d="M{cx-8} {cy-6} v12 M{cx-8} {cy+2} q0 -5 9 -5" {s}/>',
        "bucket": f'<ellipse cx="{cx}" cy="{cy-9}" rx="12" ry="4.5" {s}/><path d="M{cx-12} {cy-9} l2.5 20 q9.5 4 19 0 l2.5 -20" {s}/>',
        "db": f'<ellipse cx="{cx}" cy="{cy-10}" rx="11" ry="4" {s}/><path d="M{cx-11} {cy-10} v20 q11 6 22 0 v-20 M{cx-11} {cy} q11 6 22 0" {s}/>',
        "run": f'<path d="M{cx-10} {cy-8} l9 8 l-9 8" {s}/><path d="M{cx+2} {cy+9} h9" {s}/>',
        "bolt": f'<path d="M{cx+3} {cy-13} l-11 15 h9 l-3 12 l11 -15 h-9 z" {s}/>',
        "filter": f'<path d="M{cx-12} {cy-11} h24 l-9 11 v10 l-6 -3 v-7 z" {s}/>',
        "sparkle": f'<path d="M{cx} {cy-13} q2 11 13 13 q-11 2 -13 13 q-2 -11 -13 -13 q11 -2 13 -13 z" {s}/>',
        "shield": f'<path d="M{cx} {cy-13} l11 4 v8 q0 9 -11 14 q-11 -5 -11 -14 v-8 z" {s}/><path d="M{cx-4} {cy+1} l3 3 l6 -7" {s}/>',
        "key": f'<circle cx="{cx-6}" cy="{cy}" r="5.5" {s}/><path d="M{cx} {cy} h14 M{cx+9} {cy} v5 M{cx+14} {cy} v4" {s}/>',
        "lb": f'<circle cx="{cx}" cy="{cy-9}" r="4" {s}/><circle cx="{cx-11}" cy="{cy+9}" r="4" {s}/><circle cx="{cx+11}" cy="{cy+9}" r="4" {s}/><path d="M{cx} {cy-5} v4 M{cx} {cy-1} h-11 v6 M{cx} {cy-1} h11 v6" {s}/>',
        "globe": f'<circle cx="{cx}" cy="{cy}" r="12" {s}/><ellipse cx="{cx}" cy="{cy}" rx="5" ry="12" {s}/><path d="M{cx-12} {cy} h24" {s}/>',
        "k8s": f'<path d="M{cx} {cy-13} l11 6 v12 l-11 6 l-11 -6 v-12 z" {s}/><circle cx="{cx}" cy="{cy}" r="3.5" {s}/>',
        "chart": f'<path d="M{cx-12} {cy+11} v-24 M{cx-12} {cy+11} h25" {s}/><path d="M{cx-6} {cy+5} v-6 M{cx} {cy+5} v-13 M{cx+6} {cy+5} v-9" {s}/>',
        "pipeline": f'<path d="M{cx-13} {cy-7} h9 M{cx-13} {cy+7} h9" {s}/><rect x="{cx-3}" y="{cy-12}" width="9" height="9" rx="2" {s}/><rect x="{cx-3}" y="{cy+3}" width="9" height="9" rx="2" {s}/><path d="M{cx+8} {cy-7} h5 M{cx+8} {cy+7} h5" {s}/>',
        "registry": f'<rect x="{cx-12}" y="{cy-12}" width="24" height="8" rx="2" {s}/><rect x="{cx-12}" y="{cy-2}" width="24" height="8" rx="2" {s}/><rect x="{cx-12}" y="{cy+8}" width="24" height="5" rx="2" {s}/>',
        "nat": f'<circle cx="{cx}" cy="{cy}" r="12" {s}/><path d="M{cx-7} {cy-3} h14 l-4 -4 M{cx+7} {cy+4} h-14 l4 4" {s}/>',
        "wall": f'<rect x="{cx-13}" y="{cy-11}" width="26" height="22" {s}/><path d="M{cx-13} {cy-3} h26 M{cx-13} {cy+4} h26 M{cx-4} {cy-11} v8 M{cx+5} {cy-3} v7 M{cx-4} {cy+4} v7" {s}/>',
        "pod": f'<path d="M{cx} {cy-12} l11 6 v12 l-11 6 l-11 -6 v-12 z M{cx-11} {cy-6} l11 6 l11 -6 M{cx} {cy} v12" {s}/>',
        "policy": f'<rect x="{cx-10}" y="{cy-13}" width="20" height="26" rx="2" {s}/><path d="M{cx-5} {cy-6} h10 M{cx-5} {cy} h10 M{cx-5} {cy+6} h6" {s}/>',
        "dns": f'<circle cx="{cx}" cy="{cy}" r="12" {s}/><path d="M{cx-6} {cy-5} h12 M{cx-6} {cy+1} h12 M{cx-6} {cy+7} h8" {s}/>',
        "money": f'<circle cx="{cx}" cy="{cy}" r="12" {s}/><path d="M{cx+4} {cy-6} q-8 -4 -8 0 q0 3 4 3 q4 0 4 3 q0 4 -8 0" {s}/>',
        "argo": f'<circle cx="{cx}" cy="{cy-2}" r="9" {s}/><path d="M{cx-4} {cy+3} q4 4 8 0 M{cx-3.5} {cy-5} v1 M{cx+3.5} {cy-5} v1" {s}/><path d="M{cx-7} {cy+11} q7 4 14 0" {s}/>',
        "cloud": f'<path d="M{cx-9} {cy+7} q-6 0 -6 -6 q0 -6 7 -6 q2 -8 10 -6 q7 1 7 8 q6 0 6 5 q0 5 -6 5 z" {s} transform="translate(0,0) scale(0.9) translate({cx*0.11},{cy*0.11})"/>',
    }
    return g.get(kind, f'<circle cx="{cx}" cy="{cy}" r="8" {s}/>')


class Diagram:
    def __init__(self, w: int, h: int, title: str, subtitle: str = ""):
        self.w, self.h = w, h
        self.title, self.subtitle = title, subtitle
        self.groups: list[str] = []
        self.body: list[str] = []
        self.nodes: dict[str, tuple[float, float]] = {}
        self.badges: list[str] = []

    # ---- boundary boxes -------------------------------------------------------------------
    def group(self, x, y, w, h, label, color="#5f6368", dash=True, fill="none", icon=None, label_w=None):
        d = 'stroke-dasharray="7 5"' if dash else ""
        self.groups.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{color}" stroke-width="1.6" {d}/>'
        )
        tw = label_w or (len(label) * 6.6 + 30)
        self.groups.append(
            f'<rect x="{x+14}" y="{y-11}" width="{tw}" height="22" rx="4" fill="#fff"/>'
            f'<text x="{x+24}" y="{y+4.5}" font-size="12.5" font-weight="700" fill="{color}" font-family="{FONT}">{_e(label)}</text>'
        )

    def band(self, x, y, w, h, label, color, fill):
        self.groups.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{color}" stroke-width="1.2"/>')
        self.groups.append(f'<text x="{x+14}" y="{y+20}" font-size="12.5" font-weight="700" fill="{color}" font-family="{FONT}">{_e(label)}</text>')

    # ---- service tiles --------------------------------------------------------------------
    def node(self, nid, cx, cy, label, kind, cat, sub=None, w=None):
        self.nodes[nid] = (cx, cy)
        col = COLORS[cat]
        x, y = cx - TILE / 2, cy - TILE / 2
        shadow = f'<rect x="{x+2}" y="{y+3}" width="{TILE}" height="{TILE}" rx="12" fill="#000" opacity="0.10"/>'
        tile = f'<rect x="{x}" y="{y}" width="{TILE}" height="{TILE}" rx="12" fill="{col}"/>'
        self.body.append(shadow + tile + glyph(kind, cx, cy))
        lines = label.split("\n")
        ty = cy + TILE / 2 + 15
        for i, ln in enumerate(lines):
            self.body.append(f'<text x="{cx}" y="{ty + i*14}" text-anchor="middle" font-size="12.5" font-weight="600" fill="#202124" font-family="{FONT}">{_e(ln)}</text>')
        if sub:
            for j, ln in enumerate(sub.split("\n")):
                self.body.append(f'<text x="{cx}" y="{ty + len(lines)*14 + j*12 - 1}" text-anchor="middle" font-size="10.5" fill="#5f6368" font-family="{FONT}">{_e(ln)}</text>')

    def small(self, nid, cx, cy, label, kind, cat):
        """A compact tile for things inside a cluster (pods, namespaces)."""
        self.nodes[nid] = (cx, cy)
        col = COLORS[cat]
        t = 44
        self.body.append(f'<rect x="{cx-t/2}" y="{cy-t/2}" width="{t}" height="{t}" rx="10" fill="{col}"/>')
        self.body.append(glyph(kind, cx, cy).replace('stroke-width="2.6"', 'stroke-width="2.2"'))
        for i, ln in enumerate(label.split("\n")):
            self.body.append(f'<text x="{cx}" y="{cy+t/2+13+i*12.5}" text-anchor="middle" font-size="11.5" font-weight="600" fill="#202124" font-family="{FONT}">{_e(ln)}</text>')

    def text(self, x, y, s, size=12, color="#5f6368", weight="400", anchor="start"):
        self.body.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" font-weight="{weight}" fill="{color}" font-family="{FONT}">{_e(s)}</text>')

    # ---- connectors -----------------------------------------------------------------------
    def _anchor(self, nid, side, half=TILE / 2):
        cx, cy = self.nodes[nid]
        return {"r": (cx + half, cy), "l": (cx - half, cy), "t": (cx, cy - half), "b": (cx, cy + half + 0)}[side]

    def edge(self, a, b, route="h", num=None, label=None, color="#3c4043", dash=False, sides=None, bend=None, lab_dy=-8, half_a=TILE / 2, half_b=TILE / 2):
        """Orthogonal connector from node a to node b.
        route: 'h' straight horizontal, 'v' straight vertical, 'hv' horizontal then vertical,
               'vh' vertical then horizontal, 'z' horizontal-vertical-horizontal via x=bend,
               'zv' vertical-horizontal-vertical via y=bend."""
        ax, ay = self.nodes[a]
        bx, by = self.nodes[b]
        sa, sb = sides or (None, None)
        if route == "h":
            sa = sa or ("r" if bx > ax else "l"); sb = sb or ("l" if bx > ax else "r")
        elif route == "v":
            sa = sa or ("b" if by > ay else "t"); sb = sb or ("t" if by > ay else "b")
        elif route == "hv":
            sa = sa or ("r" if bx > ax else "l"); sb = sb or ("t" if by > ay else "b")
        elif route == "vh":
            sa = sa or ("b" if by > ay else "t"); sb = sb or ("l" if bx > ax else "r")
        elif route == "z":
            sa = sa or ("r" if bx > ax else "l"); sb = sb or ("l" if bx > ax else "r")
        elif route == "zv":
            sa = sa or ("b" if by > ay else "t"); sb = sb or ("t" if by > ay else "b")
        p0 = self._anchor(a, sa, half_a)
        p1 = self._anchor(b, sb, half_b)
        pts = [p0]
        if route == "hv":
            pts.append((p1[0], p0[1]))
        elif route == "vh":
            pts.append((p0[0], p1[1]))
        elif route == "z":
            mx = bend if bend is not None else (p0[0] + p1[0]) / 2
            pts += [(mx, p0[1]), (mx, p1[1])]
        elif route == "zv":
            my = bend if bend is not None else (p0[1] + p1[1]) / 2
            pts += [(p0[0], my), (p1[0], my)]
        pts.append(p1)
        self._poly(pts, color, dash, num, label, lab_dy)

    def path(self, pts, num=None, label=None, color="#3c4043", dash=False, lab_dy=-8, lab_at=None):
        self._poly(pts, color, dash, num, label, lab_dy, lab_at)

    def _poly(self, pts, color, dash, num, label, lab_dy, lab_at=None):
        d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        da = 'stroke-dasharray="6 4"' if dash else ""
        self.body.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" {da} marker-end="url(#arr-{color[1:]})"/>')
        self._markers = getattr(self, "_markers", set()) | {color}
        # badge/label sit on the longest segment
        best, blen = 0, -1
        for i in range(len(pts) - 1):
            l = abs(pts[i + 1][0] - pts[i][0]) + abs(pts[i + 1][1] - pts[i][1])
            if l > blen:
                best, blen = i, l
        (x0, y0), (x1, y1) = pts[best], pts[best + 1]
        mx, my = lab_at or ((x0 + x1) / 2, (y0 + y1) / 2)
        if num is not None:
            self.badges.append(self._badge(mx, my, str(num), color))
        if label:
            horiz = abs(x1 - x0) >= abs(y1 - y0)
            tx, ty = (mx, my + lab_dy - (10 if num is not None else 0)) if horiz else (mx + 12 + (10 if num is not None else 0), my + 4)
            anchor = "middle" if horiz else "start"
            self.badges.append(f'<text x="{tx}" y="{ty}" text-anchor="{anchor}" font-size="10.5" fill="#3c4043" font-family="{FONT}" paint-order="stroke" stroke="#fff" stroke-width="4">{_e(label)}</text>')

    @staticmethod
    def _badge(x, y, text, color="#3c4043"):
        r = 10.5 if len(text) < 2 else 11.5
        return (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#fff" stroke="{color}" stroke-width="2"/>'
            f'<text x="{x:.1f}" y="{y+4.2:.1f}" text-anchor="middle" font-size="11.5" font-weight="700" fill="{color}" font-family="{FONT}">{_e(text)}</text>'
        )

    def badge(self, x, y, text, color="#3c4043"):
        self.badges.append(self._badge(x, y, text, color))

    # ---- legend ---------------------------------------------------------------------------
    def legend(self, x, y, title, rows, w=360, color="#3c4043"):
        h = 34 + len(rows) * 22
        out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#fff" stroke="#dadce0" stroke-width="1.4"/>',
               f'<text x="{x+16}" y="{y+23}" font-size="13" font-weight="700" fill="#202124" font-family="{FONT}">{_e(title)}</text>']
        for i, (num, txt) in enumerate(rows):
            yy = y + 46 + i * 22
            out.append(self._badge(x + 26, yy - 4, num, color))
            out.append(f'<text x="{x+46}" y="{yy}" font-size="12" fill="#3c4043" font-family="{FONT}">{_e(txt)}</text>')
        self.body.append("".join(out))
        return h

    def key(self, x, y):
        items = [("compute", "Compute / containers"), ("network", "Networking"), ("data", "Data"), ("ai", "AI / ML"),
                 ("security", "Security"), ("ops", "Operations"), ("dev", "Developer tooling")]
        out = [f'<text x="{x}" y="{y}" font-size="12" font-weight="700" fill="#202124" font-family="{FONT}">Service categories</text>']
        for i, (c, t) in enumerate(items):
            xx = x + (i % 4) * 158
            yy = y + 20 + (i // 4) * 22
            out.append(f'<rect x="{xx}" y="{yy-11}" width="14" height="14" rx="3" fill="{COLORS[c]}"/><text x="{xx+22}" y="{yy}" font-size="11.5" fill="#3c4043" font-family="{FONT}">{t}</text>')
        self.body.append("".join(out))

    # ---- output ---------------------------------------------------------------------------
    def svg(self) -> str:
        cols = getattr(self, "_markers", {"#3c4043"}) | {"#3c4043"}
        defs = "".join(
            f'<marker id="arr-{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 1 L10 5 L0 9 z" fill="{c}"/></marker>'
            for c in cols
        )
        head = (
            f'<text x="34" y="44" font-size="24" font-weight="800" fill="#202124" font-family="{FONT}">{_e(self.title)}</text>'
            f'<text x="34" y="66" font-size="13.5" fill="#5f6368" font-family="{FONT}">{_e(self.subtitle)}</text>'
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}">'
            f'<defs>{defs}</defs><rect width="{self.w}" height="{self.h}" fill="#ffffff"/>{head}'
            + "".join(self.groups) + "".join(self.body) + "".join(self.badges) + "</svg>"
        )

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.svg())
