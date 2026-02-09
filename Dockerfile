FROM python:3.11-slim

WORKDIR /app

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код
COPY . .

# Запускаем бота
CMD ["python", "fitness_bot_improved.py"]
```

**Что это делает (простыми словами):**
- Берёт готовый Python 3.11
- Копирует твой код в "коробку"
- Устанавливает все библиотеки из requirements.txt
- Запускает бота

---

#### 📄 **Файл 2: `.dockerignore`**

Создай файл `.dockerignore` и вставь:
```
.env
credentials.json
__pycache__
*.pyc
.git
.gitignore
README.md
visuals.py
