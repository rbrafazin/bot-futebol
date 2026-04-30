from __future__ import annotations

# Market identifiers
MARKET_HOME = "1 (Casa)"
MARKET_DRAW = "X (Empate)"
MARKET_AWAY = "2 (Visitante)"
MARKET_OVER_15 = "Over 1.5"
MARKET_UNDER_15 = "Under 1.5"
MARKET_OVER_25 = "Over 2.5"
MARKET_UNDER_25 = "Under 2.5"
MARKET_DNB_HOME = "Empate Anula Casa"
MARKET_DNB_AWAY = "Empate Anula Visitante"
MARKET_BTTS = "Ambas Marcam"
MARKET_DC_1X = "Dupla Chance 1X"
MARKET_DC_X2 = "Dupla Chance X2"
MARKET_DC_12 = "Dupla Chance 12"

# Confidence clamping
CONFIDENCE_FLOOR = 12
CONFIDENCE_CEILING = 93

# Probability clamping per market
SIDE_PROB_MIN = 0.18
SIDE_PROB_MAX = 0.88
DRAW_PROB_MIN = 0.12
DRAW_PROB_MAX = 0.42
OVER_25_PROB_MIN = 0.30
OVER_25_PROB_MAX = 0.82
OVER_15_PROB_MIN = 0.45
OVER_15_PROB_MAX = 0.90
UNDER_PROB_MIN = 0.10
UNDER_PROB_MAX = 0.82
DNB_PROB_MIN = 0.36
DNB_PROB_MAX = 0.90
BTTS_PROB_MIN = 0.18
BTTS_PROB_MAX = 0.78
DC_PROB_MIN = 0.25
DC_PROB_MAX = 0.92

# Odds-to-probability blending
BOOK_WEIGHT = 0.72
FORM_WEIGHT = 0.28

# Form score calculation
FORM_BASE = 0.22
FORM_MULTIPLIER = 0.56
FORM_DEFAULT = 0.50

# Draw estimation
DEFAULT_DRAW_RATE = 0.27
DRAW_BASELINE_EQUILIBRIUM = 0.26
DRAW_BASELINE_NORMAL = 0.21
DRAW_RATE_COEFF = 0.40
DRAW_FORM_GAP_COEFF = 0.16
DRAW_FAVORITE_GAP_COEFF = 0.35

# Over/Under estimation
OVER_25_BASELINE = 0.49
OVER_25_SIGNAL_BONUS = 0.05
OVER_15_BONUS = 0.16
OVER_15_SIGNAL_BONUS = 0.04
OVER_15_DRAW_RATE_BONUS = 0.12
OVER_25_DRAW_RATE_COEFF = 0.32
OVER_25_STRENGTH_COEFF = 0.004
OVER_25_STRENGTH_CAP = 0.05

# BTTS estimation
BTTS_BASELINE = 0.24
BTTS_OVER_25_WEIGHT = 0.52
BTTS_EQUILIBRIUM_BONUS = 0.08
BTTS_DRAW_RATE_COEFF = 0.16
BTTS_FORM_GAP_COEFF = 0.18
BTTS_FORM_GAP_CAP = 0.08
BTTS_FAVORITE_GAP_COEFF = 0.45
BTTS_FAVORITE_GAP_CAP = 0.09
BTTS_SIGNAL_BONUS = 0.08

# Strength score
STRENGTH_CLEAR_GAP = 7
STRENGTH_BOOST = 4
DNB_BOOST = 3
STRENGTH_WIN_PTS = 3
STRENGTH_DRAW_PTS = 1

# Equilibrium
FAVORITE_GAP_EQUILIBRIUM = 0.09
STRENGTH_GAP_EQUILIBRIUM = 2
CLEAR_FAVORITE_GAP = 0.16
STRENGTH_CLEAR_FAVORITE = 5

# Signal detection tokens
BTTS_TOKENS: tuple[str, ...] = (
    "both teams to score",
    "btts",
    "ambas marcam",
    "teams to score",
    "ambos marcam",
    "ambos times marcam",
    "ambos times a marcar",
)

EQUILIBRIUM_TOKENS: tuple[str, ...] = (
    "pick'em",
    "pick em",
    "equilibr",
    "tight",
    "close matchup",
    "draw",
    "very close",
    "evenly match",
    "too close to call",
    "toss-up",
    "toss up",
    "dead heat",
    "even contest",
    "balanced",
    "neck and neck",
)

GOAL_SIGNAL_OVER_25_TOKENS: tuple[str, ...] = (
    "over 2.5",
    "o 2.5",
    "2.5 goals",
    "2,5",
    "over 2½",
    "acima de 2.5",
    "mais de 2.5",
    "total over 2.5",
    "over total 2.5",
)

GOAL_SIGNAL_OVER_15_TOKENS: tuple[str, ...] = (
    "over 1.5",
    "o 1.5",
    "1.5 goals",
    "1,5",
    "over 1½",
    "acima de 1.5",
    "mais de 1.5",
)

# Under market signals
UNDER_25_TOKENS: tuple[str, ...] = (
    "under 2.5",
    "u 2.5",
    "under 2½",
    "abaixo de 2.5",
    "menos de 2.5",
)

UNDER_15_TOKENS: tuple[str, ...] = (
    "under 1.5",
    "u 1.5",
    "under 1½",
    "abaixo de 1.5",
    "menos de 1.5",
)

# Form signals from text notes
HOME_FORM_POSITIVE_TOKENS: tuple[str, ...] = (
    "won last",
    "won their last",
    "winning streak",
    "unbeaten",
    "unbeaten run",
    "invict",
    "home win",
    "strong at home",
    "home advantage",
    "home form",
    "consecutive wins",
    "win streak",
    "streak",
    "won",
    "victory",
)

HOME_FORM_NEGATIVE_TOKENS: tuple[str, ...] = (
    "lost last",
    "lost their last",
    "losing streak",
    "without a win",
    "winless",
    "home loss",
    "struggling at home",
    "poor form",
    "defeat",
    "beaten",
)

AWAY_FORM_POSITIVE_TOKENS: tuple[str, ...] = (
    "away win",
    "strong away",
    "away form",
    "road win",
    "road victory",
)

AWAY_FORM_NEGATIVE_TOKENS: tuple[str, ...] = (
    "away loss",
    "struggling away",
    "poor away",
    "road defeat",
)

# Rationale messages (pt-BR)
RATIONALE_CLEAR_HOME = "{home} aparece como favorito claro nas odds da ESPN."
RATIONALE_CLEAR_AWAY = "{away} aparece como favorito claro nas odds da ESPN."
RATIONALE_STRONGER_HOME = "{home} apresenta sinal mais forte que {away}."
RATIONALE_STRONGER_AWAY = "{away} apresenta sinal mais forte que {home}."
RATIONALE_OPEN_MATCH = "A linha principal de gols da ESPN sugere uma partida aberta."
RATIONALE_EQUILIBRIUM = "Confronto equilibrado, com boa base para mercados conservadores."
RATIONALE_DEFAULT = "Os mercados foram ranqueados com base em odds e retrospecto recente disponíveis na ESPN."
