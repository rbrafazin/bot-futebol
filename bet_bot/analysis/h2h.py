from __future__ import annotations

from typing import Any


def extract_h2h_text_signals(notes: str, home_team: str = "", away_team: str = "") -> dict[str, Any]:
    """Extract H2H-related signals from event notes/headlines text."""
    text = notes.lower()
    home_lower = home_team.lower()
    away_lower = away_team.lower()
    signals: dict[str, Any] = {
        "home_dominates_h2h": False,
        "away_dominates_h2h": False,
        "h2h_draws": False,
        "h2h_high_scoring": False,
        "h2h_low_scoring": False,
        "h2h_home_wins": 0,
        "h2h_away_wins": 0,
        "h2h_draws_count": 0,
        "h2h_total_matches": 0,
    }

    import re

    patterns = [
        r"(\w[\w\s]*?)\s+(?:have\s+)?won\s+(\d+)\s+of\s+(?:the\s+)?(?:their\s+)?last\s+(\d+)\s+(?:meetings|matches|games)",
        r"(\w[\w\s]*?)\s+(?:have\s+)?won\s+(?:the\s+)?last\s+(\d+)\s+(?:meetings|matches|games)",
        r"(\w[\w\s]*?)\s+(?:are\s+)?unbeaten\s+in\s+(?:their\s+)?last\s+(\d+)\s+(?:meetings|matches|games|visits)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            team_hint = (match.group(1) or "").strip().lower() if match.lastindex and match.lastindex >= 1 else ""
            wins_count = int(match.group(2)) if match.lastindex and match.lastindex >= 2 else 0
            total = int(match.group(3)) if match.lastindex and match.lastindex >= 3 else wins_count

            if total > 0:
                signals["h2h_total_matches"] = max(signals["h2h_total_matches"], total)
                ratio = wins_count / total
                is_home = team_hint and (team_hint in home_lower or home_lower in team_hint)
                if is_home:
                    signals["h2h_home_wins"] = max(signals["h2h_home_wins"], wins_count)
                    if ratio >= 0.6:
                        signals["home_dominates_h2h"] = True
                else:
                    signals["h2h_away_wins"] = max(signals["h2h_away_wins"], wins_count)
                    if ratio >= 0.6:
                        signals["away_dominates_h2h"] = True
            break

    # Draw patterns
    if re.search(r"(\d+)\s+draws?\s+in\s+(?:the\s+)?last\s+(\d+)", text):
        signals["h2h_draws"] = True

    # Goal patterns
    if re.search(r"(?:over|more than)\s+(\d+\.?\d*)\s+goals\s+in\s+(?:the\s+)?last\s+\d+\s+meetings", text):
        signals["h2h_high_scoring"] = True
    if re.search(r"(?:under|fewer than|less than)\s+(\d+\.?\d*)\s+goals\s+in\s+(?:the\s+)?last", text):
        signals["h2h_low_scoring"] = True

    return signals


def analyze_h2h_matches(
    home_team_id: str,
    away_team_id: str,
    home_recent: list[dict[str, Any]],
    away_recent: list[dict[str, Any]],
) -> dict[str, Any]:
    """Find H2H matches from recent form data and compute stats."""
    h2h_home_wins = 0
    h2h_away_wins = 0
    h2h_draws = 0
    h2h_total_goals: list[int] = []

    away_id_set = {str(away_team_id)}
    for event in home_recent:
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        ids = {
            str((c.get("team") or {}).get("id", ""))
            for c in competitors
        }
        if away_id_set & ids and len(ids) >= 2:
            home_score = 0
            away_score = 0
            for c in competitors:
                score_str = c.get("score", "0")
                try:
                    score = int(str(score_str))
                except (ValueError, TypeError):
                    score = 0
                ha = (c.get("homeAway") or "").lower()
                if ha == "home":
                    home_score = score
                else:
                    away_score = score

            if home_score > away_score:
                h2h_home_wins += 1
            elif away_score > home_score:
                h2h_away_wins += 1
            else:
                h2h_draws += 1
            h2h_total_goals.append(home_score + away_score)

    return {
        "h2h_home_wins": h2h_home_wins,
        "h2h_away_wins": h2h_away_wins,
        "h2h_draws": h2h_draws,
        "h2h_total_matches": h2h_home_wins + h2h_away_wins + h2h_draws,
        "h2h_avg_goals": sum(h2h_total_goals) / len(h2h_total_goals) if h2h_total_goals else 0,
    }


def compute_recent_form_stats(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute recent form stats (last N games) for a team."""
    wins = 0
    draws = 0
    losses = 0
    goals_for = 0
    goals_against = 0
    total_matches = 0

    for event in events:
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        if len(competitors) < 2:
            continue

        team_score = 0
        opponent_score = 0
        for c in competitors:
            ha = (c.get("homeAway") or "").lower()
            try:
                score = int(str(c.get("score", "0")))
            except (ValueError, TypeError):
                score = 0
            if ha == "home":
                home_score = score
                away_score = opponent_score if opponent_score else 0
            else:
                away_score = score
                home_score = opponent_score if opponent_score else 0
            opponent_score = away_score if ha == "home" else home_score

        if team_score > 0 or opponent_score > 0 or event.get("status", {}).get("type", {}).get("state") == "post":
            total_matches += 1
            goals_for += team_score
            goals_against += opponent_score

    return {
        "recent_wins": wins,
        "recent_draws": draws,
        "recent_losses": losses,
        "recent_goals_for": goals_for,
        "recent_goals_against": goals_against,
        "recent_matches": total_matches,
    }


def compute_h2h_adjustments(
    h2h_data: dict[str, Any],
    text_signals: dict[str, Any],
) -> dict[str, float]:
    """Compute adjustment factors for estimates based on H2H analysis."""
    adjustments = {
        "home_win_adj": 0.0,
        "away_win_adj": 0.0,
        "draw_adj": 0.0,
        "over_adj": 0.0,
        "under_adj": 0.0,
        "h2h_summary": "",
    }

    h2h_matches = h2h_data.get("h2h_total_matches", 0)
    parts: list[str] = []

    if h2h_matches >= 2:
        home_wins = h2h_data["h2h_home_wins"]
        away_wins = h2h_data["h2h_away_wins"]
        h2h_draws = h2h_data["h2h_draws"]
        home_ratio = home_wins / h2h_matches

        if home_ratio >= 0.75:
            adjustments["home_win_adj"] = 0.06
            adjustments["draw_adj"] = -0.02
            parts.append(f"Time da casa venceu {home_wins} dos últimos {h2h_matches} confrontos")
        elif home_wins == 0 and away_wins >= h2h_matches * 0.7:
            adjustments["away_win_adj"] = 0.06
            adjustments["draw_adj"] = -0.02
            parts.append(f"Time visitante venceu {away_wins} dos últimos {h2h_matches} confrontos")

        if h2h_draws >= h2h_matches * 0.4:
            adjustments["draw_adj"] += 0.05
            parts.append(f"{h2h_draws} empates nos últimos {h2h_matches} confrontos")

        avg_goals = h2h_data.get("h2h_avg_goals", 0)
        if avg_goals >= 3.0:
            adjustments["over_adj"] = 0.04
            parts.append(f"Média de {avg_goals:.1f} gols nos confrontos")
        elif avg_goals > 0 and avg_goals <= 1.5:
            adjustments["under_adj"] = 0.04
            parts.append(f"Média de apenas {avg_goals:.1f} gols nos confrontos")

    if text_signals.get("home_dominates_h2h"):
        adjustments["home_win_adj"] = max(adjustments["home_win_adj"], 0.04)
    if text_signals.get("away_dominates_h2h"):
        adjustments["away_win_adj"] = max(adjustments["away_win_adj"], 0.04)
    if text_signals.get("h2h_draws"):
        adjustments["draw_adj"] = max(adjustments["draw_adj"], 0.03)
    if text_signals.get("h2h_high_scoring"):
        adjustments["over_adj"] = max(adjustments["over_adj"], 0.03)
    if text_signals.get("h2h_low_scoring"):
        adjustments["under_adj"] = max(adjustments["under_adj"], 0.03)

    adjustments["h2h_summary"] = " | ".join(parts) if parts else ""
    return adjustments
