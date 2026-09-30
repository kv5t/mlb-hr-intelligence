"""Synchronous file representations of captured public analytical payloads."""

import csv
import io
import json
from datetime import date, datetime
from html import escape

from django.http import HttpResponse
from rest_framework.exceptions import NotFound
from rest_framework.negotiation import DefaultContentNegotiation

from domain.models import Player, Team

from .base import ReadOnlyView
from .errors import ApiProblem
from .services import (
    home_run_scope,
    order_home_run_events,
    player_home_run_events,
    player_recurrence,
    public_home_run_events,
    team_home_run_events,
    team_recurrence,
)
from .views import (
    _PLAYER_ANALYTICAL_PARAMETERS,
    _TEAM_ANALYTICAL_PARAMETERS,
    _analytical_inputs,
    _parameters,
    _select_player,
    _select_team,
    _uuid,
    player_leaderboard_rows,
)

METRIC_FIELDS = ("value", "state", "reason", "unit", "numerator", "denominator")
PLAYER_KPIS = (
    "hr",
    "pa",
    "hr_per_pa",
    "pa_per_hr",
    "hr_per_game",
    "hr_games",
    "hr_game_pct",
    "multi_hr_games",
    "avg_hr_gap_games",
    "median_hr_gap_games",
    "current_hr_drought_games",
    "max_hr_drought_games",
    "current_hr_streak_games",
    "max_hr_streak_games",
    "current_hr_drought_pa",
    "max_hr_drought_pa",
)
META_FIELDS = ("export_scope", "scope", "coverage", "dataset_revision", "data_as_of")
IDENTITY_FIELDS = (
    "subject_id",
    "subject_name",
    "player_id",
    "player_name",
    "represented_team_id",
    "represented_team",
)
LEGEND = (
    "VALUE: numeric evidence, including 0. NOT_APPLICABLE: does not apply. "
    "UNKNOWN: insufficient evidence. INCOMPLETE: partial/conflicting evidence. "
    "ORDER_UNVERIFIED: unresolved order. INSUFFICIENT_HISTORY: not enough history. "
    "UNKNOWN and INCOMPLETE are not zero. Current drought/streak may exceed "
    "the window; maximum runs and gaps are window-local."
)


def _json(value):
    return json.dumps(value, default=_string, ensure_ascii=True, separators=(",", ":"))


def _string(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat().replace("+00:00", "Z")
    return str(value)


def metric_columns(prefix):
    return [f"{prefix}.{field}" for field in METRIC_FIELDS]


def metric_cells(prefix, metric):
    return {f"{prefix}.{field}": metric.get(field) for field in METRIC_FIELDS}


def _identity(payload):
    subject = payload.get("team") or payload.get("player") or {}
    player = payload.get("player") or {}
    represented = player.get("represented_team") or {}
    return {
        "subject_id": subject.get("id"),
        "subject_name": subject.get("display_name"),
        "player_id": player.get("id"),
        "player_name": player.get("display_name"),
        "represented_team_id": represented.get("id"),
        "represented_team": represented.get("display_name"),
    }


def _metadata(payload, export_scope, meta):
    return {
        "export_scope": _json(export_scope),
        "scope": _json(payload.get("scope", export_scope)),
        "coverage": _json(payload.get("coverage", [])),
        **meta,
    }


def csv_rows(kind, payload):
    """Stable normalized rows. No math, selection or evidence evaluation here."""
    if kind == "leaderboard":
        prefixes = [f"player.{key}" for key in PLAYER_KPIS]
        columns = [
            *IDENTITY_FIELDS,
            *(column for prefix in prefixes for column in metric_columns(prefix)),
        ]
        rows = []
        for item in payload["results"]:
            row = {
                **_identity(item),
                "scope": _json(item["scope"]),
                "coverage": _json(item["coverage"]),
            }
            for prefix in prefixes:
                row.update(metric_cells(prefix, item["metrics"][prefix]))
            rows.append(row)
        return columns, rows
    if kind == "team_recurrence":
        columns = [
            *IDENTITY_FIELDS,
            "game_id",
            "official_date",
            "game_order",
            "scheduled_game_number",
            "opponent_id",
            "opponent",
            "home_away",
            *metric_columns("player_season_hr"),
            *metric_columns("window_hr"),
            "cell_state",
            "hr_count",
            "reason",
            "home_run_event_ids",
            *(
                column
                for key in PLAYER_KPIS[:-2]
                for column in metric_columns(f"team.{key}")
            ),
        ]
        rows = []
        for player_row in payload["rows"]:
            for index, (column, cell) in enumerate(
                zip(payload["columns"], player_row["cells"], strict=True)
            ):
                rows.append(
                    {
                        **_identity(payload),
                        "player_id": player_row["player"]["id"],
                        "player_name": player_row["player"]["display_name"],
                        "game_id": column["game_id"],
                        "official_date": column["official_date"],
                        "game_order": index + 1,
                        "scheduled_game_number": column["scheduled_game_number"],
                        "opponent_id": column["opponent"]["id"],
                        "opponent": column["opponent"]["display_name"],
                        "home_away": column["home_away"],
                        **metric_cells(
                            "player_season_hr", player_row["player_season_hr"]
                        ),
                        **metric_cells("window_hr", player_row["window_hr"]),
                        "cell_state": cell["state"],
                        "hr_count": cell["hr_count"],
                        "reason": cell["reason"],
                        "home_run_event_ids": _json(cell["home_run_event_ids"]),
                    }
                )
        for row in rows:
            for key, metric in payload["metrics"].items():
                row.update(metric_cells(key, metric))
        return columns, rows
    if kind == "player_recurrence":
        columns = [
            "record_type",
            *IDENTITY_FIELDS,
            "metric_id",
            *metric_columns("metric"),
            "game_id",
            "official_date",
            "game_order",
            "represented_teams",
            *metric_columns("pa"),
            *metric_columns("hr"),
            "from_game_id",
            "to_game_id",
            *metric_columns("non_hr_games"),
        ]
        rows = [
            {
                "record_type": "SUMMARY",
                "metric_id": key,
                **metric_cells("metric", metric),
            }
            for key, metric in sorted(payload["metrics"].items())
        ]
        rows.extend(
            {
                "record_type": "OBSERVATION",
                "game_id": item["game_id"],
                "official_date": item["official_date"],
                "game_order": index + 1,
                "represented_teams": _json(item["represented_teams"]),
                **metric_cells("pa", item["pa"]),
                **metric_cells("hr", item["hr"]),
            }
            for index, item in enumerate(payload["observations"])
        )
        rows.extend(
            {
                "record_type": "GAP",
                "from_game_id": item["from_game_id"],
                "to_game_id": item["to_game_id"],
                **metric_cells("non_hr_games", item["non_hr_games"]),
            }
            for item in payload["gaps"]
        )
        return columns, [{**_identity(payload), **row} for row in rows]
    columns = [
        "record_type",
        *IDENTITY_FIELDS,
        *metric_columns("total_hr"),
        "event_id",
        "game_id",
        "plate_appearance_id",
        "official_date",
        "batter_id",
        "batter",
        "pitcher_id",
        "pitcher",
        "batting_team_id",
        "batting_team",
        "inning",
        "half_inning",
        "game_pa_ordinal",
        "source_label",
        "retrieved_at",
    ]
    base = {**_identity(payload), **metric_cells("total_hr", payload["total_hr"])}
    rows = [{**base, "record_type": "SUMMARY"}]
    for event in payload["results"]:
        pitcher, provenance = event["pitcher"] or {}, event["provenance"] or {}
        rows.append(
            {
                **base,
                "record_type": "EVENT",
                "event_id": event["id"],
                "game_id": event["game_id"],
                "plate_appearance_id": event["plate_appearance_id"],
                "official_date": event["official_date"],
                "batter_id": event["batter"]["id"],
                "batter": event["batter"]["display_name"],
                "pitcher_id": pitcher.get("id"),
                "pitcher": pitcher.get("display_name"),
                "batting_team_id": event["batting_team"]["id"],
                "batting_team": event["batting_team"]["display_name"],
                "inning": event["inning"],
                "half_inning": event["half_inning"],
                "game_pa_ordinal": event["game_pa_ordinal"],
                "source_label": provenance.get("source_label"),
                "retrieved_at": provenance.get("retrieved_at"),
            }
        )
    return columns, rows


def render_csv(kind, payload, export_scope, meta):
    columns, rows = csv_rows(kind, payload)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=[*META_FIELDS, *columns], lineterminator="\r\n"
    )
    writer.writeheader()
    metadata = _metadata(payload, export_scope, meta)
    for row in rows:
        writer.writerow({**metadata, **row})
    return stream.getvalue().encode("utf-8"), len(rows)


def _text(value):
    return escape("" if value is None else _string(value))


def metric_text(metric):
    value = _string(metric["value"]) if metric["state"] == "VALUE" else "unavailable"
    counts = (
        ""
        if metric["numerator"] is None
        else f"; numerator={metric['numerator']}; denominator={metric['denominator']}"
    )
    reason = f"; {metric['reason']}" if metric["reason"] else ""
    return f"{value} {metric['unit'] or ''} [{metric['state']}{reason}{counts}]"


def _compact_metric(metric):
    value = _string(metric["value"]) if metric["state"] == "VALUE" else "unavailable"
    reason = f"; {metric['reason']}" if metric["reason"] else ""
    return f"{value} {metric['unit'] or ''}\n[{metric['state']}{reason}]"


def _table(headers, rows, *, css_class=""):
    return (
        f'<table class="{css_class}"><thead><tr>'
        + "".join(f"<th>{_text(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>" + "".join(f"<td>{_text(value)}</td>" for value in row) + "</tr>"
            for row in rows
        )
        + "</tbody></table>"
    )


def _summary(payload):
    return _table(
        ["Metric", "Returned value / semantic state"],
        [
            (key, metric_text(value))
            for key, value in payload.get("metrics", {}).items()
        ],
    )


def _scope_text(scope):
    return " | ".join(f"{key}: {_string(value)}" for key, value in scope.items())


def render_html(kind, payload, export_scope, meta):
    titles = {
        "leaderboard": "Player leaderboard",
        "team_recurrence": "Team recurrence matrix",
        "player_recurrence": "Player recurrence",
        "team_home_runs": "Team home-run log",
        "player_home_runs": "Player home-run log",
    }
    identity = _identity(payload)
    scope = payload.get("scope", export_scope)
    coverage = payload.get("coverage", [])
    head = (
        f"<h1>{titles[kind]}</h1>"
        f"<p>Subject: {_text(identity['subject_name'] or 'Matching players')} "
        f"{_text(identity['subject_id'])}</p>"
        f"<p class='scope'>{_text(_scope_text(scope))}</p>"
        f"<p>Dataset revision: {_text(meta['dataset_revision'])} | "
        f"data_as_of: {_text(meta['data_as_of'])}</p>"
        f"<p>Coverage: {_text(_json(coverage))}</p>"
        f"<p class='legend'>{_text(LEGEND)}</p>"
    )
    if kind == "team_recurrence":
        content = _summary(payload)
        for start in range(0, len(payload["columns"]), 15):
            columns = payload["columns"][start : start + 15]
            headers = [
                "Player",
                "Season HR",
                "Window HR",
                *[
                    f"{_string(column['official_date'])}\n"
                    f"Game {column['scheduled_game_number'] or 'unknown'}\n"
                    f"{
                        (column['opponent']['display_name'] or column['opponent']['id'])
                    }\n"
                    f"{column['home_away']}"
                    for column in columns
                ],
            ]
            data = []
            for row in payload["rows"]:
                cells = []
                for cell in row["cells"][start : start + 15]:
                    cells.append(
                        f"{cell['hr_count']} HR"
                        if cell["state"] == "HR_COUNT"
                        else {
                            "KNOWN_ZERO": "0",
                            "DNP": "DNP",
                            "ZERO_PA_APPEARANCE": "0 PA",
                            "NOT_WITH_TEAM": "Not with team",
                            "UNKNOWN": "Unknown",
                            "INCOMPLETE": "Partial",
                        }[cell["state"]]
                    )
                data.append(
                    [
                        row["player"]["display_name"] or row["player"]["id"],
                        _compact_metric(row["player_season_hr"]),
                        _compact_metric(row["window_hr"]),
                        *cells,
                    ]
                )
            content += (
                f"<section class='matrix-group'>"
                f"<h2>Games {start + 1}-{start + len(columns)} "
                f"of {len(payload['columns'])}</h2>"
                + _table(headers, data, css_class="matrix")
                + "</section>"
            )
        if not payload["columns"]:
            content += "<p>No definitive selected game columns.</p>"
    elif kind == "leaderboard":
        content = ""
        for row in payload["results"]:
            represented = (row["player"]["represented_team"] or {}).get("display_name")
            content += (
                f"<section class='player'>"
                f"<h2>{_text(row['player']['display_name'])} "
                f"({_text(row['player']['id'])})</h2>"
                f"<p>{_text(_scope_text(row['scope']))}</p>"
                f"<p>Represented team: "
                f"{_text(represented or 'not asserted')}"
                "</p>"
                f"<p>Coverage: {_text(_json(row['coverage']))}</p>"
                + _summary(row)
                + "</section>"
            )
        if not payload["results"]:
            content = "<p>No matching player records.</p>"
    elif kind == "player_recurrence":
        content = (
            _summary(payload)
            + "<h2>Chronological batting-game observations</h2>"
            + _table(
                [
                    "Game UUID",
                    "Official date",
                    "Historical represented teams",
                    "PA",
                    "HR",
                ],
                [
                    (
                        item["game_id"],
                        item["official_date"],
                        ", ".join(
                            team["display_name"] or team["id"]
                            for team in item["represented_teams"]
                        ),
                        metric_text(item["pa"]),
                        metric_text(item["hr"]),
                    )
                    for item in payload["observations"]
                ],
            )
            + "<h2>HR gaps: non-HR batting games strictly between endpoints</h2>"
            + _table(
                ["From game UUID", "To game UUID", "Non-HR games"],
                [
                    (
                        item["from_game_id"],
                        item["to_game_id"],
                        metric_text(item["non_hr_games"]),
                    )
                    for item in payload["gaps"]
                ],
            )
        )
    else:
        content = (
            "<h2>Authoritative total_hr: "
            f"{_text(metric_text(payload['total_hr']))}</h2>"
            f"<p>{len(payload['results'])} verified event records; "
            "record count is not the analytical total.</p>"
            + _table(
                [
                    "Event / game / PA UUID",
                    "Official date",
                    "Batter",
                    "Pitcher",
                    "Batting team",
                    "Inning / half / ordinal",
                    "Safe provenance",
                ],
                [
                    (
                        f"{event['id']}\n{event['game_id']}\n{event['plate_appearance_id']}",
                        event["official_date"],
                        event["batter"]["display_name"],
                        (event["pitcher"] or {}).get("display_name", "Unknown"),
                        event["batting_team"]["display_name"],
                        f"{event['inning']} / {event['half_inning']} / "
                        f"{event['game_pa_ordinal']}",
                        _json(event["provenance"]),
                    )
                    for event in payload["results"]
                ],
            )
        )
    css = """
    @page { size: A3 landscape; margin: 12mm;
      @bottom-right { content: 'Page ' counter(page) ' of ' counter(pages);
        font-size: 9pt; }
    }
    body { font-family: sans-serif; font-size: 10pt; color: #17212b; }
    h1 { font-size: 21pt; } h2 { font-size: 14pt; }
    .scope, .legend { font-size: 9pt; overflow-wrap: anywhere; }
    table { width: 100%; border-collapse: collapse; table-layout: fixed;
      margin: 4mm 0; }
    thead { display: table-header-group; }
    th, td { border: .2mm solid #bdc5cd; padding: 2mm;
      vertical-align: top; white-space: pre-wrap;
      overflow-wrap: anywhere; }
    th { background: #e8edf2; text-align: left; }
    tr { break-inside: avoid; }
    .matrix-group { break-before: page; }
    .matrix { font-size: 8pt; }
    .matrix th, .matrix td { padding: 1.3mm; }
    .matrix th:first-child, .matrix td:first-child { width: 31mm; }
    .matrix th:nth-child(2), .matrix td:nth-child(2),
    .matrix th:nth-child(3), .matrix td:nth-child(3)
      { width: 22mm; font-size: 7pt; }
    .player { break-before: page; }
    """
    return (
        f"<!doctype html>"
        f"<html lang='en'>"
        f"<head>"
        f"<meta charset='utf-8'>"
        f"<title>{titles[kind]}</title>"
        f"<style>{css}</style>"
        f"</head>"
        f"<body>{head}{content}</body>"
        f"</html>"
    )


def render_pdf(kind, payload, export_scope, meta):
    from weasyprint import HTML

    def no_external_resources(url, **kwargs):
        raise ValueError("Export templates do not load external resources")

    document = HTML(
        string=render_html(kind, payload, export_scope, meta),
        url_fetcher=no_external_resources,
    ).render()
    return document.write_pdf(), len(document.pages)


class ExportNegotiation(DefaultContentNegotiation):
    def select_renderer(self, request, renderers, format_suffix=None):
        # Binary success responses bypass DRF rendering. Failures are always JSON,
        # including requests accepting text/csv or application/pdf.
        return renderers[0], renderers[0].media_type


class ExportView(ReadOnlyView):
    content_negotiation_class = ExportNegotiation

    # DRF otherwise interprets ?format=csv as a renderer override before validation.
    def get_format_suffix(self, **kwargs):
        return None

    kind = "leaderboard"

    def get(self, request, id=None):
        player_scope = self.kind in (
            "leaderboard",
            "player_recurrence",
            "player_home_runs",
        )
        allowed = (
            _PLAYER_ANALYTICAL_PARAMETERS
            if player_scope
            else _TEAM_ANALYTICAL_PARAMETERS
        )
        extra = (
            {"search", "position", "bats", "ordering"}
            if self.kind == "leaderboard"
            else {"ordering"}
            if self.kind.endswith("home_runs")
            else set()
        )
        _parameters(request, allowed | extra | {"format"})
        format = request.query_params.get("format")
        if format not in ("csv", "pdf"):
            raise ApiProblem(
                "INVALID_FILTER",
                "format=csv or format=pdf is required",
                details={"format": "required csv|pdf"},
            )
        season, window, requested_team, home_away, cutoff = _analytical_inputs(request)
        export_scope = {
            "season": season.year,
            "window": window,
            "home_away": home_away,
            "cutoff": _string(cutoff),
            "team": str(requested_team.id) if requested_team else None,
        }
        if self.kind == "leaderboard":
            export_scope.update(
                {
                    key: request.query_params.get(key)
                    for key in ("search", "position", "bats")
                }
            )
            export_scope["ordering"] = request.query_params.get("ordering", "-hr")
            payload = {"results": player_leaderboard_rows(request)}
        else:
            model = Player if player_scope else Team
            subject = model.objects.filter(pk=_uuid(id, "id", path=True)).first()
            if subject is None:
                raise NotFound()
            export_scope["subject_id"] = str(subject.id)
            selection = (
                _select_player(
                    player=subject,
                    season=season,
                    window=window,
                    team=requested_team,
                    home_away=home_away,
                    cutoff=cutoff,
                )
                if player_scope
                else _select_team(
                    team=subject,
                    season=season,
                    window=window,
                    home_away=home_away,
                    cutoff=cutoff,
                )
            )
            if self.kind.endswith("recurrence"):
                payload = (
                    player_recurrence(subject, selection, requested_team)
                    if player_scope
                    else team_recurrence(subject, selection)
                )
            else:
                ordering = request.query_params.get("ordering", "official_date")
                if ordering not in ("official_date", "-official_date"):
                    raise ApiProblem(
                        "INVALID_FILTER",
                        "Unsupported ordering",
                        details={"ordering": "unsupported"},
                    )
                export_scope["ordering"] = ordering
                events = (
                    player_home_run_events(selection)
                    if player_scope
                    else team_home_run_events(selection)
                )
                order_home_run_events(
                    events, selection, descending=ordering.startswith("-")
                )
                payload = {
                    **home_run_scope(subject, selection, requested_team),
                    "results": public_home_run_events(events),
                }
        meta = self._meta()
        try:
            data, _ = (
                render_csv(self.kind, payload, export_scope, meta)
                if format == "csv"
                else render_pdf(self.kind, payload, export_scope, meta)
            )
        except (ImportError, OSError):
            raise ApiProblem(
                "EXPORT_UNAVAILABLE", "Export rendering is unavailable", status=503
            ) from None
        subject_key = f"{subject.id}-" if id else ""
        name = (
            f"mlb-{self.kind.replace('_', '-')}-{subject_key}"
            f"{season.year}-{window}.{format}"
        )
        response = HttpResponse(
            data,
            content_type="text/csv; charset=utf-8"
            if format == "csv"
            else "application/pdf",
        )
        response["Content-Disposition"] = f'attachment; filename="{name}"'
        response["X-Dataset-Revision"] = meta["dataset_revision"]
        response["X-Data-As-Of"] = meta["data_as_of"]
        response["X-Export-Scope"] = _json(payload.get("scope", export_scope))
        return response
