APP_DIR = "/system/apps/user/psychic_paper"

import sys
import os
import random

# Standalone bootstrap for finding app assets
os.chdir(APP_DIR)

# Standalone bootstrap for module imports
sys.path.insert(0, APP_DIR)

# Slightly psychic stationery, as carried by a certain Time Lord. It shows the
# onlooker whatever credentials they were half expecting to see - here, a random
# authority drawn fresh each time the app opens or a button is pressed.

# crisp fonts: a chunky one for the title, a small one for the fine print
title_font = pixel_font.load("/system/assets/fonts/absolute.ppf")
body_font = pixel_font.load("/system/assets/fonts/ark.ppf")

screen.antialias = image.X2

# the worn black leather of the wallet
leather = brush.pattern(color.rgb(40, 33, 28), color.rgb(24, 19, 16), 6)

# each credential: (organisation, [title lines], bearer, clearance, accent rgb)
cards = [
    ("U.N.I.T.",                ["SPECIAL", "AGENT"],       "Col. Lethbridge", "Access: All Areas",    (46, 110, 72)),
    ("GALLIFREY HIGH COUNCIL",  ["LORD", "PRESIDENT"],      "The Doctor",      "Authority: Absolute",  (130, 40, 52)),
    ("HEALTH & SAFETY EXEC.",   ["CHIEF", "INSPECTOR"],     "I. M. Watching",  "Permit: Unlimited",    (150, 96, 24)),
    ("INTERGALACTIC PRESS",     ["ROVING", "REPORTER"],     "Scoop Maxwell",   "Accredited: Press",    (32, 120, 128)),
    ("THE ROYAL SOCIETY",       ["SENIOR", "FELLOW"],       "Prof. A. Genius", "Guest of Honour",      (44, 72, 150)),
    ("GALACTIC POLICE",         ["DETECTIVE", "INSPECTOR"], "Badge No. 7",     "Warrant: Valid",       (36, 52, 104)),
    ("BANK OF THE UNIVERSE",    ["VAULT", "KEEPER"],        "V. I. Patron",    "Signatory: Vault 7",   (120, 96, 28)),
    ("THE RED GUIDE",           ["ANONYMOUS", "INSPECTOR"], "A. Gourmet",      "Table for One",        (168, 52, 52)),
    ("MIN. OF SILLY WALKS",     ["PERMANENT", "SECRETARY"], "Sir Humphrey",    "Pass: Whitehall",      (96, 104, 40)),
    ("CRUFTS DOG SHOW",         ["HEAD", "JUDGE"],          "K. Nine",         "Ring Access: All",     (110, 64, 150)),
]

# the buttons that re-roll the credential (any of them)
REROLL_BUTTONS = (BUTTON_A, BUTTON_B, BUTTON_C, BUTTON_UP, BUTTON_DOWN)

# the authority currently on show - random from the moment the app opens
current = random.randint(0, len(cards) - 1)


def reroll():
    # pick a fresh authority, never the one already showing
    global current
    current = random.choice([i for i in range(len(cards)) if i != current])


def center_text(text, y, cx=80):
    w, _ = screen.measure_text(text)
    screen.text(text, cx - (w / 2), y)


def draw_psychic_sheen(x0, y0, x1, y1):
    # a soft highlight that drifts across the card - the "psychic" shimmer
    span = x1 - x0
    centre = x0 + (badge.ticks / 14) % span
    for dx in range(-7, 8):
        a = 24 - abs(dx) * 3
        x = centre + dx
        if a > 0 and x0 <= x < x1:
            screen.pen = color.rgb(255, 255, 255, a)
            screen.line(x, y0, x, y1)


def draw_card(card):
    org, title_lines, bearer, clearance, accent = card
    accent_pen = color.rgb(*accent)
    accent_soft = color.rgb(accent[0], accent[1], accent[2], 110)
    cream = color.rgb(238, 232, 216)

    x, y, w, h = 8, 8, 144, 100

    # drop shadow, accent frame, then the cream card on top
    screen.pen = color.rgb(0, 0, 0, 90)
    screen.shape(shape.rounded_rectangle(x + 2, y + 4, w, h, 9))
    screen.pen = accent_pen
    screen.shape(shape.rounded_rectangle(x, y, w, h, 9))
    screen.pen = cream
    screen.shape(shape.rounded_rectangle(x + 2, y + 2, w - 4, h - 4, 7))

    # coloured header band carrying the organisation
    screen.pen = accent_pen
    screen.rectangle(x + 3, y + 3, w - 6, 16)
    screen.font = body_font
    screen.pen = color.rgb(245, 244, 238)
    center_text(org, y + 6)

    # the headline role, one short word per line
    screen.font = title_font
    screen.pen = color.rgb(44, 36, 30)
    ty = y + 26
    for line in title_lines:
        center_text(line, ty)
        _, line_h = screen.measure_text(line)
        ty += line_h + 1

    # divider rule
    screen.pen = accent_soft
    screen.rectangle(x + 16, ty + 1, w - 32, 1)

    # the fine print
    screen.font = body_font
    screen.pen = color.rgb(70, 62, 54)
    center_text("Bearer: " + bearer, ty + 6)
    screen.pen = accent_pen
    center_text(clearance, ty + 16)

    # an official-looking seal in the corner
    sx, sy = x + w - 22, y + h - 18
    screen.pen = accent_pen
    screen.shape(shape.circle(sx, sy, 8))
    screen.pen = cream
    screen.shape(shape.circle(sx, sy, 6))
    screen.pen = accent_pen
    screen.shape(shape.circle(sx, sy, 3))

    # psychic shimmer over the whole card
    draw_psychic_sheen(x + 4, y + 5, x + w - 4, y + h - 5)


def update():
    # the wallet leather behind the card
    screen.pen = leather
    screen.clear()

    # any button convinces the paper to show a different authority
    for button in REROLL_BUTTONS:
        if badge.pressed(button):
            reroll()
            break

    draw_card(cards[current])

    # gentle hint along the bottom
    screen.font = body_font
    screen.pen = color.rgb(196, 186, 172, 200)

run(update)
