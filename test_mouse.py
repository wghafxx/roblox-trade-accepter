"""Диагностика кликов. Открой БЛОКНОТ, поставь курсор в текст, запусти: python test_mouse.py
Если в блокноте напечатается 'qq' — клики в винде работают, дело в версии Roblox (читай ниже).
Если и в блокноте тишина — запускай консоль от администратора.
"""
import sys
import time

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from mouse import click, move, foreground_is_roblox  # noqa: E402
import ctypes  # noqa: E402

print("Курсор сейчас где стоит — через 3 сек кликну туда два раза и двину мышь по квадрату.")
print("Активное окно — roblox?", foreground_is_roblox())
admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
print("Запущено от администратора?", admin)
time.sleep(3)

x = ctypes.windll.user32.GetCursorPos
import ctypes as _c


class P(_c.Structure):
    _fields_ = [("x", _c.c_long), ("y", _c.c_long)]


p = P()
ctypes.windll.user32.GetCursorPos(ctypes.byref(p))
print(f"Кликаю в ({p.x}, {p.y}) два раза...")
click(p.x, p.y)
click(p.x, p.y)
print("Рисую квадрат мышью...")
for dx, dy in [(200, 0), (0, 200), (-200, 0), (0, -200)]:
    ctypes.windll.user32.GetCursorPos(ctypes.byref(p))
    move(p.x + dx, p.y + dy)
    time.sleep(0.3)
print("Готово. Видел движение и клики? (в блокноте должен выделиться текст)")
