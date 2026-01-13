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
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1eilH6uSqN_dd6sxB90hOc2LSChm7d2XtOaQDbboQR1w")
GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
GIGACHAT_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "credentials.json")

# ===== GIGACHAT FUNCTIONS =====
def get_gigachat_token():
    """Получает свежий Access Token автоматически"""
    try:
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
    except Exception as e:
        print(f"❌ Ошибка получения GigaChat токена: {e}")
        return None

def gigachat_ask(prompt):
    """Запрос к GigaChat с обработкой ошибок"""
    try:
        token = get_gigachat_token()
        if not token:
            return "⚠️ Ошибка: Не удалось подключиться к GigaChat API"
        
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
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка GigaChat API: {e}")
        return "⚠️ GigaChat временно недоступен. Попробуй позже."
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return "⚠️ Ошибка при обработке запроса"

# ===== GOOGLE SHEETS FUNCTIONS =====
def get_sheets_service():
    """Подключение к Google Sheets API"""
    try:
        credentials = Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_JSON,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        return build('sheets', 'v4', credentials=credentials)
    except FileNotFoundError:
        print("⚠️ Файл credentials.json не найден. Используем режим без записи в Sheets.")
        return None
    except Exception as e:
        print(f"❌ Ошибка подключения к Google Sheets: {e}")
        return None

def read_sheets(num_rows=7):
    """Читает последние N строк из Google Sheets"""
    try:
        service = get_sheets_service()
        if not service:
            # Возвращаем примеры данных если нет доступа
            return [
                ["13.01.2026", "Коньки", "45 мин", "Легко", "78 кг", "", "Зимний старт"],
                ["14.01.2026", "Зал турник", "30 мин", "Усталость средняя", "77.8", "", ""],
                ["15.01.2026", "Бег", "5 км", "Стандартно", "", "", "Вечерний"],
            ]
        
        result = service.spreadsheets().values().get(
            spreadsheetId=GOOGLE_SHEET_ID,
            range='Sheet1!A2:G100'  # Пропускаем заголовок
        ).execute()
        
        values = result.get('values', [])
        # Возвращаем последние N строк
        return values[-num_rows:] if values else []
    except Exception as e:
        print(f"❌ Ошибка чтения из Sheets: {e}")
        return []

def write_to_sheets(row_data):
    """Записывает новую тренировку в Google Sheets"""
    try:
        service = get_sheets_service()
        if not service:
            print("⚠️ Не удалось подключиться к Google Sheets для записи")
            return False
        
        # Добавляем новую строку в конец
        body = {
            'values': [row_data]
        }
        
        result = service.spreadsheets().values().append(
            spreadsheetId=GOOGLE_SHEET_ID,
            range='Sheet1!A:G',
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        
        print(f"✅ Данные записаны в Sheets: {row_data}")
        return True
    except Exception as e:
        print(f"❌ Ошибка записи в Sheets: {e}")
        return False

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
    
    # Парсим простой текст
    parts = message.split(',')
    activity = parts[0].strip() if parts else "Тренировка"
    time_info = parts[1].strip() if len(parts) > 1 else "?"
    feeling = parts[2].strip() if len(parts) > 2 else "Хорошо"
    
    # Подготавливаем данные для записи в Sheets
    date_str = datetime.now().strftime('%d.%m.%Y')
    row_data = [date_str, activity, time_info, feeling, "", "", ""]
    
    # Записываем в Google Sheets
    write_to_sheets(row_data)
    
    await update.message.reply_text(
        f"✅ Залогирована тренировка:\n"
        f"📅 {date_str}\n"
        f"🏃 {activity}\n"
        f"⏱️ {time_info}\n"
        f"😊 {feeling}\n\n"
        "Отправь `/report` для отчёта!"
    )

async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерирует отчёт за неделю"""
    await update.message.reply_text("📊 Генерирую отчёт за неделю...")
    
    data = read_sheets(7)
    if not data:
        await update.message.reply_text("⚠️ Нет данных о тренировках за последнюю неделю")
        return
    
    formatted_data = "\n".join([
        f"- {row[0]}: {row[1]} ({row[2]}), {row[3]}"
        for row in data if len(row) >= 4
    ])
    
    prompt = f"""Ты — AI-коуч по фитнесу. На основе этих данных тренировок за неделю:
**Данные:**
{formatted_data}

Создай **ПОЛНЫЙ ОТЧЁТ**:
### 1. КОНСПЕКТ НЕДЕЛИ
Что делал, сколько сеансов, ключевые активности (коньки/бег/зал).
### 2. СТАТИСТИКА И БАЛАНС
| Вид активности | Кол-во раз | Время |
| -------------- | ---------- | ------ |
| Активность | X | XX мин |
### 3. МОТИВАЦИЯ
3 предложения позитивного вывода.
### 4. РЕКОМЕНДАЦИИ
3-4 совета на следующую неделю.
**Стиль:** минималистичный, структурированный, Markdown."""
    
    report = gigachat_ask(prompt)
    await update.message.reply_text(f"📈 **Отчёт за неделю:**\n\n{report}")

async def personal_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Анализ стиля тренировок"""
    await update.message.reply_text("🎯 Генерирую персональный анализ...")
    
    data = read_sheets(10)
    if not data:
        await update.message.reply_text("⚠️ Недостаточно данных для анализа")
        return
    
    formatted_data = "\n".join([
        f"- {row[0]}: {row[1]} ({row[2]}), {row[3]}"
        for row in data if len(row) >= 4
    ])
    
    prompt = f"""На основе лога тренировок:
{formatted_data}

Создай **ПЕРСОНАЛЬНЫЙ АНАЛИЗ**:
1. **МОЙ СТИЛЬ ТРЕНИРОВОК:** какой я спортсмен?
2. **СИЛЬНЫЕ СТОРОНЫ:** что хорошо получается?
3. **ПУТИ РАЗВИТИЯ:** где улучшить?
4. **ДОЛГОСРОЧНЫЙ ПЛАН:** 5 целей на зиму.
**Тон:** мотивирующий, персональный, как разговор с другом."""
    
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
