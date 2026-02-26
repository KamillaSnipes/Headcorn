# Decision Tracker — Headcorn

Веб-трекер решений для контроля исполнения.

## Деплой на Railway

1. Создай репозиторий на GitHub:
   ```bash
   cd decision-tracker-app
   git init
   git add .
   git commit -m "initial: decision tracker"
   ```

2. Запуши на GitHub:
   ```bash
   gh repo create headcorn-decision-tracker --private --source=. --push
   ```

3. Зайди на [railway.app](https://railway.app):
   - New Project → Deploy from GitHub repo
   - Выбери `headcorn-decision-tracker`
   - Railway автоматически определит Python-проект
   - Добавь volume для сохранения данных (Settings → Volumes → Mount path: `/data`)
   - Добавь переменную окружения: `DATA_FILE=/data/decisions.json`
   - Перейди в Settings → Networking → Generate Domain

4. Готово. Трекер доступен по ссылке.

## Локальный запуск

```bash
pip install -r requirements.txt
python app.py
```

Откроется на http://localhost:5000

## Важно: Volume на Railway

Без подключённого Volume данные хранятся в памяти контейнера и **пропадут при редеплое**.
Обязательно подключи Volume с путём `/data` и установи `DATA_FILE=/data/decisions.json`.
