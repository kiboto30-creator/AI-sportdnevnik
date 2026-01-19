import pandas as pd
import matplotlib.pyplot as plt

def load_csv_safe(path):
    for enc in ("utf-8-sig", "utf-8", "cp1251", "latin1"):
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise UnicodeError("Cannot read CSV")

    # лечим русские заголовки
    rename_map = {
        "Р”Р°С‚Р°": "Дата",
        "РўРёРї": "Тип",
        "Р”Р»РёС‚РµР»СЊРЅРѕСЃС‚СЊ": "Длительность",
        "РљР°Р»РѕСЂРёРё": "Калории",
        "Р РµР¶РёРј": "Режим",
        "Р—Р°РјРµСЂС‹": "Замеры",
        "Р—Р°РјРµС‚РєРё": "Заметки",
    }

    df.columns = [rename_map.get(c.strip(), c.strip()) for c in df.columns]
    return df

df = load_csv_safe("data.csv")


# Убираем пробелы и неразрывные пробелы
df.columns = [c.replace("\xa0", " ").strip() for c in df.columns]

# Нормализуем имена колонок
df.columns = [c.strip() for c in df.columns]

# === Основные колонки ===
DATE = "Дата"
TYPE = "Тип"
DURATION = "Длительность"
CALORIES = "Калории"

# Проверка
for col in [DATE, TYPE, DURATION, CALORIES]:
    if col not in df.columns:
        raise ValueError(f"❌ В CSV нет колонки: {col}")

# === Подготовка данных ===
df[DATE] = pd.to_datetime(df[DATE], errors="coerce")
df = df.dropna(subset=[DATE])
df["date_only"] = df[DATE].dt.date

# === 1. Калории по дням ===
calories_by_day = df.groupby("date_only")[CALORIES].sum()

plt.figure()
calories_by_day.plot(kind="bar")
plt.title("Калории по дням")
plt.xlabel("Дата")
plt.ylabel("Ккал")
plt.tight_layout()
plt.savefig("calories_by_day.png")
plt.close()

# === 2. Длительность по дням ===
duration_by_day = df.groupby("date_only")[DURATION].sum()

plt.figure()
duration_by_day.plot(kind="bar")
plt.title("Длительность тренировок по дням")
plt.xlabel("Дата")
plt.ylabel("Минуты")
plt.tight_layout()
plt.savefig("duration_by_day.png")
plt.close()

# === 3. Распределение активности ===
activity = df.groupby(TYPE)[CALORIES].sum()

plt.figure()
plt.pie(activity, labels=activity.index, autopct="%1.0f%%")
plt.title("Распределение активности (по калориям)")
plt.tight_layout()
plt.savefig("activity_distribution.png")
plt.close()

# === 4. Накопленные калории ===
cumulative = calories_by_day.cumsum()

plt.figure()
cumulative.plot()
plt.title("Накопленные калории")
plt.xlabel("Дата")
plt.ylabel("Ккал")
plt.tight_layout()
plt.savefig("cumulative_calories.png")
plt.close()

print("✅ Визуализация успешно создана")
