"""Text layers for the series: title card, place stamps, end card, thumbnail. Pillow only.

Imported by build_episodes.py and build_thumbnails.py; also runs on its own to preview one
layer of each kind:

  python textlayers.py --config series.json --preview <dir>

Every layer is drawn at the canvas size in series.json from the `design` block (colours, fonts,
sizes). Sizes are canvas pixels. The defaults reproduce the channel's first two series at 4K;
a 1080p series sets "text_scale": 0.5 (or its own sizes) in the design block.

Fonts are files: `design.fonts.sans` / `design.fonts.mono` point at TTFs (a variable font is
fine; `sans_weight` selects the instance). Letter-spacing and shadows are drawn by hand so the
result matches the CSS the layers were first designed in.
"""
import argparse, json, os, re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

DEFAULTS = {
    "paper": "#F5F1E8", "ink": "#25302D", "accent": "#6A4432", "rule": "#C9A88F",
    "text_scale": 1.0,
    # title card (over the first shot)
    "title_left": 96, "title_bottom": 92, "title_width": 1400,
    "title_eyebrow_size": 26, "title_eyebrow_tracking": 4, "title_eyebrow_gap": 14,
    "title_size": 88, "title_tracking": -2.5, "title_line_height": 1.05,
    "title_sub_size": 28, "title_sub_tracking": 3, "title_sub_gap": 16,
    "title_scrim_from": 0.55, "title_scrim_alpha": 0.55,
    # place stamp
    "stamp_left": 96, "stamp_bottom": 84, "stamp_size": 26, "stamp_tracking": 2,
    "stamp_rule": 2, "stamp_pad_top": 10,
    # end card
    "end_size": 64, "end_tracking": -1.5, "end_line_height": 1.15, "end_width": 1500,
    "end_sub_size": 26, "end_sub_tracking": 4, "end_sub_gap": 28,
    "end_credit_size": 18, "end_credit_tracking": 3, "end_credit_bottom": 44,
    # thumbnail (1280x720)
    "thumb_side": 56, "thumb_bottom": 52, "thumb_eyebrow_size": 24, "thumb_eyebrow_tracking": 5,
    "thumb_eyebrow_gap": 10, "thumb_size": 78, "thumb_tracking": -2.5, "thumb_line_height": 1.02,
    "thumb_scrim_from": 0.45, "thumb_scrim_alpha": 0.72,
}


def rgb(hexstr, alpha=255):
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


class Design:
    def __init__(self, cfg, base):
        d = dict(DEFAULTS); d.update(cfg.get("design", {}))
        self.d = d
        self.scale = float(d.get("text_scale", 1.0))
        fonts = d.get("fonts") or {}
        self.sans_path = str((base / fonts.get("sans", "assets/fonts/Montserrat[wght].ttf")).resolve())
        self.mono_path = str((base / fonts.get("mono", "assets/fonts/IBMPlexMono-Regular.ttf")).resolve())
        self.sans_weight = float(fonts.get("sans_weight", 700))
        self.serif_path = str((base / fonts["serif"]).resolve()) if fonts.get("serif") else None
        for p in (self.sans_path, self.mono_path) + ((self.serif_path,) if self.serif_path else ()):
            if not os.path.exists(p):
                raise SystemExit(f"font missing: {p}  (run scripts/fetch_fonts.py or set design.fonts)")
        self._cache = {}

    def px(self, key):
        return self.d[key] * self.scale

    def font(self, kind, size):
        key = (kind, round(size, 2))
        if key not in self._cache:
            if kind == "serif":
                if not self.serif_path:
                    raise SystemExit("design.fonts.serif not set")
                path = self.serif_path
            else:
                path = self.sans_path if kind == "sans" else self.mono_path
            f = ImageFont.truetype(path, int(round(size)))
            if kind == "sans":
                try:
                    f.set_variation_by_axes([self.sans_weight])
                except Exception:
                    pass                                     # a static TTF has no axes
            self._cache[key] = f
        return self._cache[key]


# --- drawing primitives ------------------------------------------------------------------

def text_width(font, text, tracking):
    if not text: return 0.0
    return sum(font.getlength(ch) for ch in text) + tracking * (len(text) - 1)


def draw_tracked(draw, xy, text, font, fill, tracking):
    """Draw text glyph by glyph with letter-spacing (CSS letter-spacing semantics)."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + tracking


def wrap(font, text, tracking, max_width):
    """CSS-style word wrap; an explicit <br> or newline always breaks."""
    lines = []
    for para in re.split(r"<br\s*/?>|\n", text):
        words, cur = para.split(), ""
        for w in words:
            cand = (cur + " " + w) if cur else w
            if cur and text_width(font, cand, tracking) > max_width:
                lines.append(cur); cur = w
            else:
                cur = cand
        lines.append(cur)
    return lines


def shadowed_block(size, lines, font, tracking, line_height, fill, shadow, align="left"):
    """Render wrapped lines onto a transparent RGBA layer with a CSS-like text-shadow.
    shadow = (dx, dy, blur, alpha). Returns (layer, block_height)."""
    W, H = size
    asc, desc = font.getmetrics()
    lh = font.size * line_height
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    txt = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    y = 0.0
    for ln in lines:
        w = text_width(font, ln, tracking)
        x = 0 if align == "left" else (W - w) / 2
        draw_tracked(d, (x, y + (lh - (asc + desc)) / 2), ln, font, fill, tracking)
        y += lh
    if shadow:
        dx, dy, blur, a = shadow
        sh = Image.new("RGBA", size, (0, 0, 0, 0))
        alpha = txt.getchannel("A").point(lambda v: int(v * a))
        sh.putalpha(alpha)
        sh = sh.transform(size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy))
        if blur: sh = sh.filter(ImageFilter.GaussianBlur(blur / 2))
        layer.alpha_composite(sh)
    layer.alpha_composite(txt)
    return layer, y


def gradient_scrim(size, start_frac, alpha):
    """Vertical scrim: transparent until start_frac of the height, then to black*alpha at the bottom."""
    W, H = size
    col = Image.new("L", (1, H), 0)
    px = col.load()
    y0 = int(H * start_frac)
    for y in range(H):
        px[0, y] = 0 if y < y0 else int(255 * alpha * (y - y0) / max(1, H - 1 - y0))
    scrim = Image.new("RGBA", size, (0, 0, 0, 255))
    scrim.putalpha(col.resize(size))
    return scrim


def paste_block(canvas, layer, block_h, left, bottom):
    """Place a rendered block so its bottom edge sits `bottom` px above the canvas bottom."""
    W, H = canvas.size
    y = int(round(H - bottom - block_h))
    canvas.alpha_composite(layer, (int(round(left)), max(0, y)) if left >= 0 else (0, max(0, y)))


# --- layers --------------------------------------------------------------------------------

def render_title(D, canvas, eyebrow, title, sub):
    """Title card overlay, transparent: scrim + eyebrow + wrapped title + sub line."""
    W, H = canvas
    img = gradient_scrim(canvas, D.d["title_scrim_from"], D.d["title_scrim_alpha"])
    paper = rgb(D.d["paper"])
    fe, ft, fs = D.font("mono", D.px("title_eyebrow_size")), D.font("sans", D.px("title_size")), D.font("mono", D.px("title_sub_size"))
    width = D.px("title_width")
    # build from the bottom up: sub, title, eyebrow
    sub_layer, sub_h = shadowed_block((int(width), int(fs.size * 2)), [sub], fs, D.px("title_sub_tracking"), 1.0,
                                      rgb(D.d["paper"], int(255 * .9)), None)
    lines = wrap(ft, title, D.px("title_tracking"), width)
    t_layer, t_h = shadowed_block((int(width) + 40, int(ft.size * D.d["title_line_height"] * len(lines)) + 30), lines, ft,
                                  D.px("title_tracking"), D.d["title_line_height"], paper, (0, 2 * D.scale, 24 * D.scale, .35))
    e_layer, e_h = shadowed_block((int(width), int(fe.size * 2)), [eyebrow], fe, D.px("title_eyebrow_tracking"), 1.0,
                                  rgb(D.d["paper"], int(255 * .85)), None)
    left, bottom = D.px("title_left"), D.px("title_bottom")
    paste_block(img, sub_layer, sub_h, left, bottom)
    bottom += sub_h + D.px("title_sub_gap")
    paste_block(img, t_layer, t_h, left, bottom)
    bottom += t_h + D.px("title_eyebrow_gap")
    paste_block(img, e_layer, e_h, left, bottom)
    return img


def render_stamp(D, canvas, text):
    """Place stamp overlay, transparent: a thin rule above mono letter-spaced text."""
    W, H = canvas
    img = Image.new("RGBA", canvas, (0, 0, 0, 0))
    f = D.font("mono", D.px("stamp_size"))
    tracking = D.px("stamp_tracking")
    w = text_width(f, text, tracking)
    layer, h = shadowed_block((int(w) + 40, int(f.size * 1.6)), [text], f, tracking, 1.0, rgb(D.d["paper"]),
                              (0, 1 * D.scale, 14 * D.scale, .55))
    left, bottom = D.px("stamp_left"), D.px("stamp_bottom")
    paste_block(img, layer, h, left, bottom)
    top = H - bottom - h - D.px("stamp_pad_top")
    ImageDraw.Draw(img).rectangle([left, top - D.px("stamp_rule"), left + w, top], fill=rgb(D.d["rule"]))
    return img


def render_end(D, canvas, big, small, credit):
    """End card, opaque paper: centred closing line, sub line, music credit at the foot."""
    W, H = canvas
    img = Image.new("RGBA", canvas, rgb(D.d["paper"]))
    ink, accent = rgb(D.d["ink"]), rgb(D.d["accent"])
    fb, fs, fc = D.font("sans", D.px("end_size")), D.font("mono", D.px("end_sub_size")), D.font("mono", D.px("end_credit_size"))
    lines = wrap(fb, big, D.px("end_tracking"), D.px("end_width"))
    b_layer, b_h = shadowed_block((W, int(fb.size * D.d["end_line_height"] * len(lines)) + 10), lines, fb,
                                  D.px("end_tracking"), D.d["end_line_height"], ink, None, align="center")
    s_layer, s_h = shadowed_block((W, int(fs.size * 2)), [small], fs, D.px("end_sub_tracking"), 1.0, accent, None, align="center")
    total = b_h + D.px("end_sub_gap") + s_h
    y = (H - total) / 2
    img.alpha_composite(b_layer, (0, int(y)))
    img.alpha_composite(s_layer, (0, int(y + b_h + D.px("end_sub_gap"))))
    if credit:
        c_layer, c_h = shadowed_block((W, int(fc.size * 2)), [credit], fc, D.px("end_credit_tracking"), 1.0,
                                      rgb(D.d["accent"], int(255 * .7)), None, align="center")
        paste_block(img, c_layer, c_h, 0, D.px("end_credit_bottom"))
    return img


def render_thumb(D, still_path, eyebrow, title, size=(1280, 720)):
    """YouTube thumbnail: hero still (cover-fit) + scrim + eyebrow + title. Sizes are unscaled 1280x720 px."""
    W, H = size
    im = Image.open(still_path).convert("RGB")
    r = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * r + .5), int(im.height * r + .5)), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    img = im.crop((x, y, x + W, y + H)).convert("RGBA")
    img.alpha_composite(gradient_scrim(size, D.d["thumb_scrim_from"], D.d["thumb_scrim_alpha"]))
    paper = rgb(D.d["paper"])
    fe, ft = D.font("mono", D.d["thumb_eyebrow_size"]), D.font("sans", D.d["thumb_size"])
    width = W - 2 * D.d["thumb_side"]
    lines = wrap(ft, title, D.d["thumb_tracking"], width)
    t_layer, t_h = shadowed_block((width + 40, int(ft.size * D.d["thumb_line_height"] * len(lines)) + 30), lines, ft,
                                  D.d["thumb_tracking"], D.d["thumb_line_height"], paper, (0, 3, 24, .5))
    e_layer, e_h = shadowed_block((width, int(fe.size * 2)), [eyebrow], fe, D.d["thumb_eyebrow_tracking"], 1.0,
                                  rgb(D.d["paper"], int(255 * .9)), None)
    bottom = D.d["thumb_bottom"]
    paste_block(img, t_layer, t_h, D.d["thumb_side"], bottom)
    paste_block(img, e_layer, e_h, D.d["thumb_side"], bottom + t_h + D.d["thumb_eyebrow_gap"])
    return img.convert("RGB")


def render_lockup(D, canvas, lines, position, top_px, color, shadow):
    """Static text lockup for social-reel: N lines, each its own font kind/size/tracking, one
    shared fill colour and shadow, centred horizontally and stacked with no gap between lines'
    own leading. Never animated - present for the reel's full length.

    lines: [{"text":..., "font": "sans"|"mono"|"serif", "size": px, "tracking": px}, ...]
    position: "top" (block's top edge sits `top_px` down from the canvas top) or "centre"
    (block vertically centred). shadow = (dx, dy, blur, alpha) or None."""
    W, H = canvas
    fill = rgb(color)
    sh = tuple(shadow) if shadow else None
    blocks = []
    for ln in lines:
        size = ln["size"] * D.scale
        tracking = ln.get("tracking", 0) * D.scale
        f = D.font(ln.get("font", "sans"), size)
        text = ln["text"]
        w = text_width(f, text, tracking)
        layer, h = shadowed_block((int(w) + 40, int(f.size * 1.3)), [text], f, tracking, 1.0,
                                  fill, sh, align="center")
        blocks.append((layer, h))
    total_h = sum(h for _, h in blocks)
    img = Image.new("RGBA", canvas, (0, 0, 0, 0))
    y = top_px * D.scale if position == "top" else (H - total_h) / 2
    for layer, h in blocks:
        lw, _ = layer.size
        img.alpha_composite(layer, (int(round((W - lw) / 2)), int(round(y))))
        y += h
    return img


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--preview", required=True, help="directory for one sample of each layer")
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8"))
    base = Path(a.config).resolve().parent / cfg.get("project", ".")
    D = Design(cfg, base)
    canvas = tuple(cfg.get("canvas", [1920, 1080]))
    out = Path(a.preview); out.mkdir(parents=True, exist_ok=True)
    tx = cfg.get("text", {})
    render_title(D, canvas, tx.get("first_series_line", "SERIES · MONTH YEAR"), "A title long enough to wrap onto a second line",
                 "EPISODE 01 · 6 SEP · SOMEWHERE · MORNING").save(out / "title.png")
    render_stamp(D, canvas, "Mae Kampong Village · evening").save(out / "stamp.png")
    render_end(D, canvas, tx.get("end_last", "The end."), tx.get("end_last_sub", "THE END"), tx.get("credit", "")).save(out / "end.png")
    print("wrote", out)
