from __future__ import annotations

from . import constants as c


def estimate_side_probability(book_probability: float | str | None, form_score: float) -> float:
    form_probability = c.FORM_BASE + (form_score * c.FORM_MULTIPLIER)
    if isinstance(book_probability, float):
        estimate = (book_probability * c.BOOK_WEIGHT) + (form_probability * c.FORM_WEIGHT)
    else:
        estimate = form_probability
    return max(c.SIDE_PROB_MIN, min(c.SIDE_PROB_MAX, estimate))


def estimate_over_25_probability(
    over_25_probability: float | str | None,
    over_under: float | str | None,
    over_25_signal: bool,
    equilibrium: bool,
    draw_rate: float,
    strength_gap: int,
) -> float:
    if isinstance(over_25_probability, float):
        estimate = over_25_probability
    elif isinstance(over_under, float):
        estimate = 0.54 if over_under >= 2.5 else 0.46
    else:
        estimate = c.OVER_25_BASELINE
        estimate += (0.25 - draw_rate) * c.OVER_25_DRAW_RATE_COEFF
        estimate += min(c.OVER_25_STRENGTH_CAP, abs(strength_gap) * c.OVER_25_STRENGTH_COEFF)
        if equilibrium:
            estimate -= 0.02

    if over_25_signal:
        estimate += c.OVER_25_SIGNAL_BONUS

    return max(c.OVER_25_PROB_MIN, min(c.OVER_25_PROB_MAX, estimate))


def estimate_over_15_probability(
    over_25_estimate: float,
    over_15_signal: bool,
    draw_rate: float,
) -> float:
    estimate = over_25_estimate + c.OVER_15_BONUS
    estimate += (0.25 - draw_rate) * c.OVER_15_DRAW_RATE_BONUS
    if over_15_signal:
        estimate += c.OVER_15_SIGNAL_BONUS
    return max(c.OVER_15_PROB_MIN, min(c.OVER_15_PROB_MAX, estimate))


def estimate_draw_probability(
    draw_probability: float | str | None,
    equilibrium: bool,
    home_form: float,
    away_form: float,
    favorite_gap: float | str | None,
    draw_rate: float,
) -> float:
    estimate = c.DRAW_BASELINE_EQUILIBRIUM if equilibrium else c.DRAW_BASELINE_NORMAL
    estimate += (draw_rate - 0.25) * c.DRAW_RATE_COEFF
    estimate -= min(0.05, abs(home_form - away_form) * c.DRAW_FORM_GAP_COEFF)
    if isinstance(favorite_gap, float):
        estimate -= min(0.06, favorite_gap * c.DRAW_FAVORITE_GAP_COEFF)
    if isinstance(draw_probability, float):
        estimate = (draw_probability * c.BOOK_WEIGHT) + (estimate * c.FORM_WEIGHT)
    return max(c.DRAW_PROB_MIN, min(c.DRAW_PROB_MAX, estimate))


def estimate_under_probability(
    under_probability: float | str | None,
    over_estimate: float,
) -> float:
    if isinstance(under_probability, float):
        estimate = under_probability
    else:
        estimate = 1.0 - over_estimate
    return max(c.UNDER_PROB_MIN, min(c.UNDER_PROB_MAX, estimate))


def estimate_draw_no_bet_probability(
    side_estimate: float,
    other_side_estimate: float,
) -> float:
    total = side_estimate + other_side_estimate
    if total <= 0:
        return 0.5
    estimate = side_estimate / total
    return max(c.DNB_PROB_MIN, min(c.DNB_PROB_MAX, estimate))


def estimate_btts_probability(
    over_25_estimate: float,
    equilibrium: bool,
    favorite_gap: float | str | None,
    btts_signal: bool,
    draw_rate: float,
    form_gap: float,
) -> float:
    estimate = c.BTTS_BASELINE + (over_25_estimate * c.BTTS_OVER_25_WEIGHT)
    if equilibrium:
        estimate += c.BTTS_EQUILIBRIUM_BONUS
    estimate += (0.25 - draw_rate) * c.BTTS_DRAW_RATE_COEFF
    estimate -= min(c.BTTS_FORM_GAP_CAP, form_gap * c.BTTS_FORM_GAP_COEFF)
    if isinstance(favorite_gap, float):
        estimate -= min(c.BTTS_FAVORITE_GAP_CAP, favorite_gap * c.BTTS_FAVORITE_GAP_COEFF)
    if btts_signal:
        estimate += c.BTTS_SIGNAL_BONUS
    return max(c.BTTS_PROB_MIN, min(c.BTTS_PROB_MAX, estimate))


def estimate_double_chance_1x(
    home_estimate: float,
    draw_estimate: float,
) -> float:
    estimate = home_estimate + draw_estimate
    return max(c.DC_PROB_MIN, min(c.DC_PROB_MAX, estimate))


def estimate_double_chance_x2(
    away_estimate: float,
    draw_estimate: float,
) -> float:
    estimate = away_estimate + draw_estimate
    return max(c.DC_PROB_MIN, min(c.DC_PROB_MAX, estimate))


def estimate_double_chance_12(
    home_estimate: float,
    away_estimate: float,
) -> float:
    estimate = home_estimate + away_estimate
    return max(c.DC_PROB_MIN, min(c.DC_PROB_MAX, estimate))


def to_percent(probability: float) -> int:
    return max(c.CONFIDENCE_FLOOR, min(c.CONFIDENCE_CEILING, int(round(probability * 100))))
