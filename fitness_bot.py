import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# ===== НАСТРОЙКИ =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Из .env
GOOGLE_SHEET_ID = "1eilH6uSqN_dd6sxB90hOc2LSChm7d2XtOaQDbboQR1w"  # Твой Sheet
GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
GIGACHAT_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")

# ===== GIGACHAT FUNCTIONS =====
def get_gigachat_token():
    """Получает свежий Access Token автоматически"""
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    data = {"scope": "GIGACHAT_API_PERS"}
    auth = (GIGACHAT_CLIENT_ID, GIGACHAT_CLIENT_SECRET)
    
    resp = requests.post(url, headers=headers, data=data, auth=auth, verify=True)
    resp.raise_for_status()
    return resp.json()["access_token"]

def gigachat_ask(prompt):
    """Запрос к GigaChat"""
    token = get_gigachat_token()
    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    payload = {
        "model": "GigaChat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    
    resp = requests.post(url, headers=headers, json=payload, verify=True)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

# ===== GOOGLE SHEETS =====
def read_sheets():
    """Читает последние 7 строк из твоего Sheets"""
    # Создай сервисный аккаунт или используй ручной ввод для прототипа
    # Пока упрощённо: возвращаем пример данных
    return [
        ["13.01.2026", "Коньки", "45 мин", "Легко", "78 кг", "", "Зимний старт"],
        ["14.01.2026", "Зал турник", "30 мин", "Усталость средняя", "77.8", "", ""],
        ["15.01.2026", "Бег", "5 км", "Стандартно", "", "", "Вечерний"],
    ]

# ===== TELEGRAM HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏋️ **AI Спортдневник** готов!\n\n"
        "📝 **Как использовать:**\n"
        "• Отправь текст тренировки (пример: \"Коньки 45 мин, легко\")\n"
        "• `/report` — отчёт за неделю\n"
        "• `/analysis` — анализ стиля тренировок\n\n"
        "✅ Подключён к GigaChat API и твоему Google Sheets!"
    )

async def add_training(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет тренировку из текста"""
    message = update.message.text
    
    # Парсим простой текст (можно улучшить)
    parts = message.split()
    activity = parts[0] if parts else "Тренировка"
    time = parts[1] if len(parts) > 1 else "?"
    feeling = " ".join(parts[2:]) if len(parts) > 2 else "Хорошо"
    
    # TODO: записать в Sheets
    await update.message.reply_text(
        f"✅ Залогирована тренировка:\n"
        f"📅 {datetime.now().strftime('%d.%m.%Y')}\n"
        f"🏃 {activity}\n"
        f"⏱️ {time}\n"
        f"😊 {feeling}\n\n"
        "Отправь `/report` для отчёта!"
    )

async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерирует отчёт за неделю"""
    await update.message.reply_text("📊 Генерирую отчёт за неделю...")
    
    data = read_sheets()
    formatted_data = "\n".join([
        f"- {row[0]}: {row[1]} ({row[2]}), {row[3]}"
        for row in data
    ])
    
    prompt = f"""
Ты — AI-коуч по фитнесу. На основе этих данных тренировок за неделю:

**Данные:**
{formatted_data}

Создай **ПОЛНЫЙ ОТЧЁТ**:

### 1. КОНСПЕКТ НЕДЕЛИ
Что делал, сколько сеансов, ключевые активности (коньки/бег/зал).

### 2. СТАТИСТИКА И БАЛАНС
| Вид активности | Кол-во раз | Время  |
| -------------- | ---------- | ------ |
| Коньки         | X          | XX мин |
| Зал            | Y          | YY мин |

### 3. МОТИВАЦИЯ
3 предложения позитивного вывода.

### 4. РЕКОМЕНДАЦИИ
3-4 совета на следующую неделю.

**Стиль:** минималистичный, структурированный, Markdown.
"""
    
    report = gigachat_ask(prompt)
    await update.message.reply_text(f"📈 **Отчёт за неделю:**\n\n{report}")

async def personal_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Анализ стиля тренировок"""
    data = read_sheets()
    formatted_data = "\n".join([
        f"- {row[0]}: {row[1]} ({row[2]}), {row[3]}"
        for row in data
    ])
    
    prompt = f"""
На основе лога тренировок: {formatted_data}

Создай **ПЕРСОНАЛЬНЫЙ АНАЛИЗ**:

1. **МОЙ СТИЛЬ ТРЕНИРОВОК:** какой я спортсмен?
2. **СИЛЬНЫЕ СТОРОНЫ:** что хорошо получается?
3. **ПУТИ РАЗВИТИЯ:** где улучшить?
4. **ДОЛГОСРОЧНЫЙ ПЛАН:** 5 целей на зиму.

**Тон:** мотивирующий, персональный, как разговор с другом.
"""
    
    analysis = gigachat_ask(prompt)
    await update.message.reply_text(f"🎯 **Твой анализ:**\n\n{analysis}")

# ===== ЗАПУСК =====
def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", generate_report))
    app.add_handler(CommandHandler("analysis", personal_analysis))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_training))
    
    print("🚀 Бот запущен! Отправь /start в @Sportdnevnik_bot")
    app.run_polling()

if __name__ == "__main__":
    main()
  
