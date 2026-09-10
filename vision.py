"""Зрение: скриншоты (mss), поиск шаблонов (OpenCV), OCR (Tesseract)."""
import os
import time

import cv2
import numpy as np
from mss import mss

_ocr = None
_ocr_error_shown = False


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
        """Ищет шаблон. Возвращает (cx, cy, score) в пикселях или None."""
        if not os.path.exists(template_path):
            return None
        img = self.grab(region)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        tpl = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        if tpl is None:
            return None
        ox, oy = 0, 0
        if region is not None:
            ox, oy = int(region[0] * self.w), int(region[1] * self.h)
        best = None
        th, tw = tpl.shape[:2]
        for s in scales:
            nw, nh = max(4, int(tw * s)), max(4, int(th * s))
            if nh > gray.shape[0] or nw > gray.shape[1]:
                continue
            t = cv2.resize(tpl, (nw, nh))
            res = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
            _, mx, _, ml = cv2.minMaxLoc(res)
            if best is None or mx > best[0]:
                best = (mx, ml, nw, nh)
        if best is None or best[0] < thr:
            return None
        score, (lx, ly), nw, nh = best
        return ox + lx + nw // 2, oy + ly + nh // 2, float(score)


def _prep_ocr(img, upscale=2):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    _, g = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return g


def ocr_text(img, whitelist=None, psm=7, tesseract_cmd="", lang="eng"):
    """Текст с картинки. whitelist — разрешённые символы. None если OCR нет."""
    ocr = _get_ocr(tesseract_cmd)
    if ocr is None:
        return None
    cfg = f"--psm {psm} -l {lang}"
    if whitelist:
        cfg += f" -c tessedit_char_whitelist={whitelist}"
    try:
        return ocr.image_to_string(_prep_ocr(img), config=cfg).strip()
    except Exception as e:
        print("[vision] ocr ошибка:", e)
        return None


NICK_WHITELIST = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"


def ocr_nick(img, tesseract_cmd="", lang="eng"):
    t = ocr_text(img, NICK_WHITELIST, 7, tesseract_cmd, lang)
    if not t:
        return ""
    return "".join(ch for ch in t.split()[:1] if ch in NICK_WHITELIST)


def ocr_number(img, tesseract_cmd=""):
    t = ocr_text(img, "0123456789", 7, tesseract_cmd)
    if not t:
        return None
    digits = "".join(ch for ch in t if ch.isdigit())
    return int(digits) if digits else None


def norm_nick(nick):
    return (nick or "").lstrip("@").strip().lower()


def slot_empty(slot_img, plus_template_path, thr=0.8):
    """Пустой слот = большой '+' по центру. True если слот пуст."""
    if not os.path.exists(plus_template_path):
        # запасной вариант: почти однотонный тёмный слот = пуст
        g = cv2.cvtColor(slot_img, cv2.COLOR_BGR2GRAY)
        return float(g.std()) < 12.0
    tpl = cv2.imread(plus_template_path, cv2.IMREAD_GRAYSCALE)
    g = cv2.cvtColor(slot_img, cv2.COLOR_BGR2GRAY)
    if tpl is None or tpl.shape[0] > g.shape[0] or tpl.shape[1] > g.shape[1]:
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
