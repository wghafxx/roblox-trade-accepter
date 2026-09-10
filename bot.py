"""Тест-бот автопринятия кейсов (Trade Plaza).

ТЕСТ-РЕЖИМ: сайт не трогаем, ничего не зачисляем. Только клики в игре + логи.
Успешная сделка = строка 'ПРИНЯТО ... (TEST: без зачисления)'.

Запуск на ПК с игрой: python bot.py
Остановка: Ctrl+C в консоли (или закрыть консоль). Мышь во время кликов не трогать.
"""
import os
import sys
import time
import traceback
from datetime import datetime

import yaml

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import mouse  # noqa: E402
from mouse import click  # noqa: E402
from vision import (Screen, expand, nick_matches, norm_nick, ocr_nick,  # noqa: E402
                    ocr_number, ocr_text, slot_empty, wait_until)


def log(*a):
    msg = f"[{datetime.now().strftime('%H:%M:%S')}] " + " ".join(str(x) for x in a)
    print(msg, flush=True)
    with open(os.path.join(BASE, "bot.log"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")


class Cfg:
    def __init__(self, path):
        with open(path, encoding="utf-8") as f:
            self.d = yaml.safe_load(f)
        self.only = {norm_nick(n) for n in (self.d.get("only_nicks") or []) if norm_nick(n)}
        self.white = set(self.d.get("whitelist_rap", []))
        self.min_total = float(self.d.get("min_total_rap", 35))
        self.max_items = int(self.d.get("max_items", 6))
        self.strict_page = bool(self.d.get("single_page_only", True))
        self.match_total = bool(self.d.get("check_total_match", True))
        self.auto_focus = bool(self.d.get("auto_focus", True))
        self.stable = float(self.d.get("accept_stable_sec", 4.0))
        self.t_items = float(self.d.get("wait_items_sec", 180))
        self.t_window = float(self.d.get("wait_window_sec", 15))
        self.t_close = float(self.d.get("wait_close_sec", 30))
        self.poll = float(self.d.get("poll_idle_sec", 5.0))
        self.force = float(self.d.get("force_scan_sec", 30.0))
        self.thr = self.d.get("thresholds", {}) or {}
        self.tpl = self.d.get("templates_dir", "templates")
        self.reg = self.d.get("regions", {}) or {}
        self.pts = self.d.get("points", {}) or {}
        self.tess = self.d.get("tesseract_cmd", "") or ""
        self.lang = self.d.get("ocr_lang", "eng")

    def T(self, name):
        return os.path.join(BASE, self.tpl, f"{name}.png")

    def thr_of(self, name, default=0.85):
        try:
            return float(self.thr.get(name, default))
        except Exception:
            return default


def shift(region, dy):
    x1, y1, x2, y2 = region
    return [x1, y1 + dy, x2, y2 + dy]


def roi_center(screen, roi):
    return screen.to_px((roi[0] + roi[2]) / 2, (roi[1] + roi[3]) / 2)


def main():
    cfg_path = os.path.join(BASE, "config.yaml")
    if not os.path.exists(cfg_path):
        print("Нет config.yaml! Скопируй config.example.yaml, откалибруй: python calibrate.py")
        sys.exit(1)
    cfg = Cfg(cfg_path)
    for k in ("row_nick", "row_accept", "row_decline", "their_total", "our_total", "their_grid"):
        if k not in cfg.reg:
            print(f"В config.yaml нет regions.{k} — запусти python calibrate.py")
            sys.exit(1)
    if "row_step_y" not in cfg.pts:
        print("В config.yaml нет points.row_step_y — запусти python calibrate.py")
        sys.exit(1)
    for name in ("person", "accept", "decline", "accept_trade", "decline_trade"):
        if not os.path.exists(cfg.T(name)):
            log(f"ВНИМАНИЕ: нет шаблона templates/{name}.png — запусти python calibrate.py")

    log("Старт. only_nicks =", sorted(cfg.only) or "ПУСТО (беру первую строку!)",
        "| whitelist =", sorted(cfg.white))
    log("Мышь:", mouse.mode(), "| админ:", mouse.is_admin())
    if not mouse.using_interception():
        log("ВНИМАНИЕ: работаем через SendInput. Если клики не доходят до игры — "
            "поставь драйвер Interception (README) и pip install interception-python pywin32")

    screen = Screen()
    scr = cfg.d.get("screen", {}) or {}
    if (screen.w, screen.h) != (scr.get("w"), scr.get("h")):
        log(f"ВНИМАНИЕ: разрешение {screen.w}x{screen.h} != калибровка {scr} — шаблоны могут не находиться!")

    last_force = 0.0
    while True:
        try:
            if not ensure_roblox(cfg):
                time.sleep(cfg.poll)
                continue
            if trade_open(screen, cfg):
                decline(screen, cfg, "Висит открытое окно трейда, сбрасываю")
                continue
            badge = screen.find(cfg.T("badge"), thr=cfg.thr_of("badge", 0.8))
            if badge or (time.time() - last_force > cfg.force):
                last_force = time.time()
                if open_list(screen, cfg):
                    try:
                        handle_list(screen, cfg)
                    finally:
                        close_list(screen, cfg)
            time.sleep(cfg.poll)
        except KeyboardInterrupt:
            log("Стоп.")
            break
        except Exception:
            log("ОШИБКА цикла:\n" + traceback.format_exc())
            time.sleep(2)


_focus_warned = False


def ensure_roblox(cfg):
    """True если окно Roblox активно (при auto_focus само выводит его на передний план)."""
    global _focus_warned
    if mouse.foreground_is_roblox():
        _focus_warned = False
        return True
    if mouse.roblox_window() is None:
        msg = "Окно Roblox не найдено — запусти игру. Жду..."
    elif cfg.auto_focus and mouse.activate_roblox():
        log("Окно Roblox выведено на передний план.")
        _focus_warned = False
        return True
    else:
        msg = "Окно Roblox не на переднем плане — кликни по окну игры. Жду..."
    if not _focus_warned:
        log(msg)
        _focus_warned = True
    return False


# ---------- список трейдов ----------
def open_list(screen, cfg):
    p = screen.find(cfg.T("person"), thr=cfg.thr_of("person"))
    if not p:
        log("Иконка человечка не найдена (порог thresholds.person? список уже открыт?).")
        return False
    click(p[0], p[1])
    opened = wait_until(
        lambda: any(screen.find(cfg.T(n), thr=cfg.thr_of(n)) for n in ("close", "accept", "decline")),
        3.0, 0.3)
    if not opened:
        log("Список трейдов не открылся после клика по иконке.")
    return bool(opened)


def close_list(screen, cfg):
    p = screen.find(cfg.T("close"), thr=cfg.thr_of("close"))
    if p:
        click(p[0], p[1])
        time.sleep(0.8)
    elif os.path.exists(cfg.T("close")):
        log("Кнопка close списка не найдена.")


def row_rois(cfg, i=0):
    dy = i * float(cfg.pts["row_step_y"])
    return (
        shift(cfg.reg["row_nick"], dy),
        shift(cfg.reg["row_accept"], dy),
        shift(cfg.reg["row_decline"], dy),
    )


def row_button(screen, cfg, name, roi):
    """Координаты кнопки строки: ищем шаблон около области, если шаблона нет — центр области."""
    if not os.path.exists(cfg.T(name)):
        return roi_center(screen, roi)
    p = screen.find(cfg.T(name), region=expand(roi, 0.6), thr=cfg.thr_of(name))
    return (p[0], p[1]) if p else None


def handle_list(screen, cfg):
    """Всегда работаем с ПЕРВОЙ строкой: наш -> accept, чужой -> decline (список сдвигается)."""
    for _ in range(12):
        nick_roi, acc_roi, dec_roi = row_rois(cfg, 0)
        acc = row_button(screen, cfg, "accept", acc_roi)
        if acc is None:
            log("Строк в списке нет (кнопка accept 1-й строки не найдена).")
            return
        nick = ocr_nick(screen.grab(nick_roi), cfg.tess, cfg.lang)
        nn = norm_nick(nick)
        if len(nn) < 3:
            if cfg.only:
                log(f"Ник не прочитан ('{nick}'), пропускаю строку (строгий режим).")
                return
            log("Ник не прочитан, беру первую строку вслепую.")
            return accept_row(screen, cfg, acc, None)
        match = nick_matches(nn, cfg.only) if cfg.only else nn
        if not match:
            log(f"Чужой ({nick}) — DECLINE.")
            dec = row_button(screen, cfg, "decline", dec_roi) or roi_center(screen, dec_roi)
            click(dec[0], dec[1])
            time.sleep(1.2)
            continue
        log(f"Наш ({nick} -> {match}) — ACCEPT.")
        return accept_row(screen, cfg, acc, match)
    log("Строки не кончаются, выхожу из списка.")


def accept_row(screen, cfg, acc, nick):
    click(acc[0], acc[1])
    time.sleep(1.0)
    handle_trade(screen, cfg, nick)


# ---------- окно трейда ----------
def trade_open(screen, cfg):
    return (screen.find(cfg.T("accept_trade"), thr=cfg.thr_of("accept")) is not None
            or screen.find(cfg.T("decline_trade"), thr=cfg.thr_of("decline")) is not None)


def decline(screen, cfg, reason):
    log(reason, "— DECLINE.")
    p = screen.find(cfg.T("decline_trade"), thr=cfg.thr_of("decline"))
    if not p:
        log("Кнопка decline в окне трейда не найдена!")
        return False
    click(p[0], p[1])
    if wait_until(lambda: not trade_open(screen, cfg), 5.0, 0.5) is None:
        log("Окно трейда не закрылось после decline.")
    return True


def read_total(screen, cfg, key):
    return ocr_number(screen.grab(cfg.reg[key]), cfg.tess)


def grid_cells(screen, cfg):
    """9 ячеек их сетки 3x3."""
    x1, y1, x2, y2 = cfg.reg["their_grid"]
    cells = []
    for r in range(3):
        for c in range(3):
            cells.append(screen.grab([
                x1 + (x2 - x1) * c / 3, y1 + (y2 - y1) * r / 3,
                x1 + (x2 - x1) * (c + 1) / 3, y1 + (y2 - y1) * (r + 1) / 3,
            ]))
    return cells


def cell_top(cell):
    return cell[0:int(cell.shape[0] * 0.35), :]


def evaluate(screen, cfg):
    """Одна проверка окна. -> ('ok'|'wait'|'decline', total, сообщение)."""
    their = read_total(screen, cfg, "their_total")
    if not their:
        return "wait", 0, "Их сторона пуста, жду предметы..."
    our = read_total(screen, cfg, "our_total")
    if our is None:
        return "wait", their, "Не читается наша сумма, жду..."
    if our != 0:
        return "decline", their, f"!!! НАША СТОРОНА НЕ ПУСТА ({our}) — проверь акк!"

    cells = grid_cells(screen, cfg)
    filled = [c for c in cells if not slot_empty(c, cfg.T("plus"), cfg.thr_of("plus", 0.8))]
    if len(filled) > cfg.max_items:
        return "decline", their, f"Слотов занято {len(filled)} > {cfg.max_items}"
    raps = [ocr_number(cell_top(c), cfg.tess) for c in filled]
    if any(v is None for v in raps):
        return "wait", their, f"RAP не везде прочитан {raps}, жду..."
    bad = [v for v in raps if v not in cfg.white]
    if bad:
        return "decline", their, f"Левые предметы {bad}, принимаем только {sorted(cfg.white)}"

    if cfg.strict_page and "pager" in cfg.reg:
        txt = (ocr_text(screen.grab(cfg.reg["pager"]), "0123456789/", 7, cfg.tess, cfg.lang) or "").replace(" ", "")
        if txt and txt not in ("1/1", "11"):
            return "decline", their, f"Похоже есть 2-я страница ({txt})"

    total = sum(raps)
    if cfg.match_total and total != their:
        return "wait", their, f"Сумма слотов {total} != Total RAP {their}, жду..."
    if total < cfg.min_total:
        return "wait", their, f"Мало: {total} < {cfg.min_total}, жду..."
    return "ok", total, f"Всё чисто: слотов {len(filled)}, RAP {raps}, сумма {total}. Жду стабильности {cfg.stable}с..."


def handle_trade(screen, cfg, expected_nick):
    if not wait_until(lambda: trade_open(screen, cfg), cfg.t_window, 0.5):
        log("Окно трейда не открылось.")
        return
    if expected_nick and "partner_name" in cfg.reg:
        partner = ocr_nick(screen.grab(cfg.reg["partner_name"]), cfg.tess, cfg.lang)
        if partner and not nick_matches(partner, {expected_nick}):
            decline(screen, cfg, f"Чужое окно ({partner} != {expected_nick})")
            return
        log(f"Партнёр: {partner or '?'}.")

    deadline = time.time() + cfg.t_items
    stable_since, last_total, last_msg, total = None, None, None, 0
    while time.time() < deadline:
        if not trade_open(screen, cfg):
            log("Окно трейда закрылось само (партнёр отменил?).")
            return
        status, total, msg = evaluate(screen, cfg)
        if status == "decline":
            decline(screen, cfg, msg)
            return
        green = screen.find(cfg.T("accept_trade"), thr=cfg.thr_of("accept"))
        if status == "ok" and not green:
            msg = "Кнопка accept не зелёная/не найдена, жду..."
        if msg != last_msg:
            log(msg)
            last_msg = msg
        if status != "ok" or not green or total != last_total:
            stable_since = None
            last_total = total if status == "ok" else None
            time.sleep(0.7)
            continue
        if stable_since is None:
            stable_since = time.time()
        if time.time() - stable_since >= cfg.stable:
            log(f"Жму ACCEPT (total={total}).")
            click(green[0], green[1])
            break
        time.sleep(0.5)
    else:
        decline(screen, cfg, f"Таймаут {cfg.t_items:.0f}с, сделка не сложилась")
        return

    if wait_until(lambda: not trade_open(screen, cfg), cfg.t_close, 0.8):
        log(f"ПРИНЯТО! total={total} (TEST: без зачисления, на сайте ничего не тронуто).")
    else:
        log("Окно не закрылось после accept — возможно нужен второй клик/подтверждение. Смотри сам.")


if __name__ == "__main__":
    main()
