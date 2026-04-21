"""
Рендер слайда «Сколько стоит онбординг разработчика» 1920×1080 PNG.
Светлая тема, editorial-style. Без внешних зависимостей (только Pillow).
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1920, 1080

# ── Палитра ───────────────────────────────────────────────
BG        = (251, 249, 245)   # #FBF9F5
CARD      = (255, 255, 255)
BORDER    = (229, 224, 214)
INK       = (18, 22, 32)
INK_SOFT  = (89, 97, 112)
INK_MUTED = (144, 149, 159)
ACCENT    = (40, 78, 231)
RED       = (223, 69, 66)
GREEN     = (34, 144, 94)
GOLD      = (243, 194, 56)

# ── Шрифты (macOS system) ────────────────────────────────
F_REG   = "/System/Library/Fonts/Supplemental/Arial.ttf"
F_BOLD  = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
F_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"

def font(path, size):
    return ImageFont.truetype(path, size)

# ── Canvas ────────────────────────────────────────────────
img = Image.new("RGB", (W, H), BG)

# ── Декоративные градиентные блобы ───────────────────────
def radial_blob(cx, cy, radius, color, max_alpha):
    size = radius * 2
    blob = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = blob.load()
    for y in range(size):
        for x in range(size):
            dx, dy = x - radius, y - radius
            d = (dx * dx + dy * dy) ** 0.5
            if d >= radius:
                continue
            t = 1.0 - d / radius
            alpha = int(max_alpha * (t ** 2))
            px[x, y] = (color[0], color[1], color[2], alpha)
    img.paste(blob, (cx - radius, cy - radius), blob)

radial_blob(1760, 80,  360, ACCENT, 40)    # верхний правый угол — синий
radial_blob(80,   1060, 280, GOLD,   56)   # нижний левый — тёплый

draw = ImageDraw.Draw(img)

# ── Заголовок ─────────────────────────────────────────────
# Top rule
draw.rectangle([140, 120, 140 + 80, 120 + 3], fill=ACCENT)

# Eyebrow
eyebrow_font = font(F_BOLD, 20)
eyebrow = "HEISENBUG 2026 — ИССЛЕДОВАНИЕ"
# ручной letter-spacing 12%
x = 140
y_eyebrow = 140
for ch in eyebrow:
    draw.text((x, y_eyebrow), ch, font=eyebrow_font, fill=ACCENT)
    bbox = eyebrow_font.getbbox(ch)
    x += (bbox[2] - bbox[0]) + 3

# Title — две строки
title_font = font(F_BLACK, 88)
draw.text((140, 190), "Сколько стоит",            font=title_font, fill=INK)
draw.text((140, 295), "онбординг разработчика",   font=title_font, fill=INK)

# Subtitle
sub_font = font(F_REG, 26)
draw.text(
    (140, 425),
    "Прямой сетап + ежемесячные потери продуктивности в период ramp-up",
    font=sub_font, fill=INK_SOFT,
)

# ── Карточка таблицы ──────────────────────────────────────
T_X, T_Y = 140, 520
T_W = 1640
HDR_H = 64
ROW_H = 86
ROWS_N = 5
T_H = HDR_H + ROW_H * ROWS_N

# Тень: рисуем размытый тёмный прямоугольник под карточкой
shadow = Image.new("RGBA", (T_W + 120, T_H + 120), (0, 0, 0, 0))
sd = ImageDraw.Draw(shadow)
sd.rounded_rectangle(
    [60, 80, 60 + T_W, 80 + T_H],
    radius=28, fill=(18, 22, 32, 38),
)
shadow = shadow.filter(ImageFilter.GaussianBlur(30))
img.paste(shadow, (T_X - 60, T_Y - 60), shadow)

# Карточка
draw.rounded_rectangle(
    [T_X, T_Y, T_X + T_W, T_Y + T_H],
    radius=28, fill=CARD,
)

# ── Заголовок таблицы ────────────────────────────────────
PAD_L = 48
COL_REGION = 420
COL_SETUP  = 520
COL_ONB_X  = T_X + PAD_L + COL_REGION + COL_SETUP

def draw_tracked(draw_obj, text, pos, f, fill, tracking_px=2):
    x, y = pos
    for ch in text:
        draw_obj.text((x, y), ch, font=f, fill=fill)
        bbox = f.getbbox(ch)
        x += (bbox[2] - bbox[0]) + tracking_px

hdr_font = font(F_BOLD, 16)
hdr_y = T_Y + (HDR_H - 16) // 2 + 10
draw_tracked(draw, "РЕГИОН",          (T_X + PAD_L,                      hdr_y), hdr_font, INK_MUTED, 2)
draw_tracked(draw, "СЕТАП",           (T_X + PAD_L + COL_REGION,         hdr_y), hdr_font, INK_MUTED, 2)
draw_tracked(draw, "ОНБОРДИНГ / МЕС", (COL_ONB_X,                        hdr_y), hdr_font, INK_MUTED, 2)

# подчёркивание заголовка
draw.line(
    [(T_X + PAD_L, T_Y + HDR_H), (T_X + T_W - PAD_L, T_Y + HDR_H)],
    fill=BORDER, width=1,
)

# ── Строки данных ────────────────────────────────────────
rows = [
    ("Европа",    "€3–5k",      "€7–10k",      None,            None),
    ("США",       "$1–2k",      "$20k",        "Самый дорогой", RED),
    ("Россия",    "50–80k ₽",   "100–250k ₽",  None,            None),
    ("Азия",      "$1–2k",      "$3–5k",       "Выгодный",      GREEN),
    ("В среднем", "$1–3k",      "$4–8k",       None,            None),
]

name_font  = font(F_BOLD,  32)
setup_font = font(F_BOLD,  34)
hero_font  = font(F_BLACK, 48)
pill_font  = font(F_BLACK, 15)

for idx, (name, setup, onb, tag, tag_color) in enumerate(rows):
    y = T_Y + HDR_H + ROW_H * idx

    # разделитель (кроме последней)
    if idx < ROWS_N - 1:
        draw.line(
            [(T_X + PAD_L, y + ROW_H), (T_X + T_W - PAD_L, y + ROW_H)],
            fill=(229, 224, 214), width=1,
        )

    # Регион — цветной индикатор слева (маленькая точка)
    dot_r = 6
    dot_color = (ACCENT if idx == 0
                 else RED if idx == 1
                 else INK_SOFT if idx == 2
                 else GREEN if idx == 3
                 else INK_MUTED)
    cy = y + ROW_H // 2
    draw.ellipse([T_X + PAD_L, cy - dot_r,
                  T_X + PAD_L + dot_r * 2, cy + dot_r],
                 fill=dot_color)

    # имя
    text_y = y + (ROW_H - 32) // 2 - 2
    draw.text((T_X + PAD_L + 32, text_y), name, font=name_font, fill=INK)

    # setup
    setup_y = y + (ROW_H - 34) // 2 - 2
    draw.text((T_X + PAD_L + COL_REGION, setup_y), setup, font=setup_font, fill=INK_SOFT)

    # hero number
    hero_y = y + (ROW_H - 48) // 2 - 4
    draw.text((COL_ONB_X, hero_y), onb, font=hero_font, fill=INK)

    # pill
    if tag and tag_color:
        onb_bbox = hero_font.getbbox(onb)
        onb_w = onb_bbox[2] - onb_bbox[0]
        pill_x = COL_ONB_X + onb_w + 20
        pill_text = tag.upper()
        pt_bbox = pill_font.getbbox(pill_text)
        pt_w = pt_bbox[2] - pt_bbox[0]
        pill_pad_x = 16
        pill_pad_y = 8
        pill_h = 30
        pill_w = pt_w + pill_pad_x * 2 + (len(pill_text) - 1) * 1  # + tracking
        pill_y = y + (ROW_H - pill_h) // 2 + 3

        # фон pill — прозрачный оверлей
        pill_bg = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
        pd = ImageDraw.Draw(pill_bg)
        pd.rounded_rectangle(
            [0, 0, pill_w, pill_h],
            radius=pill_h // 2,
            fill=(tag_color[0], tag_color[1], tag_color[2], 28),
            outline=(tag_color[0], tag_color[1], tag_color[2], 110),
            width=1,
        )
        img.paste(pill_bg, (pill_x, pill_y), pill_bg)

        # текст pill с tracking
        tx = pill_x + pill_pad_x
        ty = pill_y + (pill_h - 15) // 2 - 2
        for ch in pill_text:
            draw.text((tx, ty), ch, font=pill_font, fill=tag_color)
            b = pill_font.getbbox(ch)
            tx += (b[2] - b[0]) + 1

# ── Футер ─────────────────────────────────────────────────
foot_y = T_Y + T_H + 48
# accent dash
draw.rectangle([140, foot_y + 12, 140 + 40, foot_y + 14], fill=ACCENT)
note_font = font(F_BOLD, 18)
draw.text(
    (200, foot_y),
    "Без учёта рекрутинга, оборудования и налогов. Цифры — медианы по открытым отчётам.",
    font=note_font, fill=INK_SOFT,
)
src_font = font(F_REG, 16)
draw.text(
    (140, foot_y + 38),
    "Источники: Stripe Developer Coefficient · Boundless · getDX · Computerra · cloudviewpartners · whatfix",
    font=src_font, fill=INK_MUTED,
)

# ── Сохраняем ─────────────────────────────────────────────
out = "/Users/nikitarulenko/Downloads/heisenbug-research/assets/onboarding_cost_slide.png"
img.save(out, "PNG", optimize=True)
print(f"saved: {out}  ({W}x{H})")
