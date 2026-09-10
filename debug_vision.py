"""Диагностика зрения. Запуск при открытом списке трейдов (или окне трейда):
    python debug_vision.py

Покажет: режим мыши, что читает OCR в каждой области, ищутся ли шаблоны
и с каким счётом. Картинки-вырезки сохранит в debug\ — посмотри их глазами.
"""
import os
import sys

import cv2

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import mouse  # noqa: E402
import yaml  # noqa: E402
from vision import Screen, expand, norm_nick, ocr_nick, ocr_number, ocr_text  # noqa: E402

cfg_path = os.path.join(BASE, "config.yaml")
if not os.path.exists(cfg_path):
    print("Нет config.yaml — сначала python calibrate.py")
    sys.exit(1)
with open(cfg_path, encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
tpl_dir = cfg.get("templates_dir", "templates")
reg = cfg.get("regions", {}) or {}

print("Мышь        :", mouse.mode())
print("Админ       :", mouse.is_admin())
print("Окно Roblox :", "найдено" if mouse.roblox_window() else "НЕ найдено")
screen = Screen()
print("Экран       :", screen.w, "x", screen.h, "| калибровка:", cfg.get("screen"))
os.makedirs(os.path.join(BASE, "debug"), exist_ok=True)

print("\n--- шаблоны (best score на всём экране) ---")
for name in ("person", "badge", "accept", "decline", "close", "accept_trade", "decline_trade", "plus"):
    p = os.path.join(BASE, tpl_dir, f"{name}.png")
    if not os.path.exists(p):
        print(f"{name:14} НЕТ templates/{name}.png")
        continue
    hit = screen.find(p, thr=0.0)
    print(f"{name:14} score={hit[2]:.3f} at {hit[0]},{hit[1]}" if hit else f"{name:14} не найден")

print("\n--- OCR областей (вырезки в debug\\) ---")
for key in ("row_nick", "row_accept", "row_decline", "their_total", "our_total", "pager", "partner_name"):
    if key not in reg:
        print(f"{key:14} нет в config.yaml")
        continue
    img = screen.grab(reg[key])
    out = os.path.join(BASE, "debug", f"{key}.png")
    cv2.imwrite(out, img)
    if key == "row_nick":
        val = ocr_nick(img, cfg.get("tesseract_cmd", ""), cfg.get("ocr_lang", "eng"))
        print(f"{key:14} OCR nick = '{val}' (norm '{norm_nick(val)}')  -> debug/{key}.png")
    elif key in ("their_total", "our_total"):
        val = ocr_number(img, cfg.get("tesseract_cmd", ""))
        print(f"{key:14} OCR number = {val}  -> debug/{key}.png")
    else:
        val = ocr_text(img, "0123456789/", 7, cfg.get("tesseract_cmd", ""), cfg.get("ocr_lang", "eng"))
        print(f"{key:14} OCR = '{val}'  -> debug/{key}.png")

if "their_grid" in reg:
    x1, y1, x2, y2 = reg["their_grid"]
    n = 0
    for r in range(3):
        for c in range(3):
            cell = screen.grab([
                x1 + (x2 - x1) * c / 3, y1 + (y2 - y1) * r / 3,
                x1 + (x2 - x1) * (c + 1) / 3, y1 + (y2 - y1) * (r + 1) / 3,
            ])
            cv2.imwrite(os.path.join(BASE, "debug", f"cell_{n}.png"), cell)
            n += 1
    print("Ячейки сетки сохранены: debug/cell_0..8.png")

print("\nГотово. Открой папку debug и сверь: то ли вырезали, что ожидал?")
