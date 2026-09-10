"""Зрение: скриншоты (mss), поиск шаблонов (OpenCV, в цвете), OCR (Tesseract)."""
import difflib
import os
import time

import cv2
import numpy as np
from mss import mss

_ocr = None
_ocr_error_shown = False
_tpl_cache = {}


def _get_ocr(tesseract_cmd=""):
    global _ocr, _ocr_error_shown
    if _ocr is not None:
        return _ocr
    try:
        import pytesseract

        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        _ocr = pytesseract
        return _ocr
    except Exception as e:
        if not _ocr_error_shown:
            print("[vision] НЕТ pytesseract/tesseract:", e)
            print("[vision] Поставь Tesseract (https://github.com/UB-Mannheim/tesseract/wiki) и pip install pytesseract")
            _ocr_error_shown = True
        return None


def _load_tpl(path):
    t = _tpl_cache.get(path)
    if t is None and os.path.exists(path):
        t = cv2.imread(path, cv2.IMREAD_COLOR)
        if t is not None:
            _tpl_cache[path] = t
    return t


class Screen:
    def __init__(self):
        self.sct = mss()
        mon = self.sct.monitors[1]
        self.w, self.h = mon["width"], mon["height"]

    def grab(self, region=None):
        """region — доли (x1,y1,x2,y2) от экрана. Возвращает BGR numpy."""
        if region is None:
            shot = self.sct.grab(self.sct.monitors[1])
            return cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)
        x1, y1, x2, y2 = region
        mon = {
            "left": int(x1 * self.w),
            "top": int(y1 * self.h),
            "width": max(1, int((x2 - x1) * self.w)),
            "height": max(1, int((y2 - y1) * self.h)),
        }
        shot = self.sct.grab(mon)
        return cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)

    def to_px(self, fx, fy):
        return int(fx * self.w), int(fy * self.h)

    def find(self, template_path, region=None, thr=0.85, scales=(0.92, 1.0, 1.08)):
        """Ищет шаблон В ЦВЕТЕ (зелёный accept != красный decline). (cx, cy, score) в пикселях или None."""
        tpl = _load_tpl(template_path)
        if tpl is None:
            return None
        img = self.grab(region)
        ox, oy = (0, 0) if region is None else (int(region[0] * self.w), int(region[1] * self.h))
        best = None
        th, tw = tpl.shape[:2]
        for s in scales:
            nw, nh = max(4, int(tw * s)), max(4, int(th * s))
            if nh > img.shape[0] or nw > img.shape[1]:
                continue
            t = tpl if s == 1.0 else cv2.resize(tpl, (nw, nh))
            res = cv2.matchTemplate(img, t, cv2.TM_CCOEFF_NORMED)
            _, mx, _, ml = cv2.minMaxLoc(res)
            if best is None or mx > best[0]:
                best = (mx, ml, nw, nh)
        if best is None or best[0] < thr:
            return None
        score, (lx, ly), nw, nh = best
        return ox + lx + nw // 2, oy + ly + nh // 2, float(score)


def expand(region, k=0.5):
    """Расширяет область (в долях экрана) на k от её размера в каждую сторону."""
    x1, y1, x2, y2 = region
    dw, dh = (x2 - x1) * k, (y2 - y1) * k
    return [max(0.0, x1 - dw), max(0.0, y1 - dh), min(1.0, x2 + dw), min(1.0, y2 + dh)]


def _prep_ocr(img, upscale=3):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    _, g = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if g.mean() < 127:
        g = 255 - g  # tesseract лучше читает тёмный текст на белом
    return cv2.copyMakeBorder(g, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)


def ocr_text(img, whitelist=None, psm=7, tesseract_cmd="", lang="eng"):
    """Текст с картинки. whitelist — разрешённые символы. None если OCR нет."""
    ocr = _get_ocr(tesseract_cmd)
    if ocr is None:
        return None
    cfg = f"--psm {psm}"
    if whitelist:
        cfg += f" -c tessedit_char_whitelist={whitelist}"
    try:
        return ocr.image_to_string(_prep_ocr(img), lang=lang, config=cfg).strip()
    except Exception as e:
        print("[vision] ocr ошибка:", e)
        return None


NICK_WHITELIST = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"


def ocr_nick(img, tesseract_cmd="", lang="eng"):
    t = ocr_text(img, NICK_WHITELIST, 7, tesseract_cmd, lang)
    if not t:
        return ""
    return "".join(ch for ch in t.split()[0] if ch in NICK_WHITELIST)


def ocr_number(img, tesseract_cmd=""):
    t = ocr_text(img, "0123456789", 7, tesseract_cmd)
    if not t:
        return None
    digits = "".join(ch for ch in t if ch.isdigit())
    return int(digits) if digits else None


def norm_nick(nick):
    return (nick or "").lstrip("@").strip().lower()


_CONFUSABLE = str.maketrans({"0": "o", "1": "l", "i": "l", "|": "l", "5": "s", "8": "b"})


def nick_matches(nick, allowed, min_ratio=0.8):
    """Ник из allowed, на который похож распознанный nick (с поправкой на ошибки OCR o/0, l/1/i), иначе None."""
    n = norm_nick(nick)
    if not n:
        return None
    if n in allowed:
        return n
    nt = n.translate(_CONFUSABLE)
    best, best_r = None, 0.0
    for a in allowed:
        r = difflib.SequenceMatcher(None, nt, a.translate(_CONFUSABLE)).ratio()
        if r > best_r:
            best, best_r = a, r
    return best if best_r >= min_ratio else None


def slot_empty(slot_img, plus_template_path, thr=0.8):
    """Пустой слот = большой '+' по центру. True если слот пуст."""
    g = cv2.cvtColor(slot_img, cv2.COLOR_BGR2GRAY)
    tpl = _load_tpl(plus_template_path)
    if tpl is None:
        return float(g.std()) < 12.0  # запасной вариант: почти однотонный слот = пуст
    tpl = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
    if tpl.shape[0] > g.shape[0] or tpl.shape[1] > g.shape[1]:
        return float(g.std()) < 12.0
    res = cv2.matchTemplate(g, tpl, cv2.TM_CCOEFF_NORMED)
    return float(res.max()) >= thr


def wait_until(fn, timeout, poll=0.4):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = fn()
        if v:
            return v
        time.sleep(poll)
    return None
