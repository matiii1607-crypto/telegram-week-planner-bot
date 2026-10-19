"""Wrapper fino sobre la API de Google Calendar: autenticación OAuth y
operaciones CRUD de eventos usadas por el agente de IA."""

import datetime as dt
import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _load_credentials_from_env() -> Credentials | None:
    """En un servidor sin navegador (ej. Render) no se puede hacer el OAuth
    interactivo. Si GOOGLE_TOKEN_JSON está seteada (con el token ya
    autorizado antes, en una máquina con navegador), la usamos directamente
    y la refrescamos en memoria con el refresh_token; no hay filesystem
    persistente para guardarla de nuevo, así que no hace falta."""
    token_json = os.environ.get("GOOGLE_TOKEN_JSON")
    if not token_json:
        return None
    creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def _load_credentials() -> Credentials:
    env_creds = _load_credentials_from_env()
    if env_creds:
        return env_creds

    os.makedirs(config.CREDENTIALS_DIR, exist_ok=True)
    creds = None

    if os.path.exists(config.GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_FILE, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        if not os.path.exists(config.GOOGLE_CREDENTIALS_FILE):
            raise RuntimeError(
                "Falta credentials/credentials.json. Descargalo desde Google Cloud "
                "Console (OAuth client ID de tipo 'Desktop app') y colocalo ahí. "
                "Mirá el README para el paso a paso."
            )
        flow = InstalledAppFlow.from_client_secrets_file(config.GOOGLE_CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)

    with open(config.GOOGLE_TOKEN_FILE, "w") as token_file:
        token_file.write(creds.to_json())

    return creds


_service = None


def get_service():
    global _service
    if _service is None:
        creds = _load_credentials()
        _service = build("calendar", "v3", credentials=creds)
    return _service


def _to_rfc3339(value: str) -> str:
    """Acepta 'YYYY-MM-DDTHH:MM:SS' (sin zona) y le aplica la zona horaria
    configurada, o devuelve el valor tal cual si ya trae zona/offset."""
    if value.endswith("Z") or "+" in value[10:]:
        return value
    naive = dt.datetime.fromisoformat(value)
    if naive.tzinfo is None:
        naive = naive.replace(tzinfo=config.TIMEZONE)
    return naive.isoformat()


def list_events(time_min: str, time_max: str) -> list[dict]:
    service = get_service()
    result = (
        service.events()
        .list(
            calendarId=config.GOOGLE_CALENDAR_ID,
            timeMin=_to_rfc3339(time_min),
            timeMax=_to_rfc3339(time_max),
            singleEvents=True,
            orderBy="startTime",
            timeZone=config.TIMEZONE_NAME,
        )
        .execute()
    )
    events = []
    for item in result.get("items", []):
        start = item["start"].get("dateTime", item["start"].get("date"))
        end = item["end"].get("dateTime", item["end"].get("date"))
        events.append(
            {
                "id": item["id"],
                "summary": item.get("summary", "(sin título)"),
                "start": start,
                "end": end,
                "description": item.get("description", ""),
                "location": item.get("location", ""),
            }
        )
    return events


def create_event(
    summary: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
) -> dict:
    service = get_service()
    body = {
        "summary": summary,
        "description": description,
        "location": location,
        "start": {"dateTime": _to_rfc3339(start), "timeZone": config.TIMEZONE_NAME},
        "end": {"dateTime": _to_rfc3339(end), "timeZone": config.TIMEZONE_NAME},
    }
    created = service.events().insert(calendarId=config.GOOGLE_CALENDAR_ID, body=body).execute()
    return {"id": created["id"], "summary": created.get("summary"), "htmlLink": created.get("htmlLink")}


def update_event(
    event_id: str,
    summary: str | None = None,
    start: str | None = None,
    end: str | None = None,
    description: str | None = None,
    location: str | None = None,
) -> dict:
    service = get_service()
    event = service.events().get(calendarId=config.GOOGLE_CALENDAR_ID, eventId=event_id).execute()

    if summary is not None:
        event["summary"] = summary
    if description is not None:
        event["description"] = description
    if location is not None:
        event["location"] = location
    if start is not None:
        event["start"] = {"dateTime": _to_rfc3339(start), "timeZone": config.TIMEZONE_NAME}
    if end is not None:
        event["end"] = {"dateTime": _to_rfc3339(end), "timeZone": config.TIMEZONE_NAME}

    updated = (
        service.events()
        .update(calendarId=config.GOOGLE_CALENDAR_ID, eventId=event_id, body=event)
        .execute()
    )
    return {"id": updated["id"], "summary": updated.get("summary")}


def delete_event(event_id: str) -> dict:
    service = get_service()
    service.events().delete(calendarId=config.GOOGLE_CALENDAR_ID, eventId=event_id).execute()
    return {"id": event_id, "deleted": True}
