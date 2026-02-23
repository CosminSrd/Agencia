#!/usr/bin/env bash
set -euo pipefail

BASE_URL="http://127.0.0.1:8000"

if ! curl -s -f "$BASE_URL/health" >/dev/null; then
  echo "ERROR: Server not responding at $BASE_URL. Start the app and try again." >&2
  exit 1
fi

python3 -u - << 'PY'
import json
import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

search_payload = {
    "origen": "MAD",
    "destino": "LIS",
    "fecha": "2026-03-10",
    "adultos": 1,
    "ninos": 0,
    "bebes": 0,
    "clase": "economy",
}

try:
    resp = requests.post(f"{BASE_URL}/api/buscar-vuelos", json=search_payload, timeout=30)
    resp.raise_for_status()

    try:
        offers = resp.json()
    except Exception:
        print("ERROR: /api/buscar-vuelos did not return JSON", file=sys.stderr, flush=True)
        print(resp.text, file=sys.stderr, flush=True)
        raise

    print(f"Search results: {len(offers)}", flush=True)
    if offers:
        print("First offer source:", offers[0].get("source"), flush=True)

    amadeus = [o for o in offers if o.get("source") == "Amadeus" and o.get("amadeus_full_offer")]
    print(f"Amadeus offers with full offer: {len(amadeus)}", flush=True)

    if not amadeus:
        raise SystemExit("ERROR: No Amadeus offer with amadeus_full_offer found.")

    offer = amadeus[0]

    payload = {
        "offer_id": offer.get("id"),
        "datos_vuelo": {
            "origen": offer.get("origen"),
            "destino": offer.get("destino"),
            "aerolinea": offer.get("aerolinea"),
            "source": offer.get("source"),
            "fecha_ida": offer.get("fecha") or "2026-03-10",
            "segmentos": offer.get("segmentos"),
            "services": [],
        },
        "pasajeros": [{
            "tipo": "ADULT",
            "nombres": "Test",
            "apellidos": "User",
            "email": "test@example.com",
            "phone_number": "+34111111111",
        }],
        "amadeus_full_offer": offer.get("amadeus_full_offer"),
        "precio_total": offer.get("precio"),
        "email_cliente": "test@example.com",
        "telefono_cliente": "+34111111111",
    }

    resp2 = requests.post(f"{BASE_URL}/api/vuelos/crear-reserva", json=payload, timeout=30)
    print("Create reserva response:", resp2.status_code, flush=True)
    print(resp2.text, flush=True)
except SystemExit as exc:
    print(str(exc), file=sys.stderr, flush=True)
    raise
except Exception as exc:
    print(f"ERROR: {exc}", file=sys.stderr, flush=True)
    raise
PY
