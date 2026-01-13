# 🏋️ AI Sportdnevnik - AI-powered Sports Diary

Telegram bot + Google Sheets integration for tracking training sessions with AI-powered analysis using GigaChat.

## Features

✅ **Telegram Bot Commands:**
- `/start` - Introduction and help
- `/report` - Weekly training report from GigaChat
- `/analysis` - Personal sports analysis and recommendations
- Send text messages to log training (e.g., "Коньки 45 мин, легко")

✅ **Google Sheets Integration:**
- Auto-save training data to Google Sheets
- Read last 7-10 sessions for reports/analysis
- Support for date, activity, duration, feeling, weight tracking

✅ **GigaChat AI:**
- Automatic training session analysis
- Weekly performance reports
- Personalized recommendations
- Error handling and fallback mode

## Setup

### 1. Clone Repository
```bash
git clone https://github.com/kiboto30-creator/AI-sportdnevnik.git
cd AI-sportdnevnik
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment

**Create `.env` file (copy from `.env.example`):**
```bash
cp .env.example .env
```

**Fill in your credentials:**
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
GIGACHAT_CLIENT_ID=your_gigachat_client_id_here
GIGACHAT_CLIENT_SECRET=your_gigachat_client_secret_here
GOOGLE_SHEET_ID=your_google_sheet_id_here
GOOGLE_CREDENTIALS_JSON=credentials.json
```

### 4. Google Sheets Setup

1. Create a [Google Cloud Project](https://console.cloud.google.com/)
2. Enable Google Sheets API
3. Create a Service Account
4. Download JSON credentials as `credentials.json`
5. Share your Google Sheet with the service account email

### 5. Telegram Bot Setup

1. Create bot with [@BotFather](https://t.me/botfather) on Telegram
2. Get bot token and add to `.env`

### 6. GigaChat Setup

1. Register at [GigaChat](https://gigachat.devices.sberbank.ru/)
2. Get CLIENT_ID and CLIENT_SECRET
3. Add to `.env`

## Usage

### Run Bot
```bash
python fitness_bot.py
```

### Telegram Commands

**Start Bot:**
```
/start
```

**Log Training (send text):**
```
Коньки, 45 мин, легко
Бег, 5 км, усталость средняя
Зал турник, 30 мин, хорошо
```

**Get Weekly Report:**
```
/report
```

**Get Analysis:**
```
/analysis
```

## Project Structure

```
├── fitness_bot.py          # Main bot code
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (git-ignored)
├── .env.example           # Template for .env
├── .gitignore             # Git ignore rules
├── credentials.json        # Google API credentials (git-ignored)
└── README.md              # This file
```

## Technical Details

### Technologies Used
- **python-telegram-bot** - Telegram bot framework
- **Google Sheets API** - Data storage and retrieval
- **GigaChat API** - AI analysis and report generation
- **python-dotenv** - Environment variable management

### Error Handling
- Graceful fallback to demo data if Google Sheets unavailable
- Try-except blocks for GigaChat API failures
- User-friendly error messages

## Security

⚠️ **Important:**
- Never commit `.env` or `credentials.json` to Git
- Use `.gitignore` to protect sensitive files
- Keep your API keys confidential
- Regenerate keys if they're exposed

## Demo Data

If Google Sheets is not configured, bot uses demo training data:
- 13.01.2026: Коньки 45 мин, легко
- 14.01.2026: Зал турник 30 мин, усталость средняя
- 15.01.2026: Бег 5 км, стандартно

## Future Improvements

- [ ] Advanced text parsing for training data
- [ ] Weight tracking with trends
- [ ] Photo support for training logs
- [ ] Leaderboard for multi-user tracking
- [ ] Mobile app integration
- [ ] Data visualization and charts

## License

MIT License - feel free to use for personal projects

## Support

For issues or questions, open an issue on GitHub.

---

**Made with ❤️ for fitness enthusiasts**
