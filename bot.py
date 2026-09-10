"""Тест-бот автопринятия кейсов (Trade Plaza).

ТЕСТ-РЕЖИМ: сайт не трогаем, ничего не зачисляем. Только клики в игре + логи.
Успешная сделка = строка 'ПРИНЯТО ... (TEST: без зачисления)'.

Запуск на ПК с игрой: python bot.py
Остановка: Ctrl+C. Мышь во время кликов не трогать.
"""
import os
import sys
import time
from datetime import datetime

import yaml

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from mouse import click, foreground_is_roblox  # noqa: E402
from vision import Screen, norm_nick, ocr_nick, ocr_number, slot_empty  # noqa: E402


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
    log("Старт. only_nicks =", sorted(cfg.only) or "ПУСТО (беру первую строку!)",
        "| whitelist =", sorted(cfg.white))
    screen = Screen()
    if (screen.w, screen.h) != (cfg.d.get("screen", {}).get("w"), cfg.d.get("screen", {}).get("h")):
        log(f"ВНИМАНИЕ: разрешение {screen.w}x{screen.h} != калибровка",
            cfg.d.get("screen"), "— шаблоны могут не находиться!")

    last_force = 0.0
    while True:
        try:
            if not foreground_is_roblox():
                time.sleep(cfg.poll)
                continue
            badge = screen.find(cfg.T("badge"), thr=cfg.thr_of("badge", 0.8))
            if badge or (time.time() - last_force > cfg.force):
                if open_list(screen, cfg):
                    handle_list(screen, cfg)
                    close_list(screen, cfg)
                    last_force = time.time()
            time.sleep(cfg.poll)
        except KeyboardInterrupt:
            log("Стоп.")
            break
        except Exception as e:
            log("ОШИБКА цикла:", repr(e))
            time.sleep(2)


def open_list(screen, cfg):
    p = screen.find(cfg.T("person"), thr=cfg.thr_of("person"))
    if not p:
        return False
    click(p[0], p[1])
    time.sleep(1.5)
    return screen.find(cfg.T("accept"), thr=cfg.thr_of("accept")) is not None


def close_list(screen, cfg):
    p = screen.find(cfg.T("close"), thr=cfg.thr_of("close"))
    if p:
        click(p[0], p[1])
        time.sleep(0.8)


def row_rois(cfg, i=0):
    dy = i * float(cfg.pts["row_step_y"])
    return (
        shift(cfg.reg["row_nick"], dy),
        shift(cfg.reg["row_accept"], dy),
        shift(cfg.reg["row_decline"], dy),
    )


def handle_list(screen, cfg):
    """Всегда работаем с ПЕРВОЙ строкой: мэтч -> accept, чужой -> decline (список сдвигается)."""
    for _ in range(12):
        nick_roi, acc_roi, dec_roi = row_rois(cfg, 0)
        nick_img = screen.grab(nick_roi)
        nick = ocr_nick(nick_img, cfg.tess, cfg.lang)
        nn = norm_nick(nick)
        if not nn or len(nn) < 3:
            if cfg.only:
                log("Ник не прочитан, пропускаю строку (строгий режим).")
                return
            log("Ник не прочитан, беру первую строку вслепую.")
            return accept_row(screen, cfg, acc_roi, None)
        if cfg.only and nn not in cfg.only:
            log(f"Чужой ({nick}) — DECLINE.")
            _, _, dec_roi = row_rois(cfg, 0)
            dx, dy = screen.to_px((dec_roi[0] + dec_roi[2]) / 2, (dec_roi[1] + dec_roi[3]) / 2)
            click(dx, dy)
            time.sleep(1.2)
            continue
        log(f"Наш ({nick}) — ACCEPT.")
        return accept_row(screen, cfg, acc_roi, nick)
    log("Строки не кончаются, выхожу из списка.")


def accept_row(screen, cfg, acc_roi, nick):
    ax, ay = screen.to_px((acc_roi[0] + acc_roi[2]) / 2, (acc_roi[1] + acc_roi[3]) / 2)
    click(ax, ay)
    time.sleep(1.0)
    handle_trade(screen, cfg, nick)


def trade_open(screen, cfg):
    return (screen.find(cfg.T("accept_trade"), thr=cfg.thr_of("accept")) is not None
            or screen.find(cfg.T("decline_trade"), thr=cfg.thr_of("decline")) is not None)


def click_decline_trade(screen, cfg):
    p = screen.find(cfg.T("decline_trade"), thr=cfg.thr_of("decline"))
    if p:
        click(p[0], p[1])
        time.sleep(1.0)


def read_total(screen, cfg, key):
    img = screen.grab(cfg.reg[key])
    return ocr_number(img, cfg.tess)


def grid_cells(screen, cfg):
    """9 ячеек их сетки 3x3. Возвращает список картинок."""
    x1, y1, x2, y2 = cfg.reg["their_grid"]
    cells = []
    for r in range(3):
        for c in range(3):
            cx1 = x1 + (x2 - x1) * c / 3
            cx2 = x1 + (x2 - x1) * (c + 1) / 3
            cy1 = y1 + (y2 - y1) * r / 3
            cy2 = y1 + (y2 - y1) * (r + 1) / 3
            cells.append(screen.grab([cx1, cy1, cx2, cy2]))
    return cells


def cell_top(cell):
    h = cell.shape[0]
    return cell[0:int(h * 0.35), :]


def handle_trade(screen, cfg, expected_nick):
    t0 = time.time()
    while time.time() - t0 < cfg.t_window:
        if trade_open(screen, cfg):
            break
        time.sleep(0.5)
    else:
        log("Окно трейда не открылось.")
        return

    if expected_nick and "partner_name" in cfg.reg:
        partner = ocr_nick(screen.grab(cfg.reg["partner_name"]), cfg.tess, cfg.lang)
        if partner and norm_nick(partner) != norm_nick(expected_nick):
            log(f"Чужое окно ({partner} != {expected_nick}) — DECLINE.")
            click_decline_trade(screen, cfg)
            return
        log(f"Партнёр: {partner or '?'}.")

    # ждём пока положит кейсы
    their = None
    t0 = time.time()
    while time.time() - t0 < cfg.t_items:
        their = read_total(screen, cfg, "their_total")
        if their and their > 0:
            break
        time.sleep(1.0)
    if not their:
        log("Ничего не положили (таймаут) — DECLINE.")
        click_decline_trade(screen, cfg)
        return

    # проверки
    our = read_total(screen, cfg, "our_total")
    if our is None:
        log("Не прочитал нашу сумму — DECLINE (безопасность).")
        click_decline_trade(screen, cfg)
        return
    if our != 0:
        log(f"!!! НАША СТОРОНА НЕ ПУСТА ({our}) — DECLINE, проверь акк!")
        click_decline_trade(screen, cfg)
        return

    cells = grid_cells(screen, cfg)
    filled = [c for c in cells if not slot_empty(c, cfg.T("plus"), cfg.thr_of("plus", 0.8))]
    log(f"Слотов занято: {len(filled)}.")
    if len(filled) > cfg.max_items:
        log(f"Больше {cfg.max_items} штук — DECLINE.")
        click_decline_trade(screen, cfg)
        return

    raps = []
    for c in filled:
        v = ocr_number(cell_top(c), cfg.tess)
        raps.append(v)
    log("RAP по слотам:", raps)
    if any(v is None for v in raps):
        log("Какой-то RAP не прочитан — DECLINE (безопасность).")
        click_decline_trade(screen, cfg)
        return
    bad = [v for v in raps if v not in cfg.white]
    if bad:
        log(f"Левые предметы {bad}, принимаем только {sorted(cfg.white)} — DECLINE.")
        click_decline_trade(screen, cfg)
        return

    if cfg.strict_page and "pager" in cfg.reg:
        from vision import ocr_text

        pg = screen.grab(cfg.reg["pager"])
        txt = (ocr_text(pg, whitelist="0123456789/", psm=7,
                        tesseract_cmd=cfg.tess, lang=cfg.lang) or "").replace(" ", "")
        if txt and txt not in ("1/1", "11"):
            log(f"Похоже есть 2-я страница ({txt}) — DECLINE.")
            click_decline_trade(screen, cfg)
            return

    total = sum(raps)
    if total < cfg.min_total:
        log(f"Мало: {total} < {cfg.min_total} — DECLINE.")
        click_decline_trade(screen, cfg)
        return

    # стабильность 4 сек + зелёный accept -> жмём
    log(f"Всё чисто, сумма {total}. Жду стабильности {cfg.stable}с...")
    stable_since = None
    t0 = time.time()
    while time.time() - t0 < cfg.t_items:
        cur = read_total(screen, cfg, "their_total")
        green = screen.find(cfg.T("accept_trade"), thr=cfg.thr_of("accept"))
        now = time.time()
        if cur == total and green:
            if stable_since is None:
                stable_since = now
            if now - stable_since >= cfg.stable:
                log("Жму ACCEPT.")
                click(green[0], green[1])
                break
        else:
            stable_since = None
            if cur != total:
                log(f"Сумма изменилась ({total} -> {cur}), жду заново...")
                return  # упрощение теста: сумму поменяли — выходим, следующий круг разберёт
        time.sleep(0.5)
    else:
        log("Не дождался стабильного accept — выхожу.")
        return

    # ждём закрытия окна = успех
    t0 = time.time()
    while time.time() - t0 < cfg.t_close:
        if not trade_open(screen, cfg):
            log(f"ПРИНЯТО! total={total} (TEST: без зачисления, на сайте ничего не тронуто).")
            return
        time.sleep(0.8)
    log("Окно не закрылось — возможно нужен клик по галочке. Смотри сам, дальше руками.")


if __name__ == "__main__":
    main()
