#!/usr/bin/env python
"""Coleta diária de tarifas via SerpApi (Google Flights) para o Radar de Passagens.

Lê monitors.json, consulta uma vez por monitor, grava:
  prices.json            -> último resultado consolidado (o que o radar lê)
  history/YYYY-MM-DD.json-> cópia do dia
  raw/<id>.json          -> resposta bruta mais recente (para depuração)
  serpapi_account.json   -> saldo da conta SerpApi (compartilhada com outros projetos, ex.: efake2)
A chave vem da variável de ambiente SERPAPI_KEY (GitHub Actions secret). Nunca no repositório.
"""
import datetime as dt
import json
import os
import sys
import time

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
API = "https://serpapi.com/search.json"
CLASS_NAMES = {1: "econômica", 2: "premium economy", 3: "executiva", 4: "primeira"}


def load_monitors():
    with open(os.path.join(ROOT, "monitors.json"), encoding="utf-8") as f:
        return json.load(f)


def query(monitor, cfg, key):
    params = {
        "engine": "google_flights",
        "api_key": key,
        "departure_id": monitor["departure_id"],
        "arrival_id": monitor["arrival_id"],
        "outbound_date": monitor["outbound_date"],
        "type": monitor.get("type", 1),
        "travel_class": monitor.get("travel_class", 1),
        "adults": monitor.get("adults", 1),
        "stops": monitor.get("stops", 0),
        "currency": cfg.get("currency", "EUR"),
        "hl": "en",
        "gl": "br",
        "deep_search": "true",
    }
    if monitor.get("type", 1) == 1 and monitor.get("return_date"):
        params["return_date"] = monitor["return_date"]
    excl = monitor.get("exclude_airlines", cfg.get("exclude_airlines_default"))
    if excl:
        params["exclude_airlines"] = excl
    r = requests.get(API, params=params, timeout=90)
    r.raise_for_status()
    return r.json()


def summarize_option(opt):
    legs = opt.get("flights") or []
    if not legs:
        return None
    airlines = sorted({l.get("airline", "?") for l in legs})
    return {
        "price": opt.get("price"),
        "airline": " + ".join(airlines),
        "flight_numbers": [l.get("flight_number") for l in legs],
        "depart": legs[0].get("departure_airport", {}).get("time"),
        "arrive": legs[-1].get("arrival_airport", {}).get("time"),
        "from": legs[0].get("departure_airport", {}).get("id"),
        "to": legs[-1].get("arrival_airport", {}).get("id"),
        "stops": len(opt.get("layovers") or []),
        "duration_min": opt.get("total_duration"),
        "travel_class": legs[0].get("travel_class"),
    }


def summarize(monitor, data):
    options = []
    for bucket in ("best_flights", "other_flights"):
        for opt in data.get(bucket) or []:
            s = summarize_option(opt)
            if s and isinstance(s.get("price"), (int, float)):
                options.append(s)
    options.sort(key=lambda o: o["price"])
    # melhor preço por companhia (para a coluna "alternativa")
    by_airline = {}
    for o in options:
        by_airline.setdefault(o["airline"], o)
    pi = data.get("price_insights") or {}
    return {
        "id": monitor["id"],
        "route": monitor["route"],
        "query": {k: monitor.get(k) for k in ("departure_id", "arrival_id", "outbound_date", "return_date", "type", "travel_class", "stops")},
        "cabin": CLASS_NAMES.get(monitor.get("travel_class", 1)),
        "cheapest": options[0] if options else None,
        "by_airline": list(by_airline.values())[:5],
        "options_count": len(options),
        "price_insights": {
            "lowest_price": pi.get("lowest_price"),
            "price_level": pi.get("price_level"),
            "typical_price_range": pi.get("typical_price_range"),
        } if pi else None,
        "error": None if options else (data.get("error") or "sem resultados"),
    }


ACCOUNT_API = "https://serpapi.com/account.json"
ACCOUNT_FIELDS = ("plan_name", "searches_per_month", "plan_searches_left", "extra_credits",
                  "total_searches_left", "this_month_usage", "plan_renewal_date",
                  "account_rate_limit_per_hour", "this_hour_searches")


def fetch_account(key):
    """Saldo da conta SerpApi (não conta como busca). Nunca grava api_key/e-mail/id."""
    try:
        r = requests.get(ACCOUNT_API, params={"api_key": key}, timeout=30)
        r.raise_for_status()
        d = r.json()
        acc = {k: d.get(k) for k in ACCOUNT_FIELDS}
        acc["checked_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        acc["error"] = None
        return acc
    except Exception as e:  # noqa: BLE001
        return {"checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "error": f"{type(e).__name__}: {e}"}


def main():
    key = os.environ.get("SERPAPI_KEY")
    if not key:
        print("SERPAPI_KEY ausente", file=sys.stderr)
        sys.exit(2)
    cfg = load_monitors()
    today = dt.date.today()
    out = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "currency": cfg.get("currency", "EUR"), "monitors": []}
    os.makedirs(os.path.join(ROOT, "raw"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "history"), exist_ok=True)
    for m in cfg["monitors"]:
        if m.get("outbound_date") and dt.date.fromisoformat(m["outbound_date"]) < today:
            out["monitors"].append({"id": m["id"], "route": m["route"], "cheapest": None, "error": "data de ida já passou"})
            continue
        try:
            data = query(m, cfg, key)
            with open(os.path.join(ROOT, "raw", f"{m['id']}.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            out["monitors"].append(summarize(m, data))
        except Exception as e:  # noqa: BLE001
            out["monitors"].append({"id": m["id"], "route": m["route"], "cheapest": None, "error": f"{type(e).__name__}: {e}"})
        time.sleep(1.5)
    account = fetch_account(key)
    out["serpapi_account"] = account
    with open(os.path.join(ROOT, "serpapi_account.json"), "w", encoding="utf-8") as f:
        json.dump(account, f, ensure_ascii=False, indent=2)
    with open(os.path.join(ROOT, "prices.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open(os.path.join(ROOT, "history", f"{today.isoformat()}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    ok = sum(1 for x in out["monitors"] if x.get("cheapest"))
    print(f"{ok}/{len(out['monitors'])} monitores com preço")
    if not account.get("error"):
        print(f"SerpApi: {account.get('total_searches_left')} buscas restantes de {account.get('searches_per_month')} "
              f"(usadas no mês: {account.get('this_month_usage')}; renova {account.get('plan_renewal_date')})")
    for x in out["monitors"]:
        c = x.get("cheapest")
        print(f"  {x['id']:<3} {x['route']:<28} " + (f"{out['currency']} {c['price']}  {c['airline']}  ({c['stops']} escala(s))" if c else f"-- {x.get('error')}"))


if __name__ == "__main__":
    main()
