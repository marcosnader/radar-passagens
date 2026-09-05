#!/usr/bin/env python
"""Aplica ao monitors.json a versao mais recente enviada pelo painel.

O painel do Radar de Passagens abre a tela "novo arquivo" do GitHub ja preenchida
com sync/monitors-AAAAMMDD-HHMM.json (o Marcos so clica em Commit). Este script,
executado pelo GitHub Actions antes da coleta, pega o arquivo mais recente da pasta
sync/, valida e, se for diferente do monitors.json atual, sobrescreve monitors.json.
Nenhuma credencial envolvida: o commit e do proprio Marcos, via navegador.
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(ROOT, "monitors.json")


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "sync", "monitors-*.json")))
    if not files:
        print("sync/: nada a aplicar")
        return
    latest = files[-1]
    with open(latest, encoding="utf-8") as f:
        new = json.load(f)
    if not isinstance(new.get("monitors"), list):
        print(f"sync/: {os.path.basename(latest)} invalido (sem lista monitors) - ignorado")
        return
    for m in new["monitors"]:
        for k in ("id", "departure_id", "arrival_id", "outbound_date"):
            if not m.get(k):
                print(f"sync/: monitor sem campo {k} em {os.path.basename(latest)} - ignorado")
                return
    new.setdefault("currency", "EUR")
    new.setdefault("exclude_airlines_default", "LA,AV")
    current = None
    if os.path.exists(TARGET):
        with open(TARGET, encoding="utf-8") as f:
            current = json.load(f)
    if current == new:
        print(f"sync/: {os.path.basename(latest)} ja aplicado")
        return
    with open(TARGET, "w", encoding="utf-8") as f:
        json.dump(new, f, ensure_ascii=False, indent=2)
        f.write("\n")
    ids = [m["id"] for m in new["monitors"]]
    print(f"sync/: monitors.json atualizado a partir de {os.path.basename(latest)} ({len(ids)} monitores: {', '.join(ids)})")


if __name__ == "__main__":
    main()
