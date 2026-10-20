"""Renueva el acceso a Google Calendar y lo sube a Render.

Por qué existe: la app de Google está en modo "Prueba" (no pasó el proceso
de verificación de Google, innecesario para un bot personal), y en ese modo
Google hace expirar el refresh_token a los 7 días pase lo que pase. Este
script vuelve a autorizar (abre el navegador), guarda el token nuevo local y
lo sube a las variables de entorno del servicio en Render vía su API,
disparando un redeploy para que tome efecto.

Se ejecuta solo: ver check_token_refresh.vbs en la carpeta de Inicio de
Windows, que lo corre en cada inicio de sesión y este script decide si
realmente hace falta renovar (según REFRESH_EVERY_DAYS).

Uso manual: python refresh_google_token.py [--force]
"""

import datetime as dt
import os
import sys

import requests
from google_auth_oauthlib.flow import InstalledAppFlow

import config

SCOPES = ["https://www.googleapis.com/auth/calendar"]
MARKER_FILE = os.path.join(config.CREDENTIALS_DIR, ".last_refresh")
REFRESH_EVERY_DAYS = 5  # margen cómodo bajo el límite real de 7 días

RENDER_API_KEY = os.environ.get("RENDER_API_KEY")
RENDER_SERVICE_ID = os.environ.get("RENDER_SERVICE_ID")


def _is_due() -> bool:
    if not os.path.exists(MARKER_FILE):
        return True
    with open(MARKER_FILE, encoding="utf-8") as f:
        last = dt.datetime.fromisoformat(f.read().strip())
    return (dt.datetime.now() - last) >= dt.timedelta(days=REFRESH_EVERY_DAYS)


def _mark_done() -> None:
    with open(MARKER_FILE, "w", encoding="utf-8") as f:
        f.write(dt.datetime.now().isoformat())


def _get_fresh_credentials() -> str:
    flow = InstalledAppFlow.from_client_secrets_file(config.GOOGLE_CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    token_json = creds.to_json()
    with open(config.GOOGLE_TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(token_json)
    return token_json


def _update_render(token_json: str) -> None:
    if not RENDER_API_KEY or not RENDER_SERVICE_ID:
        print(
            "RENDER_API_KEY / RENDER_SERVICE_ID no están en .env: "
            "solo se actualizó el token local, no el de Render."
        )
        return

    headers = {"Authorization": f"Bearer {RENDER_API_KEY}", "Content-Type": "application/json"}
    base = f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}"

    # El endpoint reemplaza TODAS las env vars del servicio, así que primero
    # traemos las actuales para no perder ninguna.
    resp = requests.get(f"{base}/env-vars", headers=headers, params={"limit": 100})
    resp.raise_for_status()
    current = {item["envVar"]["key"]: item["envVar"]["value"] for item in resp.json()}
    current["GOOGLE_TOKEN_JSON"] = token_json

    resp = requests.put(
        f"{base}/env-vars",
        headers=headers,
        json=[{"key": k, "value": v} for k, v in current.items()],
    )
    resp.raise_for_status()

    resp = requests.post(f"{base}/deploys", headers=headers, json={})
    resp.raise_for_status()
    print("Render actualizado, redeploy en curso.")


def main(force: bool = False) -> None:
    if not force and not _is_due():
        print("Todavía no hace falta renovar.")
        return

    print("Renovando el acceso a Google Calendar (se abre el navegador)...")
    token_json = _get_fresh_credentials()
    _update_render(token_json)
    _mark_done()
    print("Listo.")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
