# Bet Bot

Bot de Telegram para consultar jogos do dia na ESPN e sugerir apostas com base em dados disponíveis no scoreboard. Suporta futebol e NBA.

## Recursos

- Consulta automática de ligas de futebol e NBA para a data atual.
- Filtro apenas para jogos que ainda não começaram.
- **Futebol**: 13 mercados (1x2, Over/Under 1.5/2.5, Draw No Bet, BTTS, Dupla Chance).
- **NBA**: 6 mercados (Moneyline, Spread, Over/Under Total).
- Detecção de **value bets** (⭐) — compara estimativa com odds implícitas.
- Mensagens formatadas em HTML (bold, hierarquia visual).
- Mercados ranqueados por confiança (12-93%) com análise textual.
- Busca paralela de ligas (ThreadPoolExecutor) para maior velocidade.
- Retry automático em falhas de rede.
- Botão inline para atualizar os palpites sem digitar comandos.
- Comando `/stats` para histórico de palpites.
- Logging estruturado.
- Token do Telegram carregado por variável de ambiente.
- Zero dependências externas (stdlib Python apenas).

## Comandos

| Comando | Descrição |
|---------|-----------|
| `/start` | Envia saudação e palpites do dia |
| `/stats` | Exibe histórico de palpites (últimos 30 dias) |
| Botão "Atualizar palpites" | Reconsulta a ESPN e reenvia sugestões |

## Value Bets

Mercados com ⭐ indicam que a estimativa do bot supera a odd implícita da casa em 5+ pontos percentuais.
⭐⭐ indica uma diferença de 12+ pp (value forte).
O edge exato é exibido como `+N%` ao lado da confiança.

## Configuração

1. Defina a variável `TELEGRAM_BOT_TOKEN`.
2. Opcionalmente ajuste:
   - `BETBOT_TIMEZONE` (padrão: `America/Sao_Paulo`)
   - `BETBOT_SUGGESTION_LIMIT` (padrão: `20`)
   - `BETBOT_POLL_SECONDS` (padrão: `25`)
   - `BETBOT_LEAGUES` — slugs ESPN separados por vírgula. Inclua `nba` para basquete.
     Ex: `eng.1,esp.1,nba`
3. Execute `python main.py`.

### Exemplo no PowerShell

```powershell
Copy-Item .env.example .env
$env:TELEGRAM_BOT_TOKEN="seu_token_aqui"
python main.py
```

## Estrutura

```
bet_bot/
├── analysis/              # Engines de sugestão
│   ├── __init__.py
│   ├── constants.py       # Constantes do futebol
│   ├── data_extractor.py  # Extração de dados da ESPN
│   ├── market_estimator.py # Estimadores de probabilidade
│   ├── formatter.py       # Cards HTML (futebol)
│   ├── engine.py          # SuggestionEngine (futebol)
│   └── nba_engine.py      # NBA: engine + constants + formatter
├── app.py                 # Entry point
├── bot.py                 # Bot Telegram (polling + comandos + multi-sport)
├── config.py              # Configuração (.env, env vars, sport mapping)
├── espn.py                # Cliente API ESPN (multi-sport)
├── http.py                # Cliente HTTP com retry
├── logging_config.py      # Configuração de logging
├── models.py              # Dataclasses (BetOption, MatchSuggestion)
└── stats.py               # Tracking de histórico
```

## Observações

- O projeto usa apenas bibliotecas da stdlib do Python.
- Caso uma liga não tenha jogos no dia, ela é ignorada silenciosamente.
- Se nenhuma partida elegível for encontrada, o bot informa isso ao usuário.
- O histórico de palpites é salvo em `bet_bot_history.json` (máx 30 dias).
- O token não foi salvo no código-fonte e deve permanecer apenas no ambiente ou no `.env` local.
