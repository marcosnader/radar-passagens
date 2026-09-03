# Radar de Passagens — coletor de tarifas

Roda todo dia às 08:30 BRT (GitHub Actions) e consulta a **Google Flights API da SerpApi** para cada
monitor em `monitors.json`, gravando o resultado em `prices.json`. A tarefa diária do Radar (Claude)
lê esse arquivo às 09:08 BRT e atualiza o painel — sem depender de rastreio manual no Google Flights.

- `monitors.json` — rotas, datas, cabine, escalas (espelho dos cards do painel; a tarefa diária pode atualizá-lo).
- `fetch_prices.py` — uma consulta por monitor; grava `prices.json`, `history/AAAA-MM-DD.json` e `raw/<id>.json`.
- `serpapi_account.json` — saldo da conta SerpApi (a conta é compartilhada com outros projetos; o painel mostra o total).
- Segredo necessário: `SERPAPI_KEY` (Settings → Secrets and variables → Actions). Plano grátis: 250 buscas/mês; 5 monitores/dia ≈ 150.
- LATAM e Avianca excluídas por padrão (`exclude_airlines_default`); sobrescreva por monitor com `"exclude_airlines": ""`.
