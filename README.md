# VintedMandos Bot 🎮

Bot que monitoriza **Vinted** cada 5 minutos buscando chollos de mandos de videoconsola (PS5, PS4, Switch, Xbox) y envía alertas a **Telegram**.

**Ejecuta 24/7 gratis** usando GitHub Actions (repositorio público = minutos ilimitados).

---

## 🚀 Configuración (5 minutos)

### 1. Crear el Bot de Telegram

1. Abre Telegram → busca **@BotFather**
2. Envía `/newbot` → elige nombre y username
3. Copia el **token** que te da

### 2. Obtener tu Chat ID

1. Envía `/start` a tu bot
2. Abre en el navegador:
   ```
   https://api.telegram.org/bot<TU_TOKEN>/getUpdates
   ```
3. Busca `"chat": {"id": 123456789}` → ese es tu **Chat ID**

### 3. Configurar Secrets en GitHub

1. Ve a tu repositorio → **Settings** → **Secrets and variables** → **Actions**
2. Haz clic en **"New repository secret"** y añade:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Tu token de BotFather |
| `TELEGRAM_CHAT_ID` | Tu chat ID |

### 4. ¡Listo!

El bot se ejecuta automáticamente **cada 5 minutos**. No necesitas hacer nada más.

Para ejecutarlo manualmente: **Actions** → **VintedMandos Scan** → **Run workflow**

---

## 📁 Estructura

```
ReventaMandos/
├── vinted_monitor.py              # Script principal
├── requirements.txt               # Dependencias
├── .github/workflows/
│   └── vinted-scan.yml            # Cron de GitHub Actions (cada 5 min)
├── data/
│   ├── seen_items.json            # IDs vistos (se mantiene con cache)
│   └── session.json               # Sesión de Vinted
├── .env.example                   # Plantilla de configuración
└── .gitignore
```

---

## ⚙️ Personalizar

### Cambiar el precio máximo
Edita `MAX_PRICE` en `.github/workflows/vinted-scan.yml`:
```yaml
env:
  MAX_PRICE: '20.00'  # Cambia a tu precio máximo
```

### Cambiar la frecuencia de escaneo
Edita el cron en `.github/workflows/vinted-scan.yml`:
```yaml
schedule:
  - cron: '*/5 * * * *'   # Cada 5 minutos
  # - cron: '*/10 * * * *'  # Cada 10 minutos
  # - cron: '*/15 * * * *'  # Cada 15 minutos
```

### Añadir más búsquedas
Edita `SEARCH_QUERIES` en `vinted_monitor.py`:
```python
SEARCH_QUERIES = [
    {"search": "mando ps5", "title_keywords": ["ps5", "dualsense"]},
    # Añade más aquí...
]
```

---

## 📨 Ejemplo de mensaje

```
🎮 ¡NUEVO CHOLLO EN VINTED! 🎮
━━━━━━━━━━━━━━━━━━━
📌 Título: Mando DualSense PS5 - Drift
💰 Precio: 15.00 €
🏷️ Estado: Bueno
👤 Vendedor: juan_gamer (47 ⭐)
📝 Descripción: Mando PS5 con drift leve...
━━━━━━━━━━━━━━━━━━━
🔗 ABRIR EN VINTED

[ 🛒 Comprar en Vinted ]
```

---

## 📝 Licencia

MIT
