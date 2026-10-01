#!/usr/bin/env python3
"""Check a run book page against the skill's mechanical rules.

Usage:
  python check_run_book.py <game-slug>-run-book.html
  python check_run_book.py --selftest

Exit code 0 = clean, 1 = problems (one per line), 2 = usage problem.
Standard library only.
"""
import math
import re
import sys
from html.parser import HTMLParser

MAP_CLASSES = {
    "room", "up", "open", "door", "gate", "fog", "ladder", "lbl", "route",
    "mk", "k-rest", "k-boss", "k-npc", "k-loot", "k-exit", "k-route",
}
PAINT_ATTRS = ("fill", "stroke", "style")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EDGE, APART = 14, 26  # reference/area-maps.md, "Done when"


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.errs = []
        self.slug = None
        self.sections = []      # stack: the area dict, or None for any other <section>
        self.area = None
        self.in_map = False
        self.mk = None          # data-n of the marker <g> awaiting its <circle>
        self.in_stops = False
        self.table = None
        self.in_tbody = False
        self.stop_ticks = {}    # data-t -> area id, stops only

    def err(self, msg):
        self.errs.append(msg)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if "data-slug" in a:
            self.slug = a["data-slug"]

        if tag == "section":
            area = None
            if "area" in cls:
                area = {"id": a.get("data-area") or a.get("id") or "?", "nomap": "nomap" in cls,
                        "stops": [], "ticks": 0, "marks": [], "box": None}
                self.area = area
            self.sections.append(area)
        elif tag == "table" and "data-total" in a:
            self.table = {"total": a["data-total"], "rows": 0}
        elif tag == "tbody":
            self.in_tbody = True
        elif tag == "tr" and self.table and self.in_tbody:
            qty = a.get("data-qty", "1")
            self.table["rows"] += int(qty) if qty.isdigit() else 1

        if not self.area:
            return
        area = self.area
        if tag == "svg" and not any(c.startswith("ico") for c in cls):
            self.in_map = True
            try:
                area["box"] = [float(v) for v in a.get("viewbox", "").split()]  # the parser lowercases names
            except ValueError:
                area["box"] = None
            if not area["box"] or len(area["box"]) != 4:
                self.err("area %s: map svg has no usable viewBox" % area["id"])
                area["box"] = None
        if self.in_map:
            for p in PAINT_ATTRS:
                if p in a:
                    self.err("area %s: <%s> carries %s= (classes only)" % (area["id"], tag, p))
            for c in cls:
                if c not in MAP_CLASSES:
                    self.err("area %s: unknown map class '%s' (renders black)" % (area["id"], c))
            if tag == "g" and "mk" in cls:
                self.mk = a.get("data-n")
            elif tag == "circle" and self.mk is not None:
                try:
                    area["marks"].append((self.mk, float(a["cx"]), float(a["cy"])))
                except (KeyError, ValueError):
                    self.err("area %s: marker %s has no cx/cy" % (area["id"], self.mk))
                self.mk = None
        elif tag == "ol" and "stops" in cls:
            self.in_stops = True
        elif tag == "li" and self.in_stops and "data-n" in a:
            area["stops"].append(a["data-n"])
        elif tag == "input" and self.in_stops and "data-t" in a:
            area["ticks"] += 1
            t = a["data-t"]
            if t in self.stop_ticks:
                self.err("tick '%s' is on two stops (areas %s and %s)" % (t, self.stop_ticks[t], area["id"]))
            self.stop_ticks[t] = area["id"]

    def handle_endtag(self, tag):
        if tag == "svg":
            self.in_map = False
        elif tag == "ol":
            self.in_stops = False
        elif tag == "tbody":
            self.in_tbody = False
        elif tag == "table" and self.table:
            t, self.table = self.table, None
            if t["total"].isdigit() and int(t["total"]) != t["rows"]:
                self.err("where-list: %d rows for a total of %s" % (t["rows"], t["total"]))
        elif tag == "section" and self.sections:
            area = self.sections.pop()
            if area:
                self.close_area(area)
                self.area = None

    def close_area(self, area):
        aid, n = area["id"], len(area["stops"])
        want = [str(i) for i in range(1, n + 1)]
        if area["stops"] != want:
            self.err("area %s: stops are numbered %s, expected 1..%d" % (aid, ",".join(area["stops"]), n))
        if area["ticks"] != n:
            self.err("area %s: %d ticks for %d stops" % (aid, area["ticks"], n))
        if area["nomap"]:
            if area["marks"]:
                self.err("area %s: nomap area has markers" % aid)
            return
        got = sorted((m[0] for m in area["marks"]), key=lambda s: int(s) if s and s.isdigit() else -1)
        if got != want:
            self.err("area %s: markers are %s, expected 1..%d" % (aid, ",".join(str(g) for g in got) or "none", n))
        box = area["box"]
        for i, (k, x, y) in enumerate(area["marks"]):
            if box and not (box[0] + EDGE <= x <= box[0] + box[2] - EDGE
                            and box[1] + EDGE <= y <= box[1] + box[3] - EDGE):
                self.err("area %s: marker %s sits within %dpx of the map edge" % (aid, k, EDGE))
            for k2, x2, y2 in area["marks"][i + 1:]:
                if math.hypot(x - x2, y - y2) < APART:
                    self.err("area %s: markers %s and %s are under %dpx apart" % (aid, k, k2, APART))


def check(html):
    page = Page()
    page.feed(html)
    errs = page.errs
    left = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", html)))
    if left:
        errs.append("placeholders left: " + " ".join(left[:8]) + (" …" if len(left) > 8 else ""))
    if not page.slug:
        errs.append("no data-slug (ticks and saved tab would collide with other run books)")
    elif not SLUG_RE.match(page.slug):
        errs.append("data-slug '%s' is not lowercase-with-dashes" % page.slug)
    return errs


GOOD = """<main data-slug="demo"><section class="panel"><section class="area" data-area="01">
<div class="map"><svg viewBox="0 0 520 300"><rect class="room up" x="1" y="1" width="9" height="9"/>
<g class="mk k-rest" data-n="1"><circle cx="70" cy="232" r="12"/><text>1</text></g>
<g class="mk k-boss" data-n="2"><circle cx="400" cy="80" r="15"/><text>2</text></g></svg></div>
<ol class="stops"><li data-n="1"><input type="checkbox" data-t="01-fire"></li>
<li data-n="2"><input type="checkbox" data-t="01-boss"></li></ol></section>
<section class="area nomap" data-area="02"><ol class="stops"><li data-n="1"><input type="checkbox" data-t="02-a"></li></ol></section>
</section><table data-total="3"><thead><tr><th></th></tr></thead><tbody><tr><td></td></tr><tr data-qty="2"><td></td></tr></tbody></table></main>"""

BAD = (GOOD.replace('cx="400" cy="80"', 'cx="80" cy="240"')          # too close
           .replace('class="room up"', 'class="room wall" fill="red"')  # unknown class + paint
           .replace('data-t="01-boss"', 'data-t="01-fire"')             # duplicate tick
           .replace('data-total="3"', 'data-total="4"')                 # where-list short
           .replace('data-slug="demo"', 'data-x="{{SLUG}}"'))           # placeholder, no slug


def selftest():
    assert check(GOOD) == [], check(GOOD)
    bad = "\n".join(check(BAD))
    for needle in ("apart", "unknown map class", "fill=", "two stops", "total of 4", "placeholders", "data-slug"):
        assert needle in bad, (needle, bad)
    print("selftest ok")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    if sys.argv[1] == "--selftest":
        selftest()
        sys.exit(0)
    with open(sys.argv[1], encoding="utf-8") as f:
        problems = check(f.read())
    for p in problems:
        print(p)
    print("%d problem(s)" % len(problems) if problems else "clean")
    sys.exit(1 if problems else 0)
