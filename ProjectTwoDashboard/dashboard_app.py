"""Grazioso Salvare rescue-animal dashboard, CS-340 Project Two.

Run this file for a standalone Dash server, or open ProjectTwoDashboard.ipynb
in Codio/JupyterLab. All displayed animals come from the aac.animals database.
"""

import base64
import math
import os
import re
from datetime import date, datetime
from pathlib import Path

import dash_leaflet as dl
import plotly.graph_objects as go
from dash import Dash, Input, Output, ctx, dash_table, dcc, html

from CRUD_Python_Module import AnimalShelter


# These are the course-provided dashboard credentials required by
# the project. AnimalShelter authenticates against admin, not the aac database.
USERNAME = "aacuser"
PASSWORD = "12345"
IDENTIFIER = "Illia Levchenko | ilevchenko691082235"
LOGO_FILE = "Grazioso Salvare Logo.png"

RESCUE_FILTERS = {
    "water": {
        "label": "Water Rescue",
        "breeds": ["Labrador Retriever Mix", "Chesapeake Bay Retriever", "Newfoundland"],
        "sex": "Intact Female",
        "minimum": 26,
        "maximum": 156,
        "description": "Water breeds · intact females · 26–156 weeks",
    },
    "mountain": {
        "label": "Mountain / Wilderness Rescue",
        "breeds": ["German Shepherd", "Alaskan Malamute", "Old English Sheepdog", "Siberian Husky", "Rottweiler"],
        "sex": "Intact Male",
        "minimum": 26,
        "maximum": 156,
        "description": "Mountain and wilderness breeds · intact males · 26–156 weeks",
    },
    "disaster": {
        "label": "Disaster / Individual Tracking",
        "breeds": ["Doberman Pinscher", "German Shepherd", "Golden Retriever", "Bloodhound", "Rottweiler"],
        "sex": "Intact Male",
        "minimum": 20,
        "maximum": 300,
        "description": "Tracking breeds · intact males · 20–300 weeks",
    },
}

COLORS = ["#107F8A", "#E6A548", "#526FAB", "#78A76E", "#C67565", "#806CA8", "#46A2B0", "#A68A52", "#69878C", "#A77498", "#CFD6DC"]
PANEL = {"backgroundColor": "white", "border": "1px solid #DDE5EB", "borderRadius": "10px", "overflow": "hidden"}
HEADING = {"fontSize": "16px", "fontWeight": "700", "margin": "0", "color": "#17324D"}


def build_query(category):
    """Build inclusive MongoDB rescue rules; reset returns every document.

    Breed boundaries permit Mix and slash-separated crosses, without matching
    a breed name embedded inside an unrelated word. Labrador Retriever Mix
    remains the exact Water Rescue breed phrase specified by the rubric.
    """
    if category == "all":
        return {}
    if category not in RESCUE_FILTERS:
        raise ValueError("Unknown rescue category.")
    rule = RESCUE_FILTERS[category]
    breed_pattern = r"\b(?:" + "|".join(re.escape(breed) for breed in rule["breeds"]) + r")\b"
    return {
        "animal_type": "Dog",
        "breed": {"$regex": breed_pattern, "$options": "i"},
        "sex_upon_outcome": rule["sex"],
        "age_upon_outcome_in_weeks": {"$gte": rule["minimum"], "$lte": rule["maximum"]},
    }


def json_value(value):
    """Convert MongoDB values to strict JSON values understood by Dash."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return str(value)


def normalize_records(documents):
    """Preserve each MongoDB _id as both a string and a stable Dash row ID."""
    records = []
    for document in documents:
        if "_id" not in document:
            raise ValueError("An animal document is missing its MongoDB identity.")
        record = {str(key): json_value(value) for key, value in document.items()}
        record["_id"] = str(document["_id"])
        record["id"] = record["_id"]
        records.append(record)
    return records


def load_records(category, shelter_factory=AnimalShelter):
    """Read through the reused CRUD module and surface database failures.

    The prior module intentionally returns [] on read errors. Verify an empty
    result directly against the same query so a failed read cannot silently
    appear as a successful zero-result filter. No synthetic fallback is used.
    """
    shelter = shelter_factory(USERNAME, PASSWORD, auth_source="admin")
    try:
        query = build_query(category)
        documents = shelter.read(query)
        if not documents and shelter.collection.count_documents(query) != 0:
            raise RuntimeError("The database contains results, but the CRUD read did not return them.")
        return normalize_records(documents)
    finally:
        shelter.close()


def valid_coordinates(record):
    """Return a usable (latitude, longitude), or None for missing/invalid data."""
    try:
        latitude = float(record.get("location_lat"))
        longitude = float(record.get("location_long"))
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(latitude) and math.isfinite(longitude)):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return latitude, longitude


def select_record(records, selected_ids):
    """Resolve selection by identity; fall back to the first filtered row."""
    selected = set(selected_ids or [])
    for record in records:
        if record.get("id") in selected:
            return record
    return records[0] if records else None


def breed_counts(records, limit=10):
    """Summarize the current table view, retaining a total-preserving Other."""
    counts = {}
    for record in records:
        breed = str(record.get("breed") or "Unknown breed")
        counts[breed] = counts.get(breed, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))
    if len(ranked) > limit:
        return ranked[:limit] + [("Other breeds", sum(count for _, count in ranked[limit:]))]
    return ranked


def breed_figure(records, unavailable=False):
    """Build a legible breed chart for all filtered rows, across table pages."""
    counts = breed_counts(records)
    figure = go.Figure()
    if counts:
        figure.add_trace(go.Pie(
            labels=[label for label, _ in counts],
            values=[count for _, count in counts],
            hole=0.64,
            sort=False,
            textinfo="none",
            marker={"colors": COLORS, "line": {"color": "white", "width": 2}},
            hovertemplate="%{label}<br>%{value:,} animals · %{percent}<extra></extra>",
        ))
        figure.add_annotation(x=0.5, y=0.5, xref="paper", yref="paper", text="<b>{:,}</b><br>animals".format(len(records)), showarrow=False, font={"size": 18, "color": "#17324D"})
    else:
        figure.add_annotation(text="Database unavailable. See the message above." if unavailable else "No animals match this view.", x=0.5, y=0.5, showarrow=False, font={"size": 15, "color": "#617487"})
    figure.update_layout(
        height=265,
        margin={"l": 10, "r": 10, "t": 8, "b": 8},
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={"family": "Arial, sans-serif", "color": "#17324D", "size": 11},
        legend={"orientation": "v", "x": 1.01, "y": 0.5, "yanchor": "middle", "font": {"size": 10}},
        showlegend=bool(counts),
    )
    if not counts:
        figure.update_xaxes(visible=False)
        figure.update_yaxes(visible=False)
    return figure


def map_content(records, selected_ids):
    """Show the selected animal using named coordinate fields and safe fallbacks."""
    record = select_record(records, selected_ids)
    coordinates = valid_coordinates(record) if record else None
    if record is None:
        message = "No animals match this view. Change the rescue or column filters."
    elif coordinates is None:
        message = "{} · {} — this animal has no valid location coordinates.".format(record.get("animal_id") or "Animal", record.get("name") or "Unnamed")
    else:
        message = "{} · {} · {}".format(record.get("animal_id") or "Animal", record.get("name") or "Unnamed", record.get("breed") or "Unknown breed")
    layers = [dl.TileLayer(attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors')]
    if coordinates is not None:
        layers.append(dl.Marker(
            position=list(coordinates),
            children=[
                dl.Tooltip(str(record.get("name") or record.get("animal_id") or "Selected animal")),
                dl.Popup([
                    html.Strong(str(record.get("name") or "Unnamed animal")),
                    html.P(str(record.get("animal_id") or "")),
                    html.P(str(record.get("breed") or "Unknown breed")),
                ]),
            ],
        ))
    return html.Div([
        html.Div(message, style={"fontSize": "12px", "color": "#536B80", "height": "30px", "padding": "0 14px", "overflow": "hidden"}),
        dl.Map(children=layers, center=list(coordinates) if coordinates else [30.2672, -97.7431], zoom=11 if coordinates else 9, style={"height": "235px", "width": "100%"}),
    ])


def logo_source():
    """Embed the supplied logo so script and notebook use the same local file."""
    folder = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
    logo = folder / LOGO_FILE
    if not logo.is_file():
        raise FileNotFoundError("Place '{}' beside the dashboard before running it.".format(LOGO_FILE))
    return "data:image/png;base64," + base64.b64encode(logo.read_bytes()).decode("ascii")


def table_columns(records):
    """Show useful decision fields first; retain remaining source fields to the right."""
    preferred = ["animal_id", "name", "breed", "sex_upon_outcome", "age_upon_outcome_in_weeks", "animal_type", "outcome_type", "color", "datetime"]
    found = set().union(*(record.keys() for record in records)) if records else set(preferred)
    fields = [field for field in preferred if field in found]
    fields += sorted(found - set(fields) - {"_id", "id"})
    labels = {"animal_id": "Animal ID", "name": "Name", "breed": "Breed", "sex_upon_outcome": "Sex / status", "age_upon_outcome_in_weeks": "Age (weeks)", "animal_type": "Animal type", "outcome_type": "Outcome", "color": "Color", "datetime": "Outcome date"}
    numeric = {"age_upon_outcome_in_weeks", "location_lat", "location_long", "rec_num"}
    return [{"name": labels.get(field, field.replace("_", " ").title()), "id": field, "type": "numeric" if field in numeric else "text"} for field in fields]


def create_app(notebook=False):
    """Create and wire the dashboard; importing this module never contacts MongoDB."""
    if notebook:
        from jupyter_dash import JupyterDash
        JupyterDash.infer_jupyter_proxy_config()
        app = JupyterDash("ProjectTwoDashboard")
    else:
        app = Dash(__name__)
    app.title = "Grazioso Salvare | Rescue Dashboard"
    try:
        records = load_records("all")
        error = ""
    except Exception as exc:
        records = []
        error = "Database unavailable. Confirm MongoDB is running and the course account can read aac.animals. ({})".format(type(exc).__name__)

    app.layout = html.Div([
        html.Header([
            html.A(html.Img(src=logo_source(), alt="Grazioso Salvare rescue-animal logo", style={"width": "84px", "height": "76px", "objectFit": "contain", "backgroundColor": "white", "borderRadius": "7px"}), href="https://www.snhu.edu", target="_blank", title="Visit Southern New Hampshire University"),
            html.Div([
                html.Div("GRAZIOSO SALVARE", style={"fontSize": "12px", "letterSpacing": "2px", "color": "#74D4D3", "fontWeight": "700"}),
                html.H1("Find the next rescue partner", style={"margin": "4px 0", "fontSize": "25px", "fontWeight": "700"}),
                html.Div("Austin Animal Center · Search, compare, and locate rescue candidates", style={"fontSize": "12px", "color": "#CFDAE5"}),
            ], style={"flex": "1"}),
            html.Div([html.Div("CS-340 · PROJECT TWO", style={"fontSize": "11px", "letterSpacing": "1px", "color": "#B6CCDC"}), html.Div(IDENTIFIER, style={"fontSize": "12px", "marginTop": "7px"})], style={"textAlign": "right"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "18px", "padding": "12px 20px", "backgroundColor": "#17324D", "color": "white", "borderRadius": "12px"}),

        html.Section([
            html.Div([dcc.RadioItems(
                id="rescue-filter",
                options=[{"label": " All animals", "value": "all"}] + [{"label": " " + rule["label"], "value": key} for key, rule in RESCUE_FILTERS.items()],
                value="all",
                inline=True,
                inputStyle={"marginRight": "4px", "accentColor": "#107F8A"},
                labelStyle={"display": "inline-block", "padding": "10px 14px", "marginRight": "9px", "backgroundColor": "#EAF2F5", "borderRadius": "6px", "cursor": "pointer", "fontSize": "13px", "fontWeight": "600"},
            ), html.Button("Reset all", id="reset-all", n_clicks=0, title="Clear every rescue and column filter and reset sorting", style={"backgroundColor": "#107F8A", "color": "white", "border": "none", "borderRadius": "6px", "fontSize": "12px", "fontWeight": "700", "padding": "10px 17px", "cursor": "pointer"})], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "gap": "10px"}),
            html.Div(id="filter-description", children="All shelter animals · Choose a rescue type to apply breed, sex, and age requirements", style={"marginTop": "8px", "fontSize": "12px", "color": "#536B80"}),
        ], style={"padding": "12px 0 10px"}),
        html.Div(id="database-error", children=error, role="alert", style={"color": "#A22828", "fontWeight": "600", "fontSize": "13px", "paddingBottom": "5px"}),

        html.Section([
            html.Div([
                html.H2("Animal candidates", style=HEADING),
                html.Span(id="result-count", style={"fontSize": "12px", "color": "#536B80"}),
            ], style={"display": "flex", "justifyContent": "space-between", "padding": "11px 14px 6px"}),
            html.Div("Filter columns, sort headers, or select a row to map it. With no visible selection, the map shows the first match. Scroll sideways for all fields.", style={"fontSize": "11px", "color": "#64788A", "padding": "0 14px 7px"}),
            dash_table.DataTable(
                id="animal-table",
                columns=table_columns(records),
                data=records,
                row_selectable="single",
                selected_rows=[0] if records else [],
                selected_row_ids=[records[0]["id"]] if records else [],
                page_action="native",
                page_size=5,
                page_current=0,
                sort_action="native",
                sort_mode="multi",
                filter_action="native",
                filter_options={"case": "insensitive"},
                style_table={"overflowX": "auto"},
                style_cell={"fontFamily": "Arial, sans-serif", "fontSize": "12px", "textAlign": "left", "padding": "7px 9px", "minWidth": "110px", "maxWidth": "240px", "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap", "border": "1px solid #E7EDF1", "color": "#263F55"},
                style_cell_conditional=[{"if": {"column_id": "breed"}, "minWidth": "225px", "width": "260px"}, {"if": {"column_id": "age_upon_outcome_in_weeks"}, "width": "120px", "textAlign": "right"}],
                style_header={"fontWeight": "700", "backgroundColor": "#EDF3F7", "color": "#17324D"},
                style_filter={"backgroundColor": "#F9FBFC", "fontSize": "11px"},
                style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#F8FAFC"}, {"if": {"state": "selected"}, "backgroundColor": "#DBF1EF", "border": "1px solid #107F8A"}],
            ),
        ], style=PANEL),

        html.Div([
            html.Section([html.H2("Breed distribution", style=dict(HEADING, padding="12px 14px 2px")), dcc.Graph(id="breed-chart", figure=breed_figure(records, bool(error)), config={"displayModeBar": False, "responsive": True}, style={"height": "265px"})], style=dict(PANEL, flex="1", minWidth="0")),
            html.Section([html.H2("Selected animal location", style=dict(HEADING, padding="12px 14px 8px")), html.Div(id="animal-map", children=html.Div("Location unavailable until the database connection is restored.", style={"padding": "14px"}) if error else map_content(records, [records[0]["id"]] if records else []))], style=dict(PANEL, flex="1", minWidth="0")),
        ], style={"display": "flex", "gap": "12px", "marginTop": "12px"}),
        html.Footer("Live MongoDB records · Charts reflect all rows in the filtered table, across pages · Ages are inclusive · Breed crosses and mixes are included", style={"fontSize": "10px", "color": "#64788A", "padding": "8px 2px 0"}),
    ], style={"fontFamily": "Arial, sans-serif", "backgroundColor": "#F3F6F8", "padding": "14px 18px", "minHeight": "100vh", "boxSizing": "border-box", "color": "#17324D"})

    @app.callback(
        Output("animal-table", "data"),
        Output("animal-table", "selected_row_ids"),
        Output("animal-table", "selected_rows"),
        Output("animal-table", "page_current"),
        Output("animal-table", "filter_query"),
        Output("animal-table", "sort_by"),
        Output("filter-description", "children"),
        Output("database-error", "children"),
        Output("rescue-filter", "value"),
        Input("rescue-filter", "value"),
        Input("reset-all", "n_clicks"),
        prevent_initial_call=True,
    )
    def change_category(category, reset_clicks):
        if ctx.triggered_id == "reset-all":
            category = "all"
        description = RESCUE_FILTERS[category]["description"] if category in RESCUE_FILTERS else "All shelter animals · Rescue, column filters, and sorting have been reset"
        try:
            filtered = load_records(category)
            message = ""
        except Exception as exc:
            filtered = []
            message = "Database query failed. Restore the MongoDB connection, then choose a filter to retry. ({})".format(type(exc).__name__)
        return filtered, [filtered[0]["id"]] if filtered else [], [0] if filtered else [], 0, "", [], description, message, category

    @app.callback(
        Output("breed-chart", "figure"),
        Output("animal-map", "children"),
        Output("result-count", "children"),
        Input("animal-table", "derived_virtual_data"),
        Input("animal-table", "selected_row_ids"),
        Input("animal-table", "data"),
        Input("database-error", "children"),
    )
    def update_visuals(visible_data, selected_ids, table_data, database_error):
        # None means DataTable has not produced its first derived view yet.
        # An empty list is a real empty filter result and must remain empty.
        visible = table_data if visible_data is None else visible_data
        visible = visible or []
        count = "Data unavailable — see database message" if database_error else "{:,} shown / {:,} in category".format(len(visible), len(table_data or []))
        location = html.Div("Location unavailable until the database connection is restored.", style={"padding": "14px"}) if database_error else map_content(visible, selected_ids)
        return breed_figure(visible, bool(database_error)), location, count

    return app


if __name__ == "__main__":
    create_app().run_server(host="0.0.0.0", port=int(os.environ.get("PORT", "8052")), debug=False)
