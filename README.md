# Bot de Telegram para organizar tu semana

Bot personal de Telegram que usa Gemini (Google AI, capa gratuita) para
entender lo que le pedís en lenguaje natural y organiza tu semana leyendo y
editando tu Google Calendar real.

## Qué puede hacer

- "¿Qué tengo esta semana?" → lee tu calendario y te hace un resumen.
- "Agendame el dentista el jueves a las 10" → crea el evento.
- "Movéme la reunión del lunes a las 16hs" → busca el evento y lo actualiza.
- "Organizame la semana" (o el comando `/semana`) → revisa los próximos 7
  días, detecta huecos libres y te propone un plan.
- `/reset` → olvida la conversación y arranca de cero.

## 1. Requisitos

- Python 3.10 o superior.
- Una cuenta de Telegram.
- Una API key gratuita de Google AI Studio (https://aistudio.google.com/apikey).
- Una cuenta de Google con Google Calendar.

## 2. Instalar dependencias

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Crear el bot de Telegram

1. Abrí Telegram y hablá con [@BotFather](https://t.me/BotFather).
2. Enviale `/newbot` y seguí las instrucciones (nombre y username).
3. Te va a dar un **token**. Copialo.
4. Hablá con [@userinfobot](https://t.me/userinfobot) para obtener tu **ID de
   usuario numérico** (necesario para que el bot solo te responda a vos).

## 4. Habilitar Google Calendar API

1. Entrá a [Google Cloud Console](https://console.cloud.google.com/).
2. Creá un proyecto nuevo (o usá uno existente).
3. Ve a **APIs & Services → Library**, buscá "Google Calendar API" y
   habilitala.
4. Ve a **APIs & Services → OAuth consent screen**:
   - Tipo de usuario: **External** (si no tenés Google Workspace).
   - Completá los campos obligatorios (nombre de la app, email).
   - En "Test users" agregá tu propia cuenta de Gmail.
5. Ve a **APIs & Services → Credentials → Create Credentials → OAuth client
   ID**:
   - Tipo de aplicación: **Desktop app**.
   - Descargá el JSON generado.
6. Creá la carpeta `credentials/` dentro de este proyecto (si no existe) y
   guardá ese archivo como `credentials/credentials.json`.

La primera vez que el bot necesite tu calendario, va a abrir una ventana del
navegador para que inicies sesión con Google y autorices el acceso. Después
de eso, guarda un `credentials/token.json` y no vuelve a pedirlo (se
refresca solo).

## 5. Configurar variables de entorno

```bash
copy .env.example .env
```

Completá `.env` con:

- `TELEGRAM_BOT_TOKEN`: el token de BotFather.
- `GEMINI_API_KEY`: tu API key gratuita de Google AI Studio.
- `ALLOWED_TELEGRAM_USER_ID`: tu ID numérico (recomendado, así nadie más
  puede usar el bot ni ver tu calendario).
- `TIMEZONE`: tu zona horaria IANA (ej. `America/Argentina/Buenos_Aires`).
- `GOOGLE_CALENDAR_ID`: dejalo en `primary` salvo que quieras usar otro
  calendario específico.

## 6. Ejecutar el bot

```bash
python bot.py
```

La primera ejecución te va a abrir el navegador para autorizar Google
Calendar. Una vez autorizado, hablale al bot en Telegram.

## Notas de seguridad

- El bot tiene permiso de **lectura y escritura** sobre tu calendario.
  Configurá siempre `ALLOWED_TELEGRAM_USER_ID` para que solo vos puedas
  usarlo.
- `credentials/credentials.json`, `credentials/token.json` y `.env` quedan
  excluidos del control de versiones (`.gitignore`) porque contienen
  secretos: no los subas a ningún repositorio público.
- La conversación se guarda solo en memoria (se pierde si reiniciás el
  bot); no hay base de datos.

## Estructura del proyecto

- `bot.py` – handlers de Telegram y arranque del bot.
- `ai_agent.py` – lógica conversacional: historial por chat y function
  calling de Gemini para operar el calendario.
- `calendar_service.py` – wrapper de la API de Google Calendar (OAuth,
  listar/crear/editar/borrar eventos).
- `config.py` – carga de variables de entorno.
