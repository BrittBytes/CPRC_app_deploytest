# cprc_app/app/components.py
from dash import html, dcc
import dash_bootstrap_components as dbc
from typing import List, Dict
from dash.dash_table import DataTable
from dash.dash_table.Format import Format
from app.theme import THEME, CARD_BASE, PILL_CARD
from app.utils import meta_row

def build_cprc_bubble(meta: dict):
    _m = meta.get("meta") or {}
    return html.Div([
        html.Div("CPRC Overview", style={
            "fontFamily": THEME["font_heading"],
            "fontSize": "12px",
            "letterSpacing": "0.06em",
            "textTransform": "uppercase",
            "opacity": 0.9,
            "marginBottom": "10px",
            "fontWeight": THEME["weight_semibold"],
        }),
        meta_row("Filename", meta.get("file", ""), allow_wrap=False),
        meta_row("Region", meta.get("region", "")),
        meta_row("Customer", meta.get("customer", "")),
        html.Hr(style={"border": "none","height": "1px","background": "rgba(255,255,255,0.25)","margin": "5px 0"}),
        meta_row("Tenant", meta.get("tenant_name", "")),
        meta_row("Tenant ID", meta.get("tenant_id") or meta.get("tenantID", "")),
        meta_row("CPRC Version", _m.get("cprc_version", "")),
        meta_row("CPRC Timestamp", _m.get("formatted_time") or _m.get("cprc_timestamp") or "Unknown"),
    ], style={**CARD_BASE, "position": "sticky","top": "36px","padding": "14px 16px","whiteSpace": "normal",
              "width": "100%","maxWidth": "100%","overflowX": "visible","pointerEvents": "none"})

def build_summary_counts_cards(model: dict):
    esps = model.get("esps", []) or []
    profiles = model.get("profiles", []) or []
    total_esps = len(esps)
    auad_esps = sum(1 for e in esps if (e.get("type") or "").upper() == "AUAD")
    standard_esps = total_esps - auad_esps
    profile_count = len(profiles)
    items = [("AUAD ESPs", auad_esps), ("Standard ESPs", standard_esps), ("Total ESPs", total_esps), ("Autopilot Profiles", profile_count)]
    segments = []
    for i, (label, value) in enumerate(items):
        segments.append(html.Div([
            html.Div(label, style={"fontFamily": THEME["font_heading"], "fontSize": "12px","fontWeight": THEME["weight_semibold"],"letterSpacing": "0.02em","opacity": 0.85}),
            html.Div(str(value), style={"fontFamily": THEME["font_body"], "fontSize": "22px","fontWeight": THEME["weight_semibold"],"lineHeight": "1"}),
        ], style={**PILL_CARD,"width": "100%","display": "flex","flexDirection": "column","alignItems": "center",
                  "justifyContent": "center","padding": "8px 14px","borderLeft": "1px solid rgba(255,255,255,0.28)" if i>0 else "none"}))
    return dbc.Card(dbc.CardBody(html.Div(segments, style={"display": "flex","flexWrap": "nowrap","gap": "12px","alignItems": "stretch"})), id="summary-cards", style=PILL_CARD)

def build_applications_section(model: dict):
    """
    Applications table with smart columns:
      Name, ID, Source, Publisher, Version, Type, Assignment, Platform, Category,
      Install Behavior, Size, Created, Last Modified, Published
    + all remaining metadata exposed as meta.<key> columns.
    A details panel placeholder is provided below the table (id='apps-details').
    """
    rows: List[Dict] = model.get("applications") or []
    if not rows:
        return html.Div("No application data found in the uploaded file.", style={**CARD_BASE, "padding": "12px"})

    # ---- Field alias maps for common attributes found across CPRC exports ----
    ALIASES = {
        "publisher": {"publisher","appPublisher","developer","vendor","Publisher","Developer","Vendor","PublisherName"},
        "version": {"version","displayVersion","appVersion","productVersion","Version"},
        "type": {"type","app_type","applicationType","install_type","contentType","AppType","InstallType"},
        "assignment": {"assignment","intent","deploymentIntent","DeploymentIntent","Assignment","InstallIntent"},
        "platform": {"platform","os","osType","OS","Platform","TargetOS"},
        "category": {"category","appCategory","Category"},
        "install_behavior": {"installBehavior","executionContext","deviceContext","userContext","ctx","InstallBehavior","RunAsAccount"},
        "size": {"size","contentSize","packageSizeBytes","PackageSize","ContentSize","TotalContentSize"},
        # dates
        "created": {"created","createdDateTime","dateCreated","Created","CreatedOn"},
        "last_modified": {"modified","lastModified","lastUpdated","updatedAt","Modified","Updated","LastModifiedDateTime"},
        "published": {"published","publishDate","Published","ReleaseDate","releaseDate"},
        # useful extras
        "detection": {"detection","detectionRule","detectionRules","DetectionRules"},
        "requirements": {"requirements","requirementRules","Requirements"},
    }

    def pick(meta: dict, keyname: str):
        if not isinstance(meta, dict): return None
        for k in ALIASES.get(keyname, ()):
            if k in meta and meta[k] not in (None, "", []):
                return meta[k]
        return None

    def fmt_size(v):
        try:
            n = float(v)
            for unit in ["B","KB","MB","GB","TB"]:
                if n < 1024:
                    return f"{n:.0f} {unit}"
                n /= 1024
        except Exception:
            pass
        return v

    # Best-effort datetime parsing
    def fmt_date(v):
        from datetime import datetime
        if v in (None, "", [], {}): return None
        s = str(v).strip()
        try_formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",  "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",     "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%m/%d/%Y %H:%M:%S",     "%m/%d/%Y %H:%M", "%m/%d/%Y",
        ]
        import re
        m = re.match(r"^/Date\((\d+)\)/$", s)  # MS JSON date
        if m:
            try:
                epoch_ms = int(m.group(1))
                dt = datetime.utcfromtimestamp(epoch_ms / 1000.0)
                return dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                return s
        for f in try_formats:
            try:
                dt = datetime.strptime(s, f)
                # if midnight, show date only
                if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
                    return dt.strftime("%Y-%m-%d")
                return dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                continue
        return s  # fallback raw

    # Canonical columns we always try to show (includes dates)
    base_cols = [
        "name", "id", "source",
        "publisher", "version", "type", "assignment",
        "platform", "category", "install_behavior", "size",
        "created", "last_modified", "published",
    ]

    # Build records and collect extra meta keys
    data = []
    extra_keys = set()
    alias_flat = set().union(*ALIASES.values())

    for r in rows:
        meta = (r.get("meta") or {})
        rec = {
            "name": r.get("name"),
            "id": r.get("id"),
            "source": r.get("source"),
            "publisher": pick(meta, "publisher"),
            "version": pick(meta, "version"),
            "type": r.get("type") or pick(meta, "type"),
            "assignment": pick(meta, "assignment"),
            "platform": pick(meta, "platform"),
            "category": pick(meta, "category"),
            "install_behavior": pick(meta, "install_behavior"),
            "size": fmt_size(pick(meta, "size")),
            "created": fmt_date(pick(meta, "created")),
            "last_modified": fmt_date(pick(meta, "last_modified")),
            "published": fmt_date(pick(meta, "published")),
        }

        # discover extra meta keys to expose as meta.<key> columns
        for k in meta.keys():
            if k in alias_flat:
                continue
            extra_keys.add(k)

        rec["_meta_raw"] = meta  # for projecting extras
        data.append(rec)

    extra_cols_sorted = sorted(extra_keys)
    all_cols = base_cols + [f"meta.{k}" for k in extra_cols_sorted]

    # project extra meta.* values into row cells (format anything that smells like a date)
    for rec in data:
        meta = rec.pop("_meta_raw", {})
        for k in extra_cols_sorted:
            val = meta.get(k)
            if isinstance(val, (str, int)) and any(x in str(val) for x in ["-", ":", "T", "/", "Date("]):
                rec[f"meta.{k}"] = fmt_date(val)
            else:
                rec[f"meta.{k}"] = val

    columns_spec = (
        [
            {"name": "Name", "id": "name"},
            {"name": "ID", "id": "id"},
            {"name": "Source", "id": "source"},
            {"name": "Publisher", "id": "publisher"},
            {"name": "Version", "id": "version"},
            {"name": "Type", "id": "type"},
            {"name": "Assignment", "id": "assignment"},
            {"name": "Platform", "id": "platform"},
            {"name": "Category", "id": "category"},
            {"name": "Install Behavior", "id": "install_behavior"},
            {"name": "Size", "id": "size"},
            {"name": "Created", "id": "created"},
            {"name": "Last Modified", "id": "last_modified"},
            {"name": "Published", "id": "published"},
        ]
        + [{"name": f"meta.{k}", "id": f"meta.{k}"} for k in extra_cols_sorted]
    )

    # Tooltips optional—keeping them for long text, but dates are shown in cells
    tooltip_data = []
    for rec in data:
        tips = {}
        for c in all_cols:
            val = rec.get(c)
            if val in (None, ""):
                continue
            s = str(val)
            tips[c] = {"value": s if len(s) <= 300 else (s[:300] + "…"), "type": "text"}
        tooltip_data.append(tips)

    return html.Div(
        [
            html.H4("Applications", style={"margin": "0 0 12px 0"}),
            DataTable(
                id="apps-table",
                data=data,
                columns=columns_spec,
                sort_action="native",
                filter_action="native",
                page_action="native",
                page_size=20,
                row_selectable="single",
                tooltip_data=tooltip_data,
                style_table={"overflowX": "auto"},
                style_header={
                    "backgroundColor": "#0b2a44",
                    "color": "#fff",
                    "fontWeight": "600",
                    "border": "1px solid rgba(255,255,255,0.15)",
                },
                style_cell={
                    "backgroundColor": "#00223E",
                    "color": "#B2DCFF",
                    "border": "1px solid rgba(255,255,255,0.08)",
                    "fontSize": "13px",
                    "padding": "8px",
                    "whiteSpace": "normal",
                    "height": "auto",
                },
                style_data_conditional=[
                    {
                        "if": {"filter_query": "{assignment} contains 'Required' || {assignment} contains 'required'"},
                        "fontWeight": "700",
                    }
                ],
            ),
            # Details panel populated by callbacks.py when a row is selected
            html.Div(id="apps-details", style={"marginTop": "12px"}),
        ],
        style={**CARD_BASE, "padding": "16px"},
    )


def build_app_layout():
    """Top bar + sticky tabs. Both pages are mounted and visibility toggled via callbacks."""
    tab_style = {
        "padding": "8px 14px",
        "background": "rgba(0,0,0,0.15)",
        "color": THEME["on_dark"],
        "border": "1px solid rgba(255,255,255,0.12)",
        "borderBottom": "none",
        "marginRight": "8px",
        "borderTopLeftRadius": "10px",
        "borderTopRightRadius": "10px",
        "fontWeight": 600,
    }
    selected_tab_style = {**tab_style, "background": "#0b2a44", "borderColor": "rgba(255,255,255,0.28)"}

    return html.Div(
        [
            # Persist model + filename for the whole session
            dcc.Store(id="memory-output", storage_type="session"),
            dcc.Store(id="file-name", storage_type="session"),

            # App bar
            html.Div(
                [
                    html.Div(
                        "CPRC Report App",
                        style={
                            "fontFamily": THEME["font_heading"],
                            "fontWeight": THEME["weight_extrabold"],
                            "fontSize": "20px",
                            "letterSpacing": ".02em",
                        },
                    ),
                    html.Div(
                        [
                            html.Span("Current XML file: ", style={"opacity": 0.8}),
                            html.Span(id="current-file-label", style={"fontWeight": 600}),
                            dcc.Upload(
                                id="upload-data",
                                children=html.Button("Upload file", style={
                                    "padding": "6px 10px",
                                    "borderRadius": "8px",
                                    "border": "1px solid rgba(255,255,255,0.2)",
                                    "background": "#124268",
                                    "color": THEME["on_dark"],
                                    "cursor": "pointer",
                                    "marginLeft": "10px",
                                }),
                                multiple=False,
                                style={"display": "inline-block"},
                            ),
                        ],
                        style={"display": "flex", "alignItems": "center", "gap": "6px"},
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "padding": "10px 12px",
                    "position": "sticky",
                    "top": 0,
                    "zIndex": 3,
                    "background": THEME["dark_blue_bg"],
                    "borderBottom": THEME["border_subtle"],
                },
            ),

            # Tabs
            dcc.Tabs(
                id="tabs",
                value="overview",
                persistence=True,
                persistence_type="session",
                style={"background": "transparent", "position": "sticky", "top": 48, "zIndex": 2},
                children=[
                    dcc.Tab(label="Overview", value="overview", style=tab_style, selected_style=selected_tab_style),
                    dcc.Tab(label="Applications", value="apps", style=tab_style, selected_style=selected_tab_style),
                ],
            ),

            # Pages (both mounted; visibility toggled)
            html.Div(
                [
                    html.Div(id="overview-page", children=build_overview_section()),
                    html.Div(id="apps-page", style={"display": "none"}),
                ],
                id="page-body",
                style={"padding": "12px"},
            ),
        ],
        style={"minHeight": "100vh", "background": THEME["dark_blue_bg"], "color": THEME["on_dark"]},
    )

def build_overview_section():
    """Two-column overview; Cytoscape column stays mounted across tab switches."""
    return html.Div(
        [
            html.Div(
                [
                    html.Div(id="output-cprc-overview", style={"paddingTop": "8px"}),
                    html.Div(id="output-tenant-counts-overview", style={"marginTop": "12px"}),
                    html.Div(
                        id="cyto-info",
                        style={"marginTop": "8px", "flex": "1 1 auto", "minHeight": 0, "overflowY": "auto"},
                    ),
                ],
                style={
                    "position": "sticky",
                    "top": "96px",  # below app bar + tabs
                    "alignSelf": "start",
                    "display": "flex",
                    "flexDirection": "column",
                    "height": "calc(100vh - 120px)",
                    "width": "fit-content",
                },
            ),
            html.Div(id="cyto-col", style={"paddingLeft": "24px", "height": "100%"}),
        ],
        style={
            "display": "grid",
            "gridTemplateColumns": "380px 1fr",
            "gap": "12px",
            "alignItems": "start",
            "height": "calc(100vh - 120px)",
            "overflow": "hidden",
        },
    )
