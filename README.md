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

## 6. Ejecutar el bot localmente

```bash
python bot.py
```

La primera ejecución te va a abrir el navegador para autorizar Google
Calendar. Una vez autorizado, hablale al bot en Telegram.

## 7. Dejarlo corriendo 24/7 en la nube (Render, gratis)

Para que el bot funcione aunque tu PC esté apagada, está desplegado en
[Render](https://render.com) (plan gratuito, sin tarjeta):

1. Subí este repo a GitHub (privado está bien).
2. En Render: **New → Web Service** → conectá el repo.
3. Build command: `pip install -r requirements.txt`. Start command:
   `python bot.py`.
4. Plan: **Free** ($0/mes).
5. Variables de entorno: cargá las mismas de tu `.env` **menos**
   `RENDER_API_KEY`/`RENDER_SERVICE_ID` (esas son solo para tu PC), más
   `GOOGLE_TOKEN_JSON` con el contenido completo de
   `credentials/token.json` (una sola línea, pegalo tal cual) — Render no
   tiene navegador para hacer el login interactivo, así que usa este token
   ya generado en tu PC.

El plan Free de Render "duerme" el servicio a los 15 minutos sin tráfico, por
eso además hay un monitor gratuito en [UptimeRobot](https://uptimerobot.com)
pegándole a la URL pública del servicio (`https://TU-SERVICIO.onrender.com`,
que responde "OK") cada 5 minutos para mantenerlo despierto.

### El límite de 7 días de Google y cómo se resuelve

La app de Google Calendar quedó en estado **"Prueba"** (no se publicó a
producción porque eso exige un dominio propio con política de privacidad —
innecesario para un bot personal). En ese estado, Google hace expirar el
`refresh_token` a los 7 días sí o sí.

Para que esto no rompa el bot, `refresh_google_token.py` renueva el acceso
localmente (abre el navegador en tu PC, pide confirmar una vez) y sube el
token nuevo a Render automáticamente vía su API, disparando un redeploy.
Un script en la carpeta de Inicio de Windows (`check_token_refresh.vbs`,
copiado manualmente ahí, no versionado) lo corre en cada inicio de sesión;
el propio script decide si ya hace falta renovar (cada ~5 días) o no hace
nada. Necesita en tu `.env` local:

- `RENDER_API_KEY`: Render → Account Settings → API Keys.
- `RENDER_SERVICE_ID`: el `srv-xxxxx` de la URL del servicio en el dashboard.

Si alguna vez tu PC está apagada más de 5-7 días seguidos sin iniciar
sesión, el bot va a dejar de poder acceder al calendario hasta que corras
`python refresh_google_token.py --force` una vez.

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

- `bot.py` – handlers de Telegram, arranque del bot y servidor de salud
  (para que Render no lo duerma).
- `ai_agent.py` – lógica conversacional: historial por chat y function
  calling de Gemini para operar el calendario.
- `calendar_service.py` – wrapper de la API de Google Calendar (OAuth,
  listar/crear/editar/borrar eventos; soporta token vía archivo local o vía
  la variable `GOOGLE_TOKEN_JSON` para despliegues sin navegador).
- `config.py` – carga de variables de entorno.
- `refresh_google_token.py` – mantenimiento: renueva el acceso a Google
  Calendar y lo sube a Render (ver sección 7).
