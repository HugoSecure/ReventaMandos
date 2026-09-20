FROM python:3.11-slim

WORKDIR /app

# Copiar dependencias primero (mejora caché de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código del bot
COPY vinted_monitor.py .
COPY .env.example .

# Puerto para el health check
EXPOSE 8080

# Variable de entorno por defecto
ENV PORT=8080

# Ejecutar el bot
CMD ["python", "vinted_monitor.py"]
