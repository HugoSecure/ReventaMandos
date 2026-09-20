# VintedMandos Bot 🎮

Bot de Python que monitoriza **Vinted** en busca de chollos de mandos de videoconsola (PS5, PS4, Switch, Xbox) y envía alertas instantáneas a **Telegram**. Ejecútalo 24/7 en la nube sin necesidad de tener el ordenador encendido.

---

## 📋 Características

- ✅ Búsqueda en 5 categorías de mandos simultáneamente
- ✅ Filtro por precio máximo configurable (default: 23€)
- ✅ Filtrado por palabras clave en título y descripción
- ✅ Mensajes formateados con botón inline "Comprar en Vinted"
- ✅ Sistema anti-duplicados (archivo JSON persistente)
- ✅ Rotación de User-Agents para evitar bloqueos
- ✅ Intervalos aleatorios entre escaneos (30-60s)
- ✅ Gestión automática de cookies y tokens CSRF de Vinted
- ✅ Reconexión automática si la sesión expira
- ✅ Mini servidor HTTP para mantener vivo el servicio en la nube
- ✅ Despliegue en Render, Railway, Fly.io, Docker, etc.

---

## 🚀 Instalación local (para pruebas)

### 1. Clonar el proyecto

```bash
git clone https://github.com/TU_USUARIO/ReventaMandos.git
cd ReventaMandos
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con tu token de Telegram y chat ID (ver sección de Telegram más abajo).

### 4. Ejecutar

```bash
python vinted_monitor.py
```

---

## 🤖 Configurar el Bot de Telegram

### Paso 1: Crear el Bot con BotFather

1. Abre Telegram y busca **@BotFather**.
2. Envía el comando `/newbot`.
3. Elige un nombre para tu bot, por ejemplo: `VintedMandos Bot`.
4. Elige un username único, por ejemplo: `VintedMandosBot`.
5. BotFather te dará un **token** como este:
   ```
   123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
6. Copia ese token y pégalo en `.env` como `TELEGRAM_BOT_TOKEN`.

### Paso 2: Obtener tu Chat ID

**Opción A — Chat privado (recomendado):**

1. Busca tu bot en Telegram por su username (ej: @VintedMandosBot).
2. Envíale un mensaje (puede ser `/start`).
3. Abre esta URL en tu navegador (reemplaza `<TU_TOKEN>`):
   ```
   https://api.telegram.org/bot<TU_TOKEN>/getUpdates
   ```
4. Busca el campo `"chat": {"id": 123456789}` en la respuesta JSON.
5. Ese número es tu `TELEGRAM_CHAT_ID`.

**Opción B — Canal o grupo:**

1. Crea un canal/grupo en Telegram.
2. Añade tu bot como administrador.
3. Envía un mensaje al canal/grupo.
4. Usa la URL `getUpdates` para obtener el chat ID del canal (empieza con `-100`).

### Paso 3: Guardar en `.env`

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

---

## ☁️ Despliegue en la nube 24/7

### Opción 1: Render (Recomendada — Gratis)

Render es la opción más sencilla. El bot se ejecuta como Background Worker 24/7.

**Pasos:**

1. **Sube el proyecto a GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/TU_USUARIO/ReventaMandos.git
   git push -u origin main
   ```

2. **Crea cuenta en [render.com](https://render.com)** (gratis con GitHub).

3. **Crea un nuevo Background Worker:**
   - Haz clic en **"New +"** → **"Background Worker"**
   - Conecta tu repositorio de GitHub
   - Configura:
     - **Name:** `vinted-mandos-bot`
     - **Runtime:** Python
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `python vinted_monitor.py`
     - **Plan:** Free

4. **Añade las variables de entorno** en la pestaña **Environment**:
   | Key | Value |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | Tu token de BotFather |
   | `TELEGRAM_CHAT_ID` | Tu chat ID |
   | `MAX_PRICE` | `23.00` |
   | `MIN_INTERVAL` | `30` |
   | `MAX_INTERVAL` | `60` |

5. **Clic en "Create Background Worker"** → ¡Listo!

**⚠️ Nota sobre Render Free:**
Render apaga los workers free tras 15 min de inactividad HTTP. Para evitarlo, configura un keep-alive:

1. Crea una cuenta en [UptimeRobot](https://uptimerobot.com/) (gratis).
2. Añade un monitor HTTP con la URL de tu servicio Render:
   ```
   https://vinted-mandos-bot.onrender.com
   ```
3. Configura el intervalo a **5 minutos**.
4. UptimeRobot hará ping cada 5 min, manteniendo el servicio vivo.

---

### Opción 2: Railway (Gratis con $5 de crédito mensual)

1. Crea cuenta en [railway.app](https://railway.app) con GitHub.
2. Haz clic en **"New Project"** → **"Deploy from GitHub repo"**.
3. Selecciona tu repositorio.
4. Railway detectará automáticamente el `Procfile`.
5. Ve a la pestaña **Variables** y añade:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `MAX_PRICE=23.00`
6. Railway desplegará automáticamente. No necesita keep-alive.

---

### Opción 3: Fly.io (Gratis con límites generosos)

1. Instala la CLI de Fly:
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```
2. Inicia sesión:
   ```bash
   fly auth login
   ```
3. En el directorio del proyecto:
   ```bash
   fly launch
   ```
4. Selecciona **"No"** para crear una app.
5. Edita `fly.toml` generado o usa el `Dockerfile` incluido.
6. Configura los secretos:
   ```bash
   fly secrets set TELEGRAM_BOT_TOKEN="tu_token" TELEGRAM_CHAT_ID="tu_chat_id" MAX_PRICE=23.00
   ```
7. Despliega:
   ```bash
   fly deploy
   ```

---

### Opción 4: Docker (cualquier servidor)

Si tienes un VPS o servidor propio:

```bash
# Clonar el proyecto
git clone https://github.com/TU_USUARIO/ReventaMandos.git
cd ReventaMandos

# Crear archivo .env
cp .env.example .env
# Editar .env con tus tokens

# Ejecutar con Docker Compose
docker-compose up -d

# Ver logs
docker-compose logs -f

# Detener
docker-compose down
```

---

### Opción 5: PythonAnywhere (Gratis)

1. Crea cuenta en [pythonanywhere.com](https://www.pythonanywhere.com).
2. Sube los archivos del proyecto.
3. Abre una consola Bash:
   ```bash
   pip install --user -r requirements.txt
   ```
4. Ve a la pestaña **Tasks** y crea una tarea programada:
   - **Command:** `cd /home/TU_USUARIO/ReventaMandos && /home/TU_USUARIO/.local/bin/python vinted_monitor.py`
5. Configura las variables de entorno en el script o en un archivo `.env`.

---

## 📁 Estructura del proyecto

```
ReventaMandos/
├── vinted_monitor.py    # Script principal del bot
├── requirements.txt     # Dependencias de Python
├── .env.example         # Plantilla de variables de entorno
├── .env                 # Tus variables reales (NO subir a Git)
├── .gitignore           # Archivos excluidos de Git
├── Procfile             # Para Heroku/Render
├── Dockerfile           # Para despliegue con Docker
├── docker-compose.yml   # Para ejecutar con Docker Compose
├── render.yaml          # Configuración automática para Render
├── seen_items.json      # Base de datos de IDs vistos (se genera)
├── bot.log              # Registro de actividad
└── README.md            # Este archivo
```

---

## 🔧 Configuración avanzada

### Variables de entorno

| Variable | Descripción | Default |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram | *Obligatorio* |
| `TELEGRAM_CHAT_ID` | Chat/canal donde enviar alertas | *Obligatorio* |
| `MAX_PRICE` | Precio máximo en euros | `23.00` |
| `MIN_INTERVAL` | Segundos mínimos entre escaneos | `30` |
| `MAX_INTERVAL` | Segundos máximos entre escaneos | `60` |
| `PORT` | Puerto del servidor HTTP de salud | `8080` |

### Personalizar búsquedas

Edita la lista `SEARCH_QUERIES` en `vinted_monitor.py`:

```python
SEARCH_QUERIES = [
    {"search": "mando ps5 dualsense", "title_keywords": ["ps5", "dualsense"]},
    {"search": "mando ps4 dualshock", "title_keywords": ["ps4", "dualshock"]},
    # Añade más búsquedas aquí...
]
```

---

## 🔧 Solución de problemas

| Problema | Solución |
|---|---|
| **Error 403 Forbidden** | El bot rota UA y reconecta automáticamente. Si persiste, espera 5-10 min. |
| **"No items found"** | Vinted puede estar en mantenimiento. Comprueba que `vinted.es` funciona. |
| **Mensajes no llegan** | Verifica token y chat ID. Envía `/start` al bot. |
| **Render se duerme** | Configura UptimeRobot con ping cada 5 min al endpoint `/`. |
| **Railway se agota** | El plan free tiene $5/mes. Monitorea el uso en el dashboard. |

### Endpoint de salud

El bot expone un endpoint HTTP en el puerto configurado (default 8080). Útil para:
- Keep-alive con UptimeRobot
- Monitorización con herramientas externas
- Verificar que el bot está activo

```
GET http://localhost:8080/
```

Respuesta:
```json
{
  "status": "ok",
  "service": "VintedMandos Bot",
  "uptime": 3600.5,
  "scan_count": 42,
  "seen_items": 150,
  "timestamp": "2025-01-15T10:30:00+00:00"
}
```

---

## 📝 Ejemplo de mensaje en Telegram

```
🎮 ¡NUEVO CHOLLO EN VINTED! 🎮
━━━━━━━━━━━━━━━━━━━
📌 Título: Mando DualSense PS5 - Drift
💰 Precio: 15.00 €
🏷️ Estado: Bueno
👤 Vendedor: juan_gamer (47 ⭐)
📝 Descripción: Mando PS5 con drift leve, funciona bien excepto joystick izquierdo...
━━━━━━━━━━━━━━━━━━━
🔗 ABRIR EN VINTED

[ 🛒 Comprar en Vinted ]  ← botón inline
```

---

## 📝 Licencia

MIT — Usa libremente este proyecto.
