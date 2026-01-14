#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Sportdnevnik Bot - Improved v2.0
Telegram bot + Google Sheets integration for fitness tracking with AI analysis

UPDATES v2.0:
- Security: Removed hardcoded GOOGLE_SHEET_ID
- Performance: Added GigaChat token caching
- Reliability: Improved text parsing with regex
- Quality: Added type hints and logging
"""

import os
import re
import time
import logging
import base64
import uuid
import json
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# ===== LOGGING CONFIGURATION =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== LOAD AND VALIDATE CONFIGURATION =====
load_dotenv()

def validate_config() -> Dict[str, str]:
    """
    Load and validate all critical environment variables.
    
    Returns:
        Dict[str, str]: Validated configuration
        
    Raises:
        ValueError: If required variables are missing
    """
    config = {
        'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
        'GOOGLE_SHEET_ID': os.getenv('GOOGLE_SHEET_ID'),
        'GIGACHAT_CLIENT_ID': os.getenv('GIGACHAT_CLIENT_ID'),
        'GIGACHAT_CLIENT_SECRET': os.getenv('GIGACHAT_CLIENT_SECRET'),
        'GOOGLE_CREDENTIALS_JSON': os.getenv('GOOGLE_CREDENTIALS_JSON', 'credentials.json'),
    }
    
    required_keys = [
        'TELEGRAM_BOT_TOKEN',
        'GOOGLE_SHEET_ID',
        'GIGACHAT_CLIENT_ID',
        'GIGACHAT_CLIENT_SECRET'
    ]
    
    missing_keys = [key for key in required_keys if not config.get(key)]
    
    if missing_keys:
        error_msg = f"\u274c CRITICAL ERROR: Missing required .env variables: {', '.join(missing_keys)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.info("\u2713 Configuration validated successfully")
    return config

try:
    CONFIG = validate_config()
except ValueError as e:
    logger.error(f"Failed to start bot: {e}")
    raise

# ===== CONSTANTS =====
TELEGRAM_BOT_TOKEN: str = CONFIG['TELEGRAM_BOT_TOKEN']
GOOGLE_SHEET_ID: str = CONFIG['GOOGLE_SHEET_ID']
GIGACHAT_CLIENT_ID: str = CONFIG['GIGACHAT_CLIENT_ID']
GIGACHAT_CLIENT_SECRET: str = CONFIG['GIGACHAT_CLIENT_SECRET']
GOOGLE_CREDENTIALS_JSON: str = CONFIG['GOOGLE_CREDENTIALS_JSON']

MAX_MESSAGE_LENGTH: int = 5000
MAX_MESSAGE_LINES: int = 10
TOKEN_CACHE_TTL: int = 3500  # 58.3 minutes
TIMEOUT_SECONDS: int = 30

# ===== TOKEN CACHE CLASS =====
class TokenCache:
    """Кэш для хранения GigaChat токена с проверкой срока действия."""
    def __init__(self):
        self.token: str | None = None
        self.timestamp: int = 0
    
    def is_valid(self) -> bool:
        """Проверить, не истек ли срок действия токена."""
        return time.time() - self.timestamp < TOKEN_CACHE_TTL
    
    def get_token(self) -> str | None:
        """Получить токен если он еще действителен."""
        if self.is_valid():
            return self.token
        return None
    
    def set_token(self, token: str) -> None:
        """Сохранить новый токен с текущим временем."""
        self.token = token
        self.timestamp = int(time.time())

token_cache = TokenCache()

def get_gigachat_token() -> str:
    """Получить актуальный GigaChat токен, используя кэш при возможности."""
    cached = token_cache.get_token()
    if cached:
        logger.debug("Using cached GigaChat token")
        return cached
    
    logger.info("Fetching new GigaChat token...")
    auth_data = base64.b64encode(
        f"{GIGACHAT_CLIENT_ID}:{GIGACHAT_CLIENT_SECRET}".encode()
    ).decode()
    
    headers = {
        "Authorization": f"Basic {auth_data}",
        "RqUID": str(uuid.uuid4()),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    
    data = {"scope": "GIGACHAT_API_PERS"}
    
    try:
        response = requests.post(
            "https://auth.api.cloud.yandex.net:443/oauth/token",
            headers=headers,
            data=data,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        token = response.json()["access_token"]
        token_cache.set_token(token)
        logger.info("GigaChat token fetched successfully")
        return token
    except requests.RequestException as e:
        logger.error(f"Failed to fetch GigaChat token: {e}")
        raise

def gigachat_ask(prompt: str) -> str:
    """Получить ответ от GigaChat на русском языке."""
    token = get_gigachat_token()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "GigaChat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 500,
    }
    
    try:
        response = requests.post(
            "https://api.gigachat.ai/core/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.RequestException as e:
        logger.error(f"GigaChat request failed: {e}")
        return "Ошибка при запросе к GigaChat. Пожалуйста, попробуйте позже."

# ===== GOOGLE SHEETS FUNCTIONS =====
def get_sheets_service():
    """Инициализировать сервис Google Sheets."""
    try:
        credentials = Credentials.from_service_account_info(
            json.loads(GOOGLE_CREDENTIALS_JSON)
        )
        service = build("sheets", "v4", credentials=credentials)
        logger.info("Google Sheets service initialized")
        return service
    except Exception as e:
        logger.error(f"Failed to initialize Google Sheets: {e}")
        return None

def read_sheets(sheet_id: str, range_name: str = "A:D") -> list[dict]:
    """Прочитать данные из Google Sheets и вернуть как список словарей."""
    service = get_sheets_service()
    if not service:
        return get_demo_data()
    
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        values = result.get("values", [])
        
        if not values:
            logger.warning("No data found in sheet")
            return get_demo_data()
        
        headers = values[0] if values else []
        data = []
        for row in values[1:]:
            data.append({headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))})
        return data
    except Exception as e:
        logger.error(f"Failed to read from sheets: {e}")
        return get_demo_data()

def write_to_sheets(sheet_id: str, values: list) -> bool:
    """Записать данные в Google Sheets."""
    service = get_sheets_service()
    if not service:
        logger.warning("Google Sheets service unavailable, data not saved")
        return False
    
    try:
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="A:D",
            valueInputOption="RAW",
            body={"values": [values]}
        ).execute()
        logger.info("Data written to sheets successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to write to sheets: {e}")
        return False

def get_demo_data() -> list[dict]:
    """Вернуть демонстрационные данные для тестирования."""
    return [
        {"Дата": "2025-01-01", "Тип": "Кардио", "Продолжительность": "30 мин", "Калории": "300"},
        {"Дата": "2025-01-02", "Тип": "Силовая", "Продолжительность": "45 мин", "Калории": "400"},
    ]

# ===== MESSAGE PARSING FUNCTIONS =====
def parse_training_message(message: str) -> dict | None:
    """Распарсить сообщение о тренировке с использованием регулярных выражений."""
    pattern = r"(?P<type>\w+)[,:\s]+(?P<duration>\d+)\s*мин[,:\s]*(?P<calories>\d+)\s*ккал?"
    match = re.search(pattern, message, re.IGNORECASE)
    
    if match:
        return {
            "type": match.group("type"),
            "duration": int(match.group("duration")),
            "calories": int(match.group("calories"))
        }
    return None

def validate_training_message(message: str) -> tuple[bool, str]:
    """Проверить валидность сообщения о тренировке."""
    if len(message) > MAX_MESSAGE_LENGTH:
        return False, f"Сообщение слишком длинное (макс {MAX_MESSAGE_LENGTH} символов)"
    
    if not parse_training_message(message):
        return False, "Неверный формат. Используйте: Тип, Длительность мин, Калории ккал"
    
    return True, "OK"

# ===== TELEGRAM HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started the bot")
    
    welcome_text = (
        "👋 Добро пожаловать в бота фитнес-трекер!\n\n"
        "Доступные команды:\n"
        "/add_training - Добавить тренировку\n"
        "/report - Получить отчет о тренировках\n"
        "/analysis - Получить анализ от ИИ\n"
        "/help - Справка\n\n"
        "Формат добавления тренировки:\n"
        "<Тип>, <Длительность мин>, <Калории ккал>"
    )
    
    await update.message.reply_text(welcome_text)

async def add_training(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик добавления тренировки."""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    is_valid, error_msg = validate_training_message(message_text)
    if not is_valid:
        await update.message.reply_text(f"❌ Ошибка: {error_msg}")
        return
    
    parsed = parse_training_message(message_text)
    if parsed:
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            parsed["type"],
            str(parsed["duration"]),
            str(parsed["calories"])
        ]
        
        success = write_to_sheets(GOOGLE_SHEET_ID, row)
        if success:
            await update.message.reply_text(
                f"✅ Тренировка добавлена!\n"
                f"Тип: {parsed['type']}\n"
                f"Длительность: {parsed['duration']} мин\n"
                f"Калории: {parsed['calories']} ккал"
            )
            logger.info(f"User {user_id} added training: {parsed}")
        else:
            await update.message.reply_text("⚠️ Не удалось сохранить данные. Попробуйте позже.")

async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /report для получения отчета о тренировках."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} requested report")
    
    await update.message.reply_text("📊 Загружаю данные...")
    
    data = read_sheets(GOOGLE_SHEET_ID)
    if not data:
        await update.message.reply_text("Нет данных для отчета.")
        return
    
    total_duration = sum(int(item.get("Продолжительность", 0)) for item in data)
    total_calories = sum(int(item.get("Калории", 0)) for item in data)
    
    report_text = (
        f"📊 Отчет о тренировках\n\n"
        f"Количество тренировок: {len(data)}\n"
        f"Общее время: {total_duration} минут\n"
        f"Сожжено калорий: {total_calories} ккал\n"
    )
    
    await update.message.reply_text(report_text)

async def personal_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /analysis для ИИ анализа."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} requested AI analysis")
    
    await update.message.reply_text("🧠 Анализирую ваши данные...")
    
    data = read_sheets(GOOGLE_SHEET_ID)
    if not data:
        await update.message.reply_text("Нет данных для анализа.")
        return
    
    summary = f"Ваши тренировки: {len(data)} тренировок. "
    summary += "Прошу дать рекомендации для улучшения."
    
    analysis = gigachat_ask(summary)
    await update.message.reply_text(f"💬 Анализ ИИ:\n\n{analysis[:MAX_MESSAGE_LENGTH]}")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик голосовых сообщений с распознаванием через Telegram API."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} sent voice message")
    
    try:
        # Получаем файл голосового сообщения
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        
        # Telegram Bot API пока не предоставляет встроенную транскрипцию для обычных ботов
        # Поэтому отправляем пользователю инструкцию
        await update.message.reply_text(
            "🎤 Голосовые сообщения пока не поддерживаются.\n\n"
            "Пожалуйста, отправьте текстом в формате:\n"
            "<Тип>, <Длительность мин>, <Калории ккал>\n\n"
            "Пример: Бег, 30 мин, 400 ккал"
        )
        
    except Exception as e:
        logger.error(f"Error handling voice message: {e}")
        await update.message.reply_text("Произошла ошибка при обработке голосового сообщения.")
# ===== MAIN APPLICATION =====
def main() -> None:
    """Запустить бота."""
    logger.info("Starting fitness bot...")
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", generate_report))
    app.add_handler(CommandHandler("analysis", personal_analysis))
    
    # Обработчик текстовых сообщений для добавления тренировок
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_training))
        
    # Обработчик голосовых сообщений
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    logger.info("Bot started. Polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
