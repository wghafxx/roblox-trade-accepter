"""Мышь для бота.

Порядок: Interception (драйвер, события неотличимы от настоящей мыши) -> SendInput.

Установка Interception (один раз, от администратора):
  1) https://github.com/oblitum/Interception/releases -> распаковать
  2) "command line installer\\install-interception.exe" /install
  3) перезагрузить ПК
  4) pip install interception-python pywin32
"""
import ctypes
import ctypes.wintypes as wt
import random
import time

user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

HOVER_DELAY = 0.12   # пауза после наведения: UI игры должен увидеть курсор над кнопкой
HOLD_DELAY = 0.07    # сколько держим кнопку нажатой (слишком быстрый клик игра может пропустить)

_ic = None
_ic_note = ""
_ic_checked = False


def cursor_pos():
    p = wt.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def screen_size():
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# ---------- Interception ----------
def _probe_mouse_device(ic):
    """Перебирает устройства 10..19 и оставляет то, которое реально двигает курсор."""
    sx, sy = cursor_pos()
    w, h = screen_size()
    tx = sx + 60 if sx + 60 < w - 5 else sx - 60
    ty = sy + 60 if sy + 60 < h - 5 else sy - 60
    order = [ic.get_mouse()] + [n for n in range(10, 20) if n != ic.get_mouse()]
    for n in order:
        try:
            ic.set_devices(mouse=n)
            ic.move_to(tx, ty)
        except Exception:
            continue
        time.sleep(0.05)
        cx, cy = cursor_pos()
        if abs(cx - tx) <= 3 and abs(cy - ty) <= 3:
            ic.move_to(sx, sy)
            return n
    return None


def _init_interception():
    global _ic, _ic_note, _ic_checked
    if _ic_checked:
        return _ic
    _ic_checked = True
    try:
        import interception
    except Exception as e:
        _ic_note = f"библиотека не импортируется ({e!r}). Выполни: pip install interception-python pywin32"
        return None
    try:
        interception.auto_capture_devices(keyboard=False, mouse=True)
    except Exception as e:
        _ic_note = (f"драйвер не найден ({e!r}). Установи Interception "
                    "(install-interception.exe /install от админа) и перезагрузи ПК")
        return None
    dev = _probe_mouse_device(interception)
    if dev is None:
        _ic_note = "драйвер есть, но ни одно устройство мыши (10..19) не двигает курсор"
        return None
    _ic = interception
    _ic_note = f"устройство мыши #{dev}"
    return _ic


# ---------- SendInput (резерв) ----------
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wt.LONG),
        ("dy", wt.LONG),
        ("mouseData", wt.DWORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("mi", MOUSEINPUT)]


def _send(flags, dx=0, dy=0):
    inp = INPUT(INPUT_MOUSE, MOUSEINPUT(dx, dy, 0, flags, 0, 0))
    return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def _move_si(x, y):
    w, h = screen_size()
    ax = int(round(x * 65535 / max(w - 1, 1)))
    ay = int(round(y * 65535 / max(h - 1, 1)))
    _send(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, ax, ay)


# ---------- публичный API ----------
def move(x, y, duration=0.45):
    """Плавно ведёт курсор в точку за duration секунд и проверяет попадание."""
    x, y = int(x), int(y)
    ic = _init_interception()
    px, py = cursor_pos()
    dist = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
    if dist < 2:
        return
    total = max(0.25, min(1.2, duration * (0.5 + dist / 800.0)))
    steps = max(8, int(total / 0.016))
    for i in range(1, steps + 1):
        t = i / steps
        t = t * t * (3 - 2 * t)  # smoothstep: старт/финиш мягко, середина быстро
        sx = round(px + (x - px) * t + random.uniform(-0.6, 0.6))
        sy = round(py + (y - py) * t + random.uniform(-0.6, 0.6))
        if ic is not None:
            ic.move_to(sx, sy)
        else:
            _move_si(sx, sy)
        time.sleep(total / steps)
    cx, cy = cursor_pos()
    if abs(cx - x) > 2 or abs(cy - y) > 2:
        if ic is not None:
            ic.move_to(x, y)
        else:
            user32.SetCursorPos(x, y)
            _move_si(x, y)
        time.sleep(0.03)


def click(x, y, pre_delay=0.1, post_delay=0.15):
    """Навести -> подождать hover -> нажать -> подержать -> отпустить."""
    ic = _init_interception()
    time.sleep(pre_delay + random.uniform(0, 0.08))
    move(x + random.randint(-1, 1), y + random.randint(-1, 1))
    time.sleep(HOVER_DELAY)
    if ic is not None:
        ic.mouse_down("left", HOLD_DELAY + random.uniform(0, 0.04))
        ic.mouse_up("left", 0.03)
    else:
        _send(MOUSEEVENTF_LEFTDOWN)
        time.sleep(HOLD_DELAY)
        _send(MOUSEEVENTF_LEFTUP)
    time.sleep(post_delay)


def mode():
    ic = _init_interception()
    return f"interception ({_ic_note})" if ic is not None else f"sendinput — {_ic_note}"


def using_interception():
    return _init_interception() is not None


# ---------- окно Roblox ----------
def _title(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value or ""


def _is_roblox_title(t):
    return t.strip().lower() == "roblox"


def roblox_window():
    """HWND окна клиента Roblox (заголовок ровно 'Roblox', браузер не подходит) или None."""
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd) and _is_roblox_title(_title(hwnd)):
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def foreground_is_roblox():
    try:
        return _is_roblox_title(_title(user32.GetForegroundWindow()))
    except Exception:
        return False


def activate_roblox():
    hwnd = roblox_window()
    if not hwnd:
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    return foreground_is_roblox()
