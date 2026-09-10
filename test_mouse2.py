"""Диагностика мыши. Запуск: python test_mouse2.py
Печатает режим (interception / sendinput и ПОЧЕМУ), права, найдено ли окно Roblox,
потом сам выводит игру на передний план и кликает в указанную точку.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mouse  # noqa: E402

print("Режим мыши :", mouse.mode())
print("Админ      :", mouse.is_admin())
print("Экран      :", mouse.screen_size())
print("Окно Roblox:", "найдено" if mouse.roblox_window() else "НЕ найдено (запусти игру)")
if not mouse.using_interception():
    print("\n!!! Драйвер НЕ активен: движения будут телепортами, игра их проигнорирует.")
    print("1) install-interception.exe /install от админа 2) ПЕРЕЗАГРУЗКА 3) повторный тест.")
    raise SystemExit(2)

input("\nОткрой игру (Trade Plaza), чтобы был виден левый край с иконками, и нажми Enter...")
x = int(input("X иконки человечка: "))
y = int(input("Y иконки человечка: "))

print("Вывожу Roblox на передний план:", mouse.activate_roblox())
print("Двигаюсь плавно и кликаю через 2 сек...")
time.sleep(2)
mouse.click(x, y, pre_delay=0.2)
print("Курсор после клика:", mouse.cursor_pos(), "ожидалось:", (x, y))
print("Готово. Меню открылось? Если нет и режим sendinput — ставь драйвер Interception (README).")
