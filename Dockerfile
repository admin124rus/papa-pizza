FROM python:3.11-slim

# рабочая папка
WORKDIR /app

# копируем зависимости
COPY requirements.txt .

# устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# копируем весь проект
COPY . .

# запуск бота
CMD ["python", "main.py"]