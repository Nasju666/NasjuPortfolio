"""Draws the flat images used on screens and posters in the room (PNG, into blender/textures/).
On the website the monitor, laptop and clock screens are replaced by live content;
these images are what the Blender render shows."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'textures')
os.makedirs(OUT, exist_ok=True)

FONT_DIRS = ['/usr/share/fonts/opentype/inter', '/usr/share/fonts/truetype/dejavu', 'C:/Windows/Fonts']


def font(size, bold=True):
    names = ['Inter-Bold.otf', 'InterDisplay-Bold.otf', 'DejaVuSans-Bold.ttf', 'arialbd.ttf'] if bold else ['Inter-Regular.otf', 'DejaVuSans.ttf', 'arial.ttf']
    for d in FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def rr(d, box, r, fill):
    d.rounded_rectangle(box, r, fill=fill)


def monitor():
    # Ultrawide 21:9 "projects" screen
    W, H = 1344, 576
    im = Image.new('RGB', (W, H), '#12162a')
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 44), fill='#1b2140')
    for i, c in enumerate(['#e0605e', '#f4b740', '#5ec27a']):
        d.ellipse((18 + i * 26, 15, 32 + i * 26, 29), fill=c)
    d.text((W // 2, 22), 'nasju / projects', font=font(20, False), fill='#9aa3c7', anchor='mm')
    d.text((60, 92), 'Projects', font=font(44), fill='#ffffff')
    cards = [('Kita', '#3b6cf5'), ('ElecTrack', '#21b07a'), ('Client app', '#f4b740'), ('Mine a Moon Ores', '#9b6cf5')]
    cw, ch, gap = 280, 300, 34
    x0 = (W - (cw * 4 + gap * 3)) // 2
    for i, (name, col) in enumerate(cards):
        x = x0 + i * (cw + gap)
        y = 190
        rr(d, (x, y, x + cw, y + ch), 22, '#1d2342')
        rr(d, (x + 16, y + 16, x + cw - 16, y + 170), 14, col)
        d.text((x + 22, y + 192), name, font=font(28), fill='#ffffff')
        d.rounded_rectangle((x + 22, y + 240, x + cw - 70, y + 252), 6, fill='#39406a')
        d.rounded_rectangle((x + 22, y + 264, x + cw - 120, y + 276), 6, fill='#39406a')
    im.save(os.path.join(OUT, 'screen_monitor.png'))


def laptop():
    W, H = 640, 400
    im = Image.new('RGB', (W, H), '#f2f4fa')
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 120, H), fill='#1f2a55')
    for i in range(5):
        rr(d, (16, 60 + i * 44, 104, 84 + i * 44), 8, '#3b4a8a' if i == 0 else '#2a3668')
    d.text((146, 24), 'Dashboard', font=font(30), fill='#1b2030')
    for i, c in enumerate(['#3b6cf5', '#21b07a', '#f4b740']):
        x = 146 + i * 160
        rr(d, (x, 80, x + 145, 170), 14, '#ffffff')
        rr(d, (x + 14, 96, x + 60, 108), 6, '#c9cfe0')
        d.text((x + 14, 120), ['1,284', '98%', '42'][i], font=font(30), fill=c)
    rr(d, (146, 190, 615, 375), 14, '#ffffff')
    import math
    pts = [(170 + i * 26, 330 - 70 * (0.5 + 0.5 * math.sin(i / 2.3)) - i * 3) for i in range(18)]
    d.line(pts, fill='#3b6cf5', width=5, joint='curve')
    im.save(os.path.join(OUT, 'screen_laptop.png'))


def clock():
    W, H = 512, 192
    im = Image.new('RGB', (W, H), '#0d0f16')
    d = ImageDraw.Draw(im)
    d.text((W // 2, H // 2 + 4), '09:41', font=font(128), fill='#f4f6ff', anchor='mm')
    im.save(os.path.join(OUT, 'screen_clock.png'))


def phone():
    W, H = 240, 480
    im = Image.new('RGB', (W, H), '#1a2240')
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line((0, y, W, y), fill=(int(40 + 60 * t), int(60 + 40 * t), int(140 - 30 * t)))
    d.text((W // 2, 120), '09:41', font=font(64), fill='#ffffff', anchor='mm')
    im.save(os.path.join(OUT, 'screen_phone.png'))


def poster():
    # Framed print standing on the shelf (About): a plain paper mat. The website draws the
    # profile photo on top of it (screen_print_photo), so the photo stays sharp and swappable.
    W, H = 600, 720
    im = Image.new('RGB', (W, H), '#f4f1ea')
    im.save(os.path.join(OUT, 'poster.png'))


def photo_slot():
    # Placeholder on the photo quads (the website draws the real photo); keeps their UV map in the export.
    Image.new('RGB', (8, 8), '#808080').save(os.path.join(OUT, 'photo_slot.png'))


def night():
    # Window view: city lights at night, slightly blurred like through glass.
    W, H = 512, 640
    im = Image.new('RGB', (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line((0, y, W, y), fill=(int(14 + 30 * t), int(20 + 26 * t), int(52 + 40 * t)))
    import random
    random.seed(4)
    for _ in range(14):
        x = random.randint(-20, W)
        w = random.randint(40, 110)
        h = random.randint(140, 380)
        d.rectangle((x, H - h, x + w, H), fill='#0e1222')
        for wy in range(H - h + 12, H - 6, 18):
            for wx in range(x + 8, x + w - 8, 14):
                if random.random() < 0.35:
                    d.rectangle((wx, wy, wx + 6, wy + 8), fill=random.choice(['#f6c76b', '#ffe3a3', '#9cc4ff']))
    im = im.filter(ImageFilter.GaussianBlur(1.6))
    im.save(os.path.join(OUT, 'window_night.png'))


if __name__ == '__main__':
    monitor(); laptop(); clock(); phone(); poster(); photo_slot(); night()
    print('textures ->', OUT)
