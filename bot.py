"""Punto de entrada del bot de Telegram."""

import asyncio
import http.server
import logging
import os
import threading

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import ai_agent
import config

if os.environ.get("RENDER") == "true":
    # En Render los logs se ven por stdout en su dashboard.
    _log_handlers = [logging.StreamHandler()]
else:
    # Si se ejecuta con pythonw (sin consola, p. ej. como tarea programada al
    # iniciar sesión) sys.stdout/stderr son None, así que logueamos a un
    # archivo en vez de a la consola.
    _log_handlers = [logging.FileHandler(os.path.join(config.BASE_DIR, "bot.log"), encoding="utf-8")]

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
    handlers=_log_handlers,
)
logger = logging.getLogger(__name__)


def _start_health_server() -> None:
    """Render exige un 'web service' que escuche en $PORT; si no, lo mata.
    El bot no necesita servir nada, así que esto solo responde 200 OK para
    que Render (y un ping externo tipo UptimeRobot) lo vean vivo."""
    port = os.environ.get("PORT")
    if not port:
        return

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - nombre fijado por BaseHTTPRequestHandler
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, format: str, *args) -> None:  # noqa: A002, N802
            pass  # no ensuciar el log del bot con cada ping de salud

    server = http.server.ThreadingHTTPServer(("0.0.0.0", int(port)), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info("Servidor de salud escuchando en el puerto %s", port)


def _is_allowed(update: Update) -> bool:
    if config.ALLOWED_TELEGRAM_USER_ID is None:
        return True
    return update.effective_user is not None and update.effective_user.id == config.ALLOWED_TELEGRAM_USER_ID


async def _reject(update: Update) -> None:
    await update.message.reply_text("Este bot es privado, no tengo autorización para responderte.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        await _reject(update)
        return
    ai_agent.reset_conversation(update.effective_chat.id)
    await update.message.reply_text(
        "¡Hola! Soy tu asistente para organizar la semana. Contame qué tenés que "
        "hacer, pedime un resumen de tu semana, o decime que armes un plan.\n\n"
        "Comandos: /semana (resumen y sugerencias), /reset (olvidar la conversación)."
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        await _reject(update)
        return
    ai_agent.reset_conversation(update.effective_chat.id)
    await update.message.reply_text("Listo, empezamos de cero.")


async def semana(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        await _reject(update)
        return
    await _respond(update, context, "Dame un resumen de mi semana (próximos 7 días) y sugerencias para organizarla mejor.")


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        await _reject(update)
        return
    await _respond(update, context, update.message.text)


async def _keep_typing(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    # El indicador de "escribiendo..." de Telegram expira a los pocos segundos;
    # lo refrescamos mientras el pedido (IA + calendario) sigue en curso.
    try:
        while True:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        pass


async def _respond(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    chat_id = update.effective_chat.id
    typing_task = asyncio.create_task(_keep_typing(context, chat_id))
    try:
        reply = await asyncio.to_thread(ai_agent.handle_message, chat_id, text)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error procesando mensaje")
        reply = f"Tuve un error procesando eso: {exc}"
    finally:
        typing_task.cancel()
    await update.message.reply_text(reply)


def main() -> None:
    _start_health_server()

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("semana", semana))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    logger.info("Bot iniciado, esperando mensajes...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
