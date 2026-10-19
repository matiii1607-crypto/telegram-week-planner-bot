"""Agente conversacional: mantiene historial por chat y usa function calling
de Gemini para operar sobre Google Calendar."""

import datetime as dt

from google import genai
from google.genai import types

import calendar_service
import config

client = genai.Client(api_key=config.GEMINI_API_KEY)

MAX_HISTORY_TURNS = 30

# Historial de conversación en memoria, por chat_id de Telegram.
# Cada entrada es un types.Content (role "user" o "model").
_conversations: dict[int, list[types.Content]] = {}

_FUNCTION_DECLARATIONS = [
    types.FunctionDeclaration(
        name="list_events",
        description=(
            "Lista los eventos del calendario entre dos fechas/horas. Usala para "
            "ver qué hay planeado en un día, una semana o un rango antes de "
            "proponer cambios o detectar huecos libres."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "time_min": types.Schema(
                    type=types.Type.STRING,
                    description="Inicio del rango, ISO 8601 (YYYY-MM-DDTHH:MM:SS).",
                ),
                "time_max": types.Schema(
                    type=types.Type.STRING,
                    description="Fin del rango, ISO 8601 (YYYY-MM-DDTHH:MM:SS).",
                ),
            },
            required=["time_min", "time_max"],
        ),
    ),
    types.FunctionDeclaration(
        name="create_event",
        description="Crea un evento nuevo en el calendario.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "summary": types.Schema(type=types.Type.STRING, description="Título del evento."),
                "start": types.Schema(type=types.Type.STRING, description="Inicio, ISO 8601."),
                "end": types.Schema(type=types.Type.STRING, description="Fin, ISO 8601."),
                "description": types.Schema(type=types.Type.STRING, description="Notas opcionales."),
                "location": types.Schema(type=types.Type.STRING, description="Ubicación opcional."),
            },
            required=["summary", "start", "end"],
        ),
    ),
    types.FunctionDeclaration(
        name="update_event",
        description="Modifica un evento existente (horario, título, descripción o ubicación).",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "event_id": types.Schema(type=types.Type.STRING, description="ID del evento."),
                "summary": types.Schema(type=types.Type.STRING),
                "start": types.Schema(type=types.Type.STRING, description="ISO 8601."),
                "end": types.Schema(type=types.Type.STRING, description="ISO 8601."),
                "description": types.Schema(type=types.Type.STRING),
                "location": types.Schema(type=types.Type.STRING),
            },
            required=["event_id"],
        ),
    ),
    types.FunctionDeclaration(
        name="delete_event",
        description="Elimina un evento del calendario.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "event_id": types.Schema(type=types.Type.STRING, description="ID del evento a eliminar."),
            },
            required=["event_id"],
        ),
    ),
]

_TOOLS = types.Tool(function_declarations=_FUNCTION_DECLARATIONS)

_TOOL_IMPL = {
    "list_events": lambda time_min, time_max: calendar_service.list_events(time_min, time_max),
    "create_event": lambda **kw: calendar_service.create_event(**kw),
    "update_event": lambda **kw: calendar_service.update_event(**kw),
    "delete_event": lambda event_id: calendar_service.delete_event(event_id),
}


def _system_prompt() -> str:
    now = dt.datetime.now(config.TIMEZONE)
    dia_semana = now.strftime("%A")
    return f"""Eres un asistente personal en español que ayuda al usuario a organizar su
semana usando su Google Calendar real a través de las herramientas disponibles.

Fecha y hora actuales: {now.strftime('%Y-%m-%d %H:%M')} ({dia_semana}), zona horaria {config.TIMEZONE_NAME}.

Pautas:
- Antes de crear, mover o borrar un evento, si no tenés el event_id a mano,
  usá list_events para encontrarlo primero.
- Cuando el usuario pida "organizar la semana" o algo similar, consultá los
  próximos 7 días con list_events, identificá huecos libres razonables y
  proponé un plan concreto (días y horarios) antes de crear eventos.
- Confirmá con una pregunta corta solo cuando la intención del usuario sea
  ambigua (por ejemplo, no especificó duración o día). Si fue claro, actuá
  directamente y después contá qué hiciste.
- Sé breve, concreto y amigable. Usá horarios en formato 24hs.
- Nunca inventes eventos: si no estás seguro de algo del calendario, consultalo
  con list_events en vez de asumir.
"""


def _get_history(chat_id: int) -> list[types.Content]:
    return _conversations.setdefault(chat_id, [])


def _trim_history(chat_id: int) -> None:
    history = _conversations[chat_id]
    if len(history) > MAX_HISTORY_TURNS:
        _conversations[chat_id] = history[-MAX_HISTORY_TURNS:]


def reset_conversation(chat_id: int) -> None:
    _conversations[chat_id] = []


def handle_message(chat_id: int, user_text: str) -> str:
    history = _get_history(chat_id)
    history.append(types.Content(role="user", parts=[types.Part(text=user_text)]))

    gen_config = types.GenerateContentConfig(
        system_instruction=_system_prompt(),
        tools=[_TOOLS],
    )

    final_text_parts: list[str] = []

    for _ in range(8):  # límite de vueltas de function-calling por mensaje
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=history,
            config=gen_config,
        )

        candidate = response.candidates[0]
        history.append(candidate.content)

        function_calls = [p.function_call for p in candidate.content.parts if p.function_call]
        text_parts = [p.text for p in candidate.content.parts if p.text]
        final_text_parts.extend(text_parts)

        if not function_calls:
            break

        response_parts = []
        for call in function_calls:
            try:
                result = _TOOL_IMPL[call.name](**call.args)
                response_payload = {"result": result}
            except Exception as exc:  # noqa: BLE001 - se reporta al modelo, no se oculta
                response_payload = {"error": str(exc)}

            response_parts.append(
                types.Part.from_function_response(name=call.name, response=response_payload)
            )

        history.append(types.Content(role="user", parts=response_parts))
    else:
        final_text_parts.append(
            "Me tomó muchas vueltas resolver esto, ¿podés reformular el pedido?"
        )

    _trim_history(chat_id)
    return "\n".join(part for part in final_text_parts if part).strip() or "Listo."
