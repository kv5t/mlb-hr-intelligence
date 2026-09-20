"""Explicit public DTO fields; no operational model is serialized wholesale."""

from analytics.values import MetricValue
from domain.models import GameDataCoverage


def metric_value(metric: MetricValue):
    return {
        "state": metric.state.value,
        "value": metric.value,
        "unit": metric.unit,
        "numerator": metric.numerator,
        "denominator": metric.denominator,
        "reason": metric.reason,
    }


def season_summary(row):
    return {
        "id": str(row.id),
        "year": row.year,
        "label": row.label,
        "starts_on": row.starts_on,
        "ends_on": row.ends_on,
        "status": row.status,
    }


def team_summary(row):
    return {
        "id": str(row.id),
        "mlb_id": row.mlb_id,
        "display_name": row.display_name,
        "abbreviation": row.abbreviation,
        "league": row.league,
        "division": row.division,
    }


def player_summary(row, represented_team=None):
    return {
        "id": str(row.id),
        "mlb_id": row.mlb_id,
        "display_name": row.display_name,
        "given_name": row.given_name,
        "family_name": row.family_name,
        "bats": row.bats,
        "throws": row.throws,
        "primary_position": row.primary_position,
        "represented_team": team_summary(represented_team)
        if represented_team
        else None,
    }


def coverage_summary(game):
    rows = {row.domain: row for row in GameDataCoverage.objects.filter(game=game)}
    return [
        {
            "domain": domain,
            "state": rows[domain].state
            if domain in rows
            else GameDataCoverage.State.UNKNOWN,
            "reason_codes": [rows[domain].reason_code]
            if domain in rows and rows[domain].reason_code
            else [],
        }
        for domain in GameDataCoverage.Domain.values
    ]


def game_summary(game, hr_metric):
    venue = game.venue
    return {
        "id": str(game.id),
        "mlb_game_pk": game.mlb_game_pk,
        "season": game.season.year,
        "game_type": game.game_type,
        "official_date": game.official_date,
        "scheduled_start_at_utc": game.scheduled_start_at_utc,
        "status": game.status,
        "finality": game.finality,
        "home_team": team_summary(game.home_team),
        "away_team": team_summary(game.away_team),
        "home_score": game.home_score,
        "away_score": game.away_score,
        "scheduled_game_number": game.scheduled_game_number,
        "venue": {
            "id": str(venue.id),
            "name": venue.name,
            "timezone_id": venue.timezone_id,
        }
        if venue
        else None,
        "hr_count": metric_value(hr_metric),
    }
