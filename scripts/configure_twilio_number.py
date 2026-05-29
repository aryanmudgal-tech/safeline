from __future__ import annotations

import argparse
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"


def discover_ngrok_public_url() -> str:
    response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=5)
    response.raise_for_status()
    tunnels = response.json().get("tunnels", [])
    https_tunnels = [
        tunnel["public_url"]
        for tunnel in tunnels
        if tunnel.get("public_url", "").startswith("https://")
    ]
    if not https_tunnels:
        raise RuntimeError("No HTTPS ngrok tunnel found on http://127.0.0.1:4040.")
    return https_tunnels[0]


def upsert_env_value(key: str, value: str) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    updated = False
    for index, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[index] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def configure_number(public_url: str, write_env: bool) -> None:
    try:
        from twilio.rest import Client
    except ImportError as exc:
        raise RuntimeError("Install the twilio package before running this script.") from exc

    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    phone_number = os.environ["TWILIO_PHONE_NUMBER"]

    client = Client(account_sid, auth_token)
    matches = client.incoming_phone_numbers.list(phone_number=phone_number, limit=1)
    if not matches:
        raise RuntimeError(f"No Twilio incoming phone number found for {phone_number}.")

    number = matches[0]
    voice_url = f"{public_url.rstrip('/')}/twilio/voice"
    call_status_url = f"{public_url.rstrip('/')}/twilio/call-status"
    ws_url = public_url.rstrip("/").replace("https://", "wss://") + "/ws/twilio"

    number.update(
        voice_url=voice_url,
        voice_method="POST",
        status_callback=call_status_url,
        status_callback_method="POST",
    )

    if write_env:
        upsert_env_value("APP_BASE_URL", public_url.rstrip("/"))
        upsert_env_value("TWILIO_PUBLIC_WS_URL", ws_url)

    print(f"Configured {phone_number}")
    print(f"Voice webhook: {voice_url}")
    print(f"Call status webhook: {call_status_url}")
    print(f"Media WebSocket: {ws_url}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure Safeline Phase 1 Twilio webhooks.")
    parser.add_argument("--public-url", help="Public HTTPS base URL, for example an ngrok URL.")
    parser.add_argument("--no-write-env", action="store_true", help="Do not update .env with public URLs.")
    args = parser.parse_args()

    load_dotenv(ENV_PATH)
    public_url = args.public_url or discover_ngrok_public_url()
    configure_number(public_url=public_url, write_env=not args.no_write_env)


if __name__ == "__main__":
    main()
