#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import logging
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

# ================== CONFIG ==================

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_CREDENTIALS_JSON_PATH = os.getenv("GOOGLE_CREDENTIALS_JSON_PATH", "credentials.json")

if not TELEGRAM_BOT_TOKEN or not GOOGLE_SHEET_ID:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN или GOOGLE_SHEET_ID не заданы")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fitness_bot")

MOTIVATION_TIPS = [
    "Продолжай в том же духе, ты уже строишь сильную привычку.",
    "Не забывай про восстановление и сон — они усиливают эффект каждой тренировки.",
    "Даже маленькая тренировка лучше, чем её отсутствие.",
    "Старайся фокусироваться на прогрессе, а не на идеале.",
    "Помни, что дисциплина важнее мотивации — просто делай следующий шаг.",
    "Добавь чуть больше движения в течение дня: шаги, лестница, лёгкая растяжка.",
    "Отслеживай не только калории, но и своё самочувствие — это главный индикатор.",
    "Иногда лучше сделать полегче, чем пропустить тренировку совсем.",
    "Закрепи результат: немного разминки утром и заминки после тренировки.",
    "Не сравнивай себя с другими — сравнивай себя с собой вчерашним."
]

def get_random_tip() -> str:
    return random.choice(MOTIVATION_TIPS)

# ================== GOOGLE SHEETS ==================

def sheets_service():
    creds = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_JSON_PATH,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds)

def read_sheets() -> List[Dict]:
    """
    Ожидаем в таблице структуру столбцов:
    A: Дата
    B: Тип
    C: Длительность
    D: Калории
    E: Режим
    F: Замеры

    Первая строка — заголовки, её пропускаем.
    """
    service = sheets_service()
    res = service.spreadsheets().values().get(
        spreadsheetId=GOOGLE_SHEET_ID,
        range="A:F"
    ).execute()

    values = res.get("values", [])
    if len(values) < 2:
        return []

    data_rows = values[1:]  # пропускаем заголовки

    result = []
    for row in data_rows:
        date = row[0] if len(row) > 0 else ""
        ttype = row[1] if len(row) > 1 else ""
        duration = row[2] if len(row) > 2 else ""
        calories = row[3] if len(row) > 3 else ""
        mode = row[4] if len(row) > 4 else ""
        measure = row[5] if len(row) > 5 else ""
        result.append(
            {
                "Дата": date,
                "Тип": ttype,
                "Длительность": duration,
                "Калории": calories,
                "Режим": mode,
                "Замеры": measure,
            }
        )
    return result

def write_to_sheets(row: list):
    service = sheets_service()
    service.spreadsheets().values().append(
        spreadsheetId=GOOGLE_SHEET_ID,
        range="A:F",
        valueInputOption="RAW",
        body={"values": [row]},
    ).execute()

# ================== DATE ==================

def parse_date(date_str: str) -> Optional[datetime]:
    """
    Поддерживаем форматы:
    - YYYY-MM-DD HH:MM
    - YYYY-MM-DD
    - DD.MM.YYYY
    """
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except Exception:
            pass
    return None

# ================== AI ==================

def openai_ask(prompt: str) -> Optional[str]:
    """
    GPT-4o-mini анализ. Если ключа нет/ошибка — возвращаем None
    и дальше используем fallback-анализ.
    """
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY не задан, используется fallback-анализ.")
        return None

    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": "Ты профессиональный фитнес‑тренер. Отвечай кратко и по делу на русском языке."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 500,
            },
            timeout=20,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"OpenAI недоступен: {e}")
        return None

# ================== PARSER ==================

def parse_training_message(text: str) -> Optional[Dict]:
    """
    Парсим сообщение пользователя, например:
    'Коньки, 30 мин, 250 ккал'
    """
    m = re.search(
        r"(?P<type>[А-Яа-яA-Za-z\s]+)[,:\s]+(?P<duration>\d+)\s*мин[,:\s]*(?P<calories>\d+)",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    return {
        "type": m.group("type").strip(),
        "duration": int(m.group("duration")),
        "calories": int(m.group("calories")),
    }

# ================== ANALYTICS ==================

def extract_int_safe(val) -> int:
    """
    Аккуратно приводим значение к int.
    """
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip()
    if not s:
        return 0
    try:
        return int(s)
    except ValueError:
        m = re.search(r"\d+", s)
        return int(m.group()) if m else 0

def fallback_analysis(data: List[Dict]) -> str:
    """
    Сухая статистика без мотивационного текста (для недельного/общего анализа,
    если OpenAI недоступен).
    """
    total = len(data)

    durations = [d.get("Длительность", "") for d in data]
    calories_raw = [d.get("Калории", "") for d in data]

    duration = sum(extract_int_safe(v) for v in durations)
    calories = sum(extract_int_safe(v) for v in calories_raw)

    text = (
        f"📊 Тренировок: {total}\n"
        f"⏱ Время: {duration} мин\n"
        f"🔥 Калории: {calories} ккал\n"
    )
    return text

def ai_analysis(data: List[Dict]) -> str:
    """
    AI анализирует список тренировок (неделя, все).
    Модель сама формирует и вывод, и мотивирующие рекомендации.
    Если OpenAI недоступен — используем fallback_analysis.
    """
    if not data:
        return "⚠️ Нет данных для анализа"

    summary = ""
    for d in data:
        calories = extract_int_safe(d.get("Калории", 0))
        duration = extract_int_safe(d.get("Длительность", 0))
        summary += (
            f"- {d.get('Дата')}: {d.get('Тип')}, "
            f"{duration} мин, {calories} ккал\n"
        )

    prompt = (
        "Проанализируй эти тренировки: регулярность, нагрузку, разнообразие и баланс.\n"
        "Сделай вывод и практические рекомендации, обязательно закончи мотивирующим советом.\n"
        "Пиши 4–7 предложений без списков.\n\n"
        f"{summary}"
    )

    ai = openai_ask(prompt)
    if ai:
        return ai
    else:
        return fallback_analysis(data)

def ai_analysis_single(data: List[Dict]) -> str:
    """
    Анализ одной последней тренировки + случайный мотивационный совет.
    Если OpenAI недоступен — используем fallback + рандомный совет.
    """
    if not data:
        return "⚠️ Нет данных для анализа"

    d = data[-1]
    calories = extract_int_safe(d.get("Калории", 0))
    duration = extract_int_safe(d.get("Длительность", 0))

    summary = (
        f"- {d.get('Дата')}: {d.get('Тип')}, "
        f"{duration} мин, {calories} ккал\n"
    )

    prompt = (
        "Проанализируй эту одну тренировку: вид нагрузки, длительность и калорийность.\n"
        "Сделай краткий вывод (2–4 предложения) только про эту тренировку.\n\n"
        f"{summary}"
    )

    ai = openai_ask(prompt)
    if ai:
        return ai + f"\n\n💡 Совет: {get_random_tip()}"
    else:
        base = fallback_analysis(data)
        return base + f"\n\n💡 Совет: {get_random_tip()}"

# ================== MOTIVATION ==================

def inactivity_warning(data: List[Dict]) -> Optional[str]:
    if not data:
        return None

    last_date = parse_date(data[-1].get("Дата", ""))
    if not last_date:
        return None

    if datetime.now() - last_date > timedelta(days=3):
        return "⏰ Ты не тренировался больше 3 дней. Самое время размяться!"
    return None

# ================== HANDLERS ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Умный AI Спортдневник\n\n"
        "✍️ Запись:\nБег, 30 мин, 400 ккал\n\n"
        "📊 Команды:\n"
        "/analysis_week — отчёт за 7 дней\n"
        "/analysis_last — последняя тренировка\n"
        "/analysis_all — все тренировки"
    )

async def add_training(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parsed = parse_training_message(update.message.text)
    if not parsed:
        await update.message.reply_text("Пример: Бег, 30 мин, 400 ккал")
        return

    # Дата | Тип | Длительность | Калории | Режим | Замеры
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M"),  # Дата
        parsed["type"],                             # Тип
        parsed["duration"],                         # Длительность (мин)
        parsed["calories"],                         # Калории (ккал)
        "",                                         # Режим
        "",                                         # Замеры
    ]
    write_to_sheets(row)

    data = read_sheets()
    warn = inactivity_warning(data)

    # Анализ именно последней записи + рандомный совет
    analysis = ai_analysis_single(data[-1:]) if data else "⚠️ Нет данных для анализа"

    text = "✅ Тренировка записана!\n\n" + analysis
    if warn:
        text = warn + "\n\n" + text

    await update.message.reply_text(text)

async def analysis_last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = read_sheets()

    if not data:
        await update.message.reply_text("Пока нет записей тренировок.")
        return

    # Анализ последней тренировки как одиночной (+ рандомный совет)
    await update.message.reply_text(ai_analysis_single(data[-1:]))

async def analysis_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = read_sheets()
    cutoff = datetime.now() - timedelta(days=7)

    week = []
    for d in data:
        date = parse_date(d.get("Дата", ""))
        if date and date >= cutoff:
            week.append(d)

    await update.message.reply_text(ai_analysis(week))

async def analysis_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Анализ всех тренировок (21 и любые будущие).
    """
    data = read_sheets()

    if not data:
        await update.message.reply_text("Пока нет записей тренировок.")
        return

    await update.message.reply_text(ai_analysis(data))

# ================== MAIN ==================

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analysis_last", analysis_last))
    app.add_handler(CommandHandler("analysis_week", analysis_week))
    app.add_handler(CommandHandler("analysis_all", analysis_all))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_training))

    logger.info("🚀 Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
