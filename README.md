# Bet Bot

Bot de Telegram para consultar jogos de futebol do dia na ESPN e sugerir apostas com base em dados disponíveis no scoreboard.

## Recursos

- Consulta automática das ligas configuradas para a data atual.
- Filtro apenas para jogos que ainda não começaram.
- Sugestões de apostas em formato enxuto para Telegram.
- Botão inline para atualizar os palpites sem digitar comandos.
- Token do Telegram carregado por variável de ambiente.

## Configuração

1. Defina a variável `TELEGRAM_BOT_TOKEN`.
2. Opcionalmente ajuste:
   - `BETBOT_TIMEZONE` (padrão: `America/Sao_Paulo`)
   - `BETBOT_SUGGESTION_LIMIT` (padrão: `20`)
   - `BETBOT_POLL_SECONDS` (padrão: `25`)
3. Execute `python main.py`.

Também é possível criar um arquivo `.env` local a partir do exemplo abaixo.

### Exemplo no PowerShell

```powershell
Copy-Item .env.example .env
$env:TELEGRAM_BOT_TOKEN="seu_token_aqui"
python main.py
```

## Fluxo

- `/start`: envia uma saudação e os melhores palpites do dia.
- `Atualizar palpites`: faz nova consulta à ESPN e reenvi­a as sugestões.

## Observações

- O projeto usa apenas bibliotecas da stdlib do Python.
- Caso uma liga não tenha jogos no dia, ela é ignorada silenciosamente.
- Se nenhuma partida elegível for encontrada, o bot informa isso ao usuário.
- O token não foi salvo no código-fonte e deve permanecer apenas no ambiente ou no `.env` local.
