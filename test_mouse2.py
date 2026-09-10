"""Проверка кликов новым способом.

1) python test_mouse2.py  — покажет режим (interception или sendinput)
2) открой игру, наведи мысль... просто смотри: бот кликнет по человечку сам.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mouse  # noqa: E402

print("Режим:", mouse.mode())
input("Открой игру (Trade Plaza), чтобы был виден левый край с иконками, и нажми Enter...")
x = int(input("X иконки человечка: "))
y = int(input("Y иконки человечка: "))
print("Двигаюсь плавно и кликаю через 2 сек...")
time.sleep(2)
mouse.click(x, y, pre_delay=0.2)
print("Готово. Меню открылось?")
