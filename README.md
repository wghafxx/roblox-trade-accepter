# Roblox Trade Auto-Accepter (Trade Plaza)

Бот-автопринятие трейдов на аккаунт-приёмщик. Сидит на ПК с открытой игрой и сам:
уведомление → список трейдов → сверка ника → accept → ждёт предметы → проверки → accept.

Windows 10/11 · Python 3.11+ · ввод мыши через драйвер Interception (игра не отличает от настоящей мыши).

## Установка

1. Python: https://www.python.org/downloads/ (галочка Add to PATH).
2. Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki (хватит English).
   Путь к tesseract.exe впиши в config.yaml → tesseract_cmd.
3. Драйвер ввода (один раз):
   - скачать https://github.com/oblitum/Interception/releases
   - распаковать → `command line installer\install-interception.exe /install` **от администратора**
   - **перезагрузить ПК**
4. В папке проекта:
```
pip install -r requirements.txt
copy config.example.yaml config.yaml
```

## Калибровка (после каждого запуска обязательно один раз)

Игра → Trade Plaza. Потом:
```
python calibrate.py
```
Скрипт по шагам просит показать экран (главный → список трейдов → окно трейда)
и обвести кнопки/области. Обводи впритык, без фона.

## Тест кликов (если клики не доходят до игры)

```
python test_mouse2.py
```
Должно напечатать `Режим: interception`. Движение плавное + клик.

## Запуск

```
python bot.py
```
Не трогай мышь во время работы. Остановка — Ctrl+C. Лог: консоль + bot.log.

## Правила приёмки (в config.yaml)

- `only_nicks` — принимать ТОЛЬКО эти ники (без @). Остальным decline.
  Пусто = берётся первая строка (опасно при живых игроках!).
- `whitelist_rap` — RAP предметов, которые принимаем. Чужой предмет = decline.
- `min_total_rap` — минимальная сумма сделки.
- `max_items` — максимум предметов (6).
- `single_page_only` — есть вторая страница трейда → decline.
- `accept_stable_sec` — accept только если суммы не менялись N секунд (кд кнопки).
- `our_total` проверяется всегда: наша сторона должна быть пустой, иначе тревога + decline.

Сомнение = decline. Лог каждого решения пишется.

## Дисклеймер

Автоматизация ввода может нарушать правила Roblox — используй на свой риск,
лучше на отдельном техническом аккаунте. Код учебный, без гарантий.
