"""Калибровка: вырезает шаблоны кнопок и запоминает области.

ВАЖНО: скрипт ничего не фотает сам — перед каждым шагом он пишет
что открыть в игре, ты открываешь и жмёшь Enter. Потом обводишь рамкой
(Enter — ок, C — заново, Esc — пропуск) или кликаешь (Esc — дальше).

Запуск: python calibrate.py   (игра 1920x1080, окно видно)
В конце всё сохранится в config.yaml.
"""
import os

import cv2
import yaml
from mss import mss

BASE = os.path.dirname(os.path.abspath(__file__))
TPL_DIR = os.path.join(BASE, "templates")
CFG_EXAMPLE = os.path.join(BASE, "config.example.yaml")
CFG = os.path.join(BASE, "config.yaml")


def shot():
    with mss() as sct:
        mon = sct.monitors[1]
        import numpy as np

        img = cv2.cvtColor(np.array(sct.grab(mon)), cv2.COLOR_BGRA2BGR)
        return img, mon["width"], mon["height"]


def snap(prompt):
    print(f"\n>>> {prompt}")
    input("    Нажми Enter здесь, когда готово... ")
    return shot()


def ask_roi(img, title, hint):
    print(f"\n--- {title} ---\n{hint}\nРамка + Enter. C — заново. Esc — пропустить.")
    while True:
        r = cv2.selectROI(title, img, showCrosshair=True, fromCenter=False)
        cv2.destroyWindow(title)
        if r == (0, 0, 0, 0):
            return None
        x, y, w, h = (int(v) for v in r)
        if w > 4 and h > 4:
            return (x, y, w, h)
        print("Слишком мелко, ещё раз.")


def ask_clicks(img, title, hint, n=2):
    print(f"\n--- {title} ---\n{hint}\nКликай в окно. Esc — дальше.")
    pts = []

    def cb(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            pts.append((x, y))
            print(f"  точка {len(pts)}: ({x}, {y})")

    cv2.imshow(title, img)
    cv2.setMouseCallback(title, cb)
    while len(pts) < n:
        if cv2.waitKey(50) == 27:
            break
    cv2.destroyWindow(title)
    return pts


def frac(rect, w, h):
    x, y, rw, rh = rect
    return [round(x / w, 4), round(y / h, 4), round((x + rw) / w, 4), round((y + rh) / h, 4)]


def save_tpl(img, rect, name):
    x, y, w, h = rect
    cv2.imwrite(os.path.join(TPL_DIR, f"{name}.png"), img[y:y + h, x:x + w])
    print(f"  saved templates/{name}.png")


def main():
    os.makedirs(TPL_DIR, exist_ok=True)
    if os.path.exists(CFG):
        with open(CFG, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        with open(CFG_EXAMPLE, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    cfg.setdefault("regions", {})
    cfg.setdefault("points", {})

    # ШАГ 1: главный экран игры
    img, w, h = snap("ШАГ 1: открой игру на Trade Plaza (обычный вид, БЕЗ открытых окон).")
    print(f"Экран: {w}x{h}" + ("" if (w, h) == (1920, 1080) else " (советую 1920x1080!)"))
    cfg["screen"] = {"w": w, "h": h}
    cv2.imwrite(os.path.join(TPL_DIR, "_main.png"), img)
    for key, title in [
        ("person", "Иконка ЧЕЛОВЕЧКА слева (открывает список трейдов) — обведи впритык"),
        ("badge", "КРАСНЫЙ кружок уведомления (если прямо сейчас нет — Esc)"),
    ]:
        r = ask_roi(img, f"Шаблон: {title}", "Обведи ТОЛЬКО значок, без фона.")
        if r is not None:
            save_tpl(img, r, key)
        else:
            print(f"  пропуск {key}")

    # ШАГ 2: список трейдов
    img2, _, _ = snap("ШАГ 2: открой СПИСОК ТРЕЙДОВ (иконка человечка) — чтобы были видны строки игроков.")
    cv2.imwrite(os.path.join(TPL_DIR, "_list.png"), img2)
    for key, title in [
        ("accept", "ЗЕЛЁНАЯ кнопка ACCEPT в строке"),
        ("decline", "КРАСНАЯ кнопка DECLINE в строке"),
        ("close", "Кнопка CLOSE списка (если нет — Esc)"),
    ]:
        r = ask_roi(img2, f"Шаблон: {title}", "Обведи ТОЛЬКО кнопку, без фона.")
        if r is not None:
            save_tpl(img2, r, key)
        else:
            print(f"  пропуск {key}")

    r = ask_roi(img2, "Область: НИК первой строки", "Обведи ТОЛЬКО имя первой строки.")
    if r is not None:
        cfg["regions"]["row_nick"] = frac(r, w, h)
    pts = ask_clicks(img2, "Шаг строк", "Кликни ЦЕНТР ника 1-й строки, затем ЦЕНТР ника 2-й строки.", 2)
    if len(pts) == 2:
        cfg["points"]["row_step_y"] = abs(pts[1][1] - pts[0][1]) / h
        print(f"  row_step_y = {cfg['points']['row_step_y']:.4f}")
    for key, title in [
        ("row_accept", "Кнопка ACCEPT 1-й строки (рамкой)"),
        ("row_decline", "Кнопка DECLINE 1-й строки (рамкой)"),
    ]:
        r = ask_roi(img2, f"Область: {title}", "Обведи рамкой.")
        if r is not None:
            cfg["regions"][key] = frac(r, w, h)

    # ШАГ 3: окно трейда
    img3, _, _ = snap("ШАГ 3: открой ОКНО ТРЕЙДА с кем-нибудь (чтобы были видны слоты и кнопки).")
    cv2.imwrite(os.path.join(TPL_DIR, "_trade.png"), img3)
    for key, title in [
        ("accept_trade", "ЗЕЛЁНАЯ кнопка ACCEPT в окне трейда"),
        ("decline_trade", "КРАСНАЯ кнопка DECLINE в окне трейда"),
        ("plus", "ПЛЮС пустого слота (если нет пустых — Esc)"),
    ]:
        r = ask_roi(img3, f"Шаблон: {title}", "Обведи ТОЛЬКО кнопку/плюс, без фона.")
        if r is not None:
            save_tpl(img3, r, key)
        else:
            print(f"  пропуск {key}")
    for key, title in [
        ("their_total", "Надпись 'Total RAP: N' СПРАВА (их сторона)"),
        ("our_total", "Надпись 'Total RAP: N' СЛЕВА (наша сторона)"),
        ("pager", "Пагинация '1/1' под их сеткой (если нет — Esc)"),
        ("partner_name", "НИК партнёра вверху окна трейда"),
        ("their_grid", "ВСЯ их сетка 3x3 целиком"),
    ]:
        r = ask_roi(img3, f"Область: {title}", "Обведи рамкой. Esc — пропустить.")
        if r is not None:
            cfg["regions"][key] = frac(r, w, h)

    with open(CFG, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    print(f"\nГотово! config.yaml сохранён. Впиши тестовый ник в only_nicks и запускай: python bot.py")


if __name__ == "__main__":
    main()
