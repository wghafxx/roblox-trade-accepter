"""Мышь: сперва Interception (события выглядят как настоящая мышь, флага
'инъекции' нет — игры его не отличают), если драйвера нет — SendInput.

Установка Interception (один раз):
  1) скачать https://github.com/oblitum/Interception (releases, zip)
  2) распаковать, в папке command line installer запустить от АДМИНА:
       install.bat
  3) перезагрузить ПК
  4) pip install interception-python
"""
import ctypes
import time

user32 = ctypes.windll.user32
try:
    user32.SetProcessDPIAware()
except Exception:
    pass

_interception = None
_interception_error = ""


def _get_interception():
    """Ленивая загрузка interception. None если драйвера/библиотеки нет."""
    global _interception, _interception_error
    if _interception is not None:
        return _interception
    if _interception_error:
        return None
    try:
        import interception

        interception.auto_capture_devices(mouse=True)
        _interception = interception
        return _interception
    except Exception as e:
        _interception_error = str(e)
        return None


# ---------- резервный путь: SendInput ----------
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("mi", MOUSEINPUT)]


def _send(flags, x=0, y=0):
    extra = ctypes.c_ulong(0)
    inp = INPUT(INPUT_MOUSE, MOUSEINPUT(x, y, 0, flags, 0, ctypes.pointer(extra)))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def _to_abs(x, y):
    sx = user32.GetSystemMetrics(0)
    sy = user32.GetSystemMetrics(1)
    return int(x * 65535 / max(sx - 1, 1)), int(y * 65535 / max(sy - 1, 1))


def _move_si(x, y):
    ax, ay = _to_abs(int(x), int(y))
    _send(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, ax, ay)
    time.sleep(0.05)


def _click_si(x, y, pre_delay, post_delay):
    time.sleep(pre_delay)
    _move_si(x, y)
    _send(MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.08)
    _send(MOUSEEVENTF_LEFTUP)
    time.sleep(post_delay)


# ---------- публичный API ----------
def _interception_ok():
    ic = _get_interception()
    if ic is None:
        return False
    try:
        # быстрый тест: драйвер реально отвечает?
        return ic.Interception is not None
    except Exception:
        return False


def move(x, y, steps=12):
    """Плавно двигает курсор в точку (человекоподобно, без телепорта)."""
    ic = _get_interception()
    p = _cursor_pos()
    if ic is not None:
        dx_total, dy_total = int(x) - p[0], int(y) - p[1]
        for i in range(1, steps + 1):
            sx = p[0] + dx_total * i / steps
            sy = p[1] + dy_total * i / steps
            ic.move_to(int(sx), int(sy))
            time.sleep(0.012)
    else:
        for i in range(1, steps + 1):
            sx = p[0] + (int(x) - p[0]) * i / steps
            sy = p[1] + (int(y) - p[1]) * i / steps
            _move_si(sx, sy)


def click(x, y, pre_delay=0.1, post_delay=0.15):
    """Клик. Сначала Interception, без драйвера — SendInput."""
    ic = _get_interception()
    if ic is not None:
        time.sleep(pre_delay)
        move(x, y)
        ic.click(1)  # 1 = левая кнопка
        time.sleep(post_delay)
    else:
        _click_si(x, y, pre_delay, post_delay)


def _cursor_pos():
    class P(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    p = P()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def mode():
    ic = _get_interception()
    return "interception" if ic is not None else f"sendinput (драйвера нет: {_interception_error or 'не установлен'})"


def foreground_is_roblox():
    try:
        hwnd = user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        return "roblox" in (buf.value or "").lower()
    except Exception:
        return False
