# Где хостить: честно, без рекламы

Задача была "бесплатно и 24/7". Сразу главное: полностью бесплатного хостинга,
который гарантированно не спит и не теряет данные, в 2026 практически нет.
Ниже варианты по убыванию адекватности.

## Почему бот не потеряет сообщения даже если полежит

Бот работает на long polling. Telegram хранит недоставленные апдейты **до 24
часов** и отдает их, как только бот вернулся. То есть короткий сон или
перезапуск не стоит ни одного сообщения. Потеряется только то, что старше
суток простоя.

Что бот делает со своей стороны:
- отдает `/health` по HTTP (хостинги проверяют живость именно так);
- если задан `KEEPALIVE_URL`, каждые 10 минут дергает сам себя.

Самопинг помогает не везде: Render, например, засыпает по отсутствию
**внешнего** трафика. Поэтому надежнее внешний пинг - см. ниже.

## Вариант 1. Fly.io - рекомендую

Не бесплатен формально, но реальный счет у такого бота выходит порядка
1-3$ в месяц, а часто и в нуле за счет ежемесячного кредита. Зато:

- машина не засыпает (`auto_stop_machines = false`);
- есть постоянный диск, база живет между деплоями;
- конфиг уже лежит в репозитории - `fly.toml`.

```bash
fly auth login
fly launch --no-deploy          # имя приложения возьмет из fly.toml
fly volumes create bot_data --size 1
fly secrets set BOT_TOKEN=... ANTHROPIC_API_KEY=... ADMIN_CHAT_ID=...
fly deploy
fly logs
```

## Вариант 2. Render free - бесплатно, но с оговорками

Конфиг: `render.yaml`. Деплоится в пару кликов из GitHub.

Две честные проблемы free-плана:
1. **Засыпает** после 15 минут без внешних запросов. Лечится внешним пингом:
   заведи на [cron-job.org](https://cron-job.org) задание на
   `https://твой-сервис.onrender.com/health` каждые 10 минут. Бесплатно.
2. **Нет постоянного диска.** База при каждом редеплое обнуляется: лимит
   "одна бесплатная диагностика" сбросится, лиды пропадут. Обязательно
   выгружай лиды командой `/leads`, они приходят CSV-файлом.

Если остаешься на Render - ставь `KEEPALIVE_URL` на свой публичный адрес и
все равно настрой внешний cron. Один самопинг Render не убеждает.

## Вариант 3. Oracle Cloud Always Free - бесплатно и всерьез

Реально бесплатная ARM-виртуалка навсегда, свой диск, никакого сна. Минус -
возня с регистрацией и нередкое "out of capacity" в популярных регионах.

```bash
sudo apt update && sudo apt install -y python3-venv git
git clone https://github.com/Evgeniy-Tkachenko-Ai/rutinomer-bot.git
cd rutinomer-bot && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env
```

Дальше systemd, чтобы поднимался сам:

```ini
# /etc/systemd/system/rutinomer.service
[Unit]
Description=Rutinomer bot
After=network-online.target

[Service]
WorkingDirectory=/home/ubuntu/rutinomer-bot
ExecStart=/home/ubuntu/rutinomer-bot/.venv/bin/python -m bot
Restart=always
RestartSec=5
User=ubuntu

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now rutinomer
journalctl -u rutinomer -f
```

## Что выбрать

- Хочешь, чтобы просто работало и не думать - **Fly.io**.
- Хочешь строго 0$ и готов раз настроить cron и выгружать лиды - **Render**.
- Готов один вечер потратить на сервер и забыть на год - **Oracle**.

## Бэкап базы

База - один файл SQLite. Бэкап это копирование файла:

```bash
fly ssh console -C "sqlite3 /data/bot.db '.backup /data/backup.db'"   # Fly
scp user@server:~/rutinomer-bot/data/bot.db ./bot-$(date +%F).db      # VPS
```

И независимо от этого - раз в неделю `/leads` в чате с ботом. Это самый
дешевый бэкап того, что реально важно.
