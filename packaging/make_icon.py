"""Draw the Day After icon (BRAND.md §1): the 7seas-telemetrics glyph (two masts, two sails, hull baseline) with
the wordmark "day after", at 1024 px, saved as icon.ico (Windows), icon.png (macOS/Linux) and a 256 px preview.
Build-time only (Pillow)."""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
S = 1024
INK = (15, 15, 15, 255)
CRIMSON = (220, 20, 60, 255)


def font(size):
    names = ("seguisb.ttf", "segoeui.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "Helvetica.ttc", "Arial Bold.ttf")
    dirs = [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"), "/usr/share/fonts/truetype/dejavu",
            "/System/Library/Fonts", "/Library/Fonts", "/System/Library/Fonts/Supplemental"]
    for d in dirs:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except OSError:
                    pass
    try:
        return ImageFont.load_default(size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([16, 16, S - 16, S - 16], radius=180, fill=(250, 250, 250, 255), outline=(20, 20, 20, 255), width=8)
    src = {"baseline": ((385, 632), (830, 632)), "mast1": ((563, 103), (563, 706)), "mast2": ((676, 103), (676, 706)),
           "sail1": ((455, 632), (563, 238)), "sail2": ((566, 632), (676, 242))}
    gx0, gx1, gy0, gy1 = 385, 830, 103, 706
    scale = min(620 / (gx1 - gx0), 560 / (gy1 - gy0))
    ox, oy = (S - (gx1 - gx0) * scale) / 2, 90
    tr = lambda p: (ox + (p[0] - gx0) * scale, oy + (p[1] - gy0) * scale)
    stroke = max(6, int(13 * scale))
    for a, b in src.values():
        d.line([tr(a), tr(b)], fill=INK, width=stroke)
    f = font(128)
    w_day = d.textlength("day ", font=f)
    w_after = d.textlength("after", font=f)
    x0 = (S - w_day - w_after) / 2
    d.text((x0, 880), "day ", font=f, fill=INK, anchor="lm")
    d.text((x0 + w_day, 880), "after", font=f, fill=CRIMSON, anchor="lm")
    return img


def main() -> int:
    img = draw()
    img.save(os.path.join(HERE, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    img.save(os.path.join(HERE, "icon.png"))
    img.resize((256, 256), Image.LANCZOS).save(os.path.join(HERE, "icon_preview.png"))
    print("icon.ico, icon.png and icon_preview.png written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
