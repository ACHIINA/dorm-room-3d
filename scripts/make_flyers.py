"""廊下の掲示板の貼り紙と、ドアのホワイトボードの落書きを作る(PIL)。
実行: python3 scripts/make_flyers.py  → textures/hall/*.png"""
import os, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "textures", "hall")
os.makedirs(OUT, exist_ok=True)
Image.MAX_IMAGE_PIXELS = None
SUP = "/System/Library/Fonts/Supplemental/"
F = lambda name, size: ImageFont.truetype(SUP + name, size)
random.seed(4)


def paper(w, h, col=(240, 236, 226)):
    im = Image.new("RGB", (w, h), col)
    noise = Image.effect_noise((w, h), 8).convert("RGB")
    return Image.blend(im, noise, 0.04)


def centered(d, y, text, font, fill, w):
    tw = d.textlength(text, font=font)
    d.text(((w - tw) / 2, y), text, font=font, fill=fill)


def finish(im, name):
    im = im.filter(ImageFilter.GaussianBlur(0.4))
    im.save(os.path.join(OUT, name + ".png"))
    # 向かいの壁(+Y 向き)に貼ると左右が逆に投影されるので、反転版も用意する
    im.transpose(Image.FLIP_LEFT_RIGHT).save(os.path.join(OUT, name + "_m.png"))


W, H = 600, 800
# 1. 階のミーティング
im = paper(W, H)
d = ImageDraw.Draw(im)
d.rectangle((0, 0, W, 150), fill=(178, 82, 40))
centered(d, 38, "FLOOR 3", F("Arial Black.ttf", 66), (250, 240, 225), W)
centered(d, 200, "Floor Meeting", F("Georgia Bold.ttf", 62), (40, 34, 30), W)
centered(d, 300, "Sunday · 8:00 PM", F("Arial.ttf", 42), (60, 52, 46), W)
centered(d, 360, "3rd Floor Lounge", F("Arial.ttf", 42), (60, 52, 46), W)
centered(d, 470, "Pizza provided", F("Arial Bold Italic.ttf", 40), (178, 82, 40), W)
centered(d, 690, "— your RA, Maya", F("Arial Italic.ttf", 30), (90, 80, 70), W)
finish(im, "flyer_meeting")

# 2. 勉強会
im = paper(W, H, (226, 236, 228))
d = ImageDraw.Draw(im)
centered(d, 70, "STATS 201", F("Arial Black.ttf", 70), (40, 70, 52), W)
centered(d, 170, "Study Group", F("Georgia Bold.ttf", 58), (30, 40, 34), W)
for i, line in enumerate(["Thursdays 7–9 PM", "Library, 3rd floor", "Room 3B (whiteboard!)", "All levels welcome"]):
    centered(d, 300 + i * 60, line, F("Arial.ttf", 38), (50, 60, 54), W)
for i in range(8):  # 切り取りタブ
    x = 10 + i * 73
    d.rectangle((x, 660, x + 66, 790), outline=(120, 130, 120), width=2)
    tab = Image.new("RGBA", (130, 40), (0, 0, 0, 0))
    ImageDraw.Draw(tab).text((4, 4), "stats201@", font=F("Arial.ttf", 20), fill=(60, 70, 64))
    tab = tab.rotate(90, expand=True)
    im.paste(tab, (x + 18, 662), tab)
finish(im, "flyer_study")

# 3. 静かな時間
im = paper(W, H, (236, 232, 245))
d = ImageDraw.Draw(im)
centered(d, 120, "QUIET", F("Arial Black.ttf", 120), (50, 52, 92), W)
centered(d, 260, "HOURS", F("Arial Black.ttf", 120), (50, 52, 92), W)
d.line((90, 430, 510, 430), fill=(50, 52, 92), width=4)
centered(d, 470, "Sun–Thu  10 PM – 8 AM", F("Arial Bold.ttf", 40), (60, 60, 80), W)
centered(d, 530, "Fri–Sat  12 AM – 9 AM", F("Arial Bold.ttf", 40), (60, 60, 80), W)
centered(d, 650, "Thanks for being a good neighbor", F("Arial Italic.ttf", 28), (90, 90, 110), W)
finish(im, "flyer_quiet")

# 4. 写真付きのサッカー部員募集
im = paper(W, H)
pano = Image.open(os.path.join(ROOT, "assets_polyhaven", "photos", "autumn_hockey.jpg")).convert("RGB")
pw, ph = pano.size
photo = pano.crop((int(pw * 0.55), int(ph * 0.38), int(pw * 0.70), int(ph * 0.52))).resize((520, 380))
photo = ImageEnhance.Contrast(photo).enhance(1.1)
im.paste(photo, (40, 40))
d = ImageDraw.Draw(im)
centered(d, 450, "Intramural", F("Georgia Bold.ttf", 56), (40, 34, 30), W)
centered(d, 520, "SOCCER", F("Arial Black.ttf", 76), (34, 92, 60), W)
centered(d, 640, "Sign up at the Rec Center by Friday", F("Arial.ttf", 28), (60, 52, 46), W)
finish(im, "flyer_soccer")

# 5. ドアのホワイトボード(マーカーの落書き)
for i, (msg, col) in enumerate([("Welcome back, Jordan!", (30, 90, 160)), ("Gone to the library\nback at 10", (180, 50, 40)),
                                  ("Sam & Lee", (40, 120, 70))]):
    im = Image.new("RGB", (500, 360), (246, 247, 246))
    d = ImageDraw.Draw(im)
    for j, line in enumerate(msg.split("\n")):
        d.text((30, 60 + j * 70), line, font=ImageFont.truetype(SUP + "Chalkboard.ttc", 38), fill=col)
    d.ellipse((380, 230, 460, 310), outline=col, width=5)
    d.arc((395, 255, 445, 295), 20, 160, fill=col, width=5)
    d.ellipse((400, 250, 410, 262), fill=col)
    d.ellipse((430, 250, 440, 262), fill=col)
    finish(im, f"whiteboard_{i}")
print(sorted(os.listdir(OUT)))


# 6. 315 号室のポスター(架空のバンドのツアー、映画の上映会)
im = Image.new("RGB", (600, 860), (24, 22, 40))
d = ImageDraw.Draw(im)
for i in range(14):
    d.ellipse((300 - 40 * i, 330 - 40 * i, 300 + 40 * i, 330 + 40 * i), outline=(220, 90 + i * 8, 120), width=3)
centered(d, 600, "THE MIDNIGHT ECHOES", F("Arial Black.ttf", 40), (245, 225, 200), 600)
centered(d, 660, "FALL TOUR", F("Arial Bold.ttf", 34), (230, 120, 130), 600)
centered(d, 720, "Oct 24 · Student Union Hall", F("Arial.ttf", 26), (210, 200, 190), 600)
finish(im, "poster_band")
im = Image.new("RGB", (600, 860), (232, 222, 196))
d = ImageDraw.Draw(im)
d.rectangle((40, 40, 560, 560), fill=(40, 70, 90))
d.ellipse((330, 90, 500, 260), fill=(240, 200, 120))
d.polygon([(40, 560), (220, 300), (360, 560)], fill=(30, 50, 60))
d.polygon([(200, 560), (400, 260), (560, 560)], fill=(24, 40, 48))
centered(d, 600, "MOVIE NIGHT", F("Arial Black.ttf", 56), (40, 34, 30), 600)
centered(d, 680, "Fridays 9 PM · Lounge", F("Georgia Bold.ttf", 32), (120, 60, 40), 600)
centered(d, 740, "bring blankets & snacks", F("Arial Italic.ttf", 26), (90, 80, 70), 600)
finish(im, "poster_film")
print("posters ok")
