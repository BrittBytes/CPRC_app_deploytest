# cprc_app/app/callbacks.py
import xmltodict
from dash import html, Input, Output, State, no_update
import dash
import dash_cytoscape as cyto

from app.utils import decode_xml_contents, json_safe, clean_id_text
from app.model import build_model
from app.theme import CARD_BASE
from app.cyto import build_cytoscape_elements
from app.components import (
    build_cprc_bubble,
    build_summary_counts_cards,
    build_applications_section,
)

def register_callbacks(app: dash.Dash):

    # --- Tab visibility toggle (keep both pages mounted) ---
    @app.callback(
        Output("overview-page", "style"),
        Output("apps-page", "style"),
        Input("tabs", "value"),
        prevent_initial_call=False,
    )
    def _toggle_pages(tab):
        if tab == "apps":
            return {"display": "none"}, {"display": "block"}
        return {"display": "block"}, {"display": "none"}

    # --- Show current file name in app bar (session persistent) ---
    @app.callback(
        Output("current-file-label", "children"),
        Input("file-name", "data"),
        prevent_initial_call=False,
    )
    def _show_filename(name):
        return name or "(none)"

    # --- File upload -> parse -> model -> render overview widgets + cyto; persist model + filename ---
    @app.callback(
        Output("memory-output", "data"),                # session store
        Output("file-name", "data"),                    # session store
        Output("output-cprc-overview", "children"),
        Output("output-tenant-counts-overview", "children"),
        Output("cyto-col", "children"),
        Input("upload-data", "contents"),
        State("upload-data", "filename"),
        prevent_initial_call=True,
    )
    def process_upload(contents, filename):
        if not contents:
            return no_update, no_update, "No file uploaded", no_update, no_update
        try:
            raw_bytes = decode_xml_contents(contents)
            xml_str = raw_bytes.decode("utf-8", errors="replace")
            doc = xmltodict.parse(xml_str)

            from classes.xml_processor import XMLProcessor
            processor = XMLProcessor(doc)
            model = build_model(filename or "", processor, doc)

            bubble = build_cprc_bubble(model)
            tenant_counts_card = build_summary_counts_cards(model)
            model_clean = json_safe(model)

            cyto_component = cyto.Cytoscape(
                id="cyto-map",
                layout={"name": "preset"},
                style={
                    "width": "100%",
                    "height": "100%",
                    "boxSizing": "border-box",
                    "overflow": "hidden",
                    "backgroundColor": "#00223E",
                    "boxShadow": "0 8px 24px rgba(0,0,0,0.2)",
                    "border": "1px solid rgba(255,255,255,0.12)",
                    "borderRadius": "12px",
                    "padding": "26px",
                },
                elements=build_cytoscape_elements(model),
                stylesheet=[
                    {"selector": ".profile", "style": {
                        "background-color": "#1f6feb",
                        "label": "data(label)",
                        "color": "#ffffff",
                        "font-size": "8px",
                        "text-wrap": "wrap",
                        "text-max-width": 180,
                        "shape": "round-rectangle",
                        "width": 160,
                        "height": 60,
                        "text-valign": "center",
                        "text-halign": "center",
                        "text-margin-y": 0,
                        "text-outline-color": "#00223E",
                        "text-outline-width": 2,
                    }},
                    {"selector": ".group", "style": {
                        "background-color": "#10b981",
                        "label": "data(label)",
                        "color": "#ffffff",
                        "font-size": "8px",
                        "text-wrap": "wrap",
                        "text-max-width": 180,
                        "shape": "round-rectangle",
                        "width": 160,
                        "height": 60,
                        "text-valign": "center",
                        "text-halign": "center",
                        "text-margin-y": 0,
                        "text-outline-color": "#00223E",
                        "text-outline-width": 2,
                    }},
                    {"selector": ".esp", "style": {
                        "background-color": "#7c3aed",
                        "label": "data(label)",
                        "color": "#ffffff",
                        "font-size": "8px",
                        "text-wrap": "wrap",
                        "text-max-width": 200,
                        "shape": "round-rectangle",
                        "width": 160,
                        "height": 60,
                        "text-valign": "center",
                        "text-halign": "center",
                        "text-margin-y": 0,
                        "text-outline-color": "#00223E",
                        "text-outline-width": 2,
                    }},
                    {"selector": "edge", "style": {
                        "line-color": "#b3b3b3",
                        "width": 3,
                        "curve-style": "bezier",
                        "target-arrow-shape": "vee",
                        "target-arrow-color": "#b3b3b3",
                    }},
                    {"selector": "edge:hover", "style": {
                        "line-color": "#ffffff",
                        "target-arrow-color": "#ffffff",
                        "width": 4,
                    }},
                ],
            )

            # Persist model + filename; re-render overview widgets; leave apps page to its own callback
            return (model_clean, filename or "", html.Div([bubble]), tenant_counts_card, cyto_component)

        except Exception as e:
            return (
                no_update,
                no_update,
                html.Div([html.Hr(), html.H4("Error processing XML"), html.Pre(str(e))], style={"color": "red"}),
                no_update,
                no_update,
            )

    # --- Fill Applications page from stored model (mounted, no unmount on tab switch) ---
    @app.callback(
        Output("apps-page", "children"),
        Input("memory-output", "data"),
        prevent_initial_call=False,
    )
    def _render_apps(model):
        if not model:
            return html.Div(
                "Upload a CPRC XML on the Overview tab to see applications.",
                style={"opacity": 0.85},
            )
        return build_applications_section(model)

    # --- Applications row -> details panel (works with sorting/filtering) ---
    @app.callback(
        Output("apps-details", "children"),
        Input("apps-table", "derived_virtual_selected_rows"),
        State("apps-table", "derived_virtual_data"),
        prevent_initial_call=False,
    )
    def _show_app_details(selected_rows, current_data):
        if not current_data:
            return html.Div("No application selected.", style={"opacity": 0.8})

        idx = None
        if isinstance(selected_rows, list) and selected_rows:
            idx = selected_rows[0]

        if idx is None or idx < 0 or idx >= len(current_data):
            return html.Div("Select an application to see details.", style={"opacity": 0.8})

        rec = current_data[idx]

        def row(lbl, key):
            return html.Div(
                [
                    html.Div(lbl, style={"opacity":0.8}),
                    html.Div(rec.get(key) or "—", style={"fontWeight":600}),
                ],
                style={"display":"grid","gridTemplateColumns":"180px 1fr","gap":"8px","marginBottom":"6px"}
            )

        summary_rows = [
            row("Name", "name"),
            row("ID", "id"),
            row("Source", "source"),
            row("Publisher", "publisher"),
            row("Version", "version"),
            row("Type", "type"),
            row("Assignment", "assignment"),
            row("Platform", "platform"),
            row("Category", "category"),
            row("Install Behavior", "install_behavior"),
            row("Size", "size"),
            row("Last Modified", "last_modified"),
        ]

        # Gather any extra meta.* columns present for this row
        extra_meta = {k.replace("meta.","",1): v for k, v in rec.items() if k.startswith("meta.") and v not in (None, "")}

        return html.Div(
            [
                html.Div("Application details", style={"fontWeight":700, "marginBottom":"8px"}),
                html.Div(summary_rows, style={**CARD_BASE, "padding":"12px", "marginBottom":"10px"}),
                html.Details([
                    html.Summary("Raw metadata"),
                    html.Pre(
                        json_safe(extra_meta),
                        style={
                            "background":"#00182b",
                            "padding":"10px",
                            "borderRadius":"8px",
                            "whiteSpace":"pre-wrap",
                            "wordBreak":"break-word",
                            "marginTop":"8px"
                        }
                    )
                ], style={**CARD_BASE, "padding":"10px"})
            ]
        )

    # --- Node details panel ---
    @app.callback(
        Output("cyto-info", "children"),
        Input("cyto-map", "tapNodeData"),
        State("memory-output", "data"),
        prevent_initial_call=True,
    )
    def show_node_info(node_data, stored_model):
        if not node_data:
            return no_update

        def row(lbl, val):
            if isinstance(val, (list, tuple)):
                val = ", ".join([str(x) for x in val if x is not None])
            return html.Div(
                [
                    html.Div(
                        str(lbl),
                        style={
                            "fontSize": "11px",
                            "opacity": 0.85,
                            "whiteSpace": "normal",
                            "overflowWrap": "anywhere",
                            "wordBreak": "break-word",
                            "minWidth": 0,
                            "alignSelf": "start",
                        },
                    ),
                    html.Div(
                        "—" if val in (None, "", []) else str(val),
                        style={
                            "fontSize": "14px",
                            "fontWeight": 600,
                            "whiteSpace": "pre-wrap",
                            "overflowWrap": "anywhere",
                            "wordBreak": "break-word",
                            "hyphens": "auto",
                            "minWidth": 0,
                        },
                    ),
                ],
                style={
                    "display": "grid",
                    "gridTemplateColumns": "minmax(110px, 40%) 1fr",
                    "gap": "6px 8px",
                    "marginBottom": "6px",
                    "alignItems": "start",
                },
            )

        def flatten_meta(meta):
            rows = []
            if not isinstance(meta, dict):
                return rows

            def _walk(prefix, d):
                for k, v in d.items():
                    key = f"{prefix}.{k}" if prefix else str(k)
                    if isinstance(v, dict):
                        _walk(key, v)
                    else:
                        rows.append((key, v))

            _walk("", meta)
            return rows

        display_label = clean_id_text(node_data.get("label"))
        display_id = clean_id_text(node_data.get("id"))
        fields = [row("Label", display_label), row("Id", display_id), row("Classes", node_data.get("classes"))]

        if isinstance(node_data.get("meta"), dict):
            for k, v in flatten_meta(node_data["meta"]):
                fields.append(row(k, v))

        model = stored_model or {}
        cls = node_data.get("classes", "")
        raw_node_id = node_data.get("id")
        raw_label = node_data.get("label")
        raw_id_pref = node_data.get("raw_id")

        def _norm(s: str) -> str:
            import re
            s = str(s or "").strip()
            s = re.sub(r"\s+", "-", s)
            s = re.sub(r"[^A-Za-z0-9_.\\-]", "_", s)
            return s.lower()

        def strip_kind_prefixes(s: str) -> str:
            import re
            s = str(s or "")
            while True:
                new = re.sub(r"^(?:esp|profile)-", "", s, flags=re.IGNORECASE)
                if new == s:
                    break
                s = new
            return s

        def norm_all_keys(*vals):
            out = set()
            for v in vals:
                if v is None:
                    continue
                raw = str(v)
                cand = {raw, strip_kind_prefixes(raw)}
                for x in list(cand):
                    if "_" in x:
                        cand.add(x.split("_", 1)[0])
                out |= {_norm(x) for x in cand}
            return {x for x in out if x}

        node_keys = norm_all_keys(raw_node_id, raw_label, raw_id_pref)

        if cls == "profile":
            found = None
            for p in (model.get("profiles") or []):
                cand = norm_all_keys(p.get("profile_id"), p.get("name"))
                if node_keys & cand:
                    found = p
                    break
            if found:
                meta = (found.get("meta") or {})
                fields.extend(
                    [
                        row("Profile ID", clean_id_text(found.get("profile_id"))),
                        row("Deployment Mode", meta.get("deployment_mode")),
                        row("Device Type", meta.get("device_type")),
                        row("User Type", meta.get("user_type")),
                        row("Language", meta.get("language")),
                        row("AAD Join As", meta.get("join_to_azure_ad_as")),
                        row("Device Name Template", meta.get("device_name_template")),
                        row("Enable Pre-provision", meta.get("enable_pre_provisioning")),
                        row("Extract HW Hash", meta.get("extract_hardware_hash")),
                        row("Hide Privacy Settings", meta.get("hide_privacy_settings")),
                        row("Hide EULA", meta.get("hide_eula")),
                        row("Hide Escape Link", meta.get("hide_escape_link")),
                        row("Assignment Target", meta.get("assignment_target")),
                    ]
                )

        elif cls == "esp":
            found = None
            for e in (model.get("esps") or []):
                cand = norm_all_keys(
                    e.get("id"),
                    e.get("name"),
                    (e.get("meta") or {}).get("assigned_group_name"),
                )
                if node_keys & cand:
                    found = e
                    break
            if found:
                meta = (found.get("meta") or {})
                apps = meta.get("selected_apps_to_wait_on")
                apps_str = (
                    ", ".join([str(a) for a in apps if a])
                    if isinstance(apps, (list, tuple))
                    else (str(apps) if apps else "")
                )
                fields.extend(
                    [
                        row("ESP ID", clean_id_text(found.get("id"))),
                        row("Type", found.get("type")),
                        row("Priority", meta.get("priority")),
                        row("Show Install Progress", meta.get("show_install_progress")),
                        row("Timeout (mins)", meta.get("timeout_mins")),
                        row("Allow Log Collection", meta.get("allow_log_collection")),
                        row("Block Device By User", meta.get("block_device_by_user")),
                        row("Apps To Wait On", apps_str),
                        row("Allow Reset On Failure", meta.get("allow_device_reset_on_failure")),
                        row("Allow Use On Failure", meta.get("allow_device_use_on_failure")),
                        row("Assigned Group", meta.get("assigned_group_name")),
                    ]
                )

        elif cls == "group":
            meta = node_data.get("meta") or {}
            parent_label = node_data.get("parent_profile_label") or ""
            parent_id = node_data.get("parent_profile_id") or ""

            def pick(*keys):
                for k in keys:
                    v = meta.get(k)
                    if v not in (None, ""):
                        return v
                return None

            fields.extend(
                [
                    row("Parent Profile", parent_label or parent_id),
                    row("Group Name", pick("display_name", "group_name", "name") or display_label),
                    row("Synthetic", str(meta.get("synthetic")) if meta.get("synthetic") is not None else "—"),
                    row("Source", meta.get("source")),
                ]
            )
            for k, v in sorted(
                (k, v)
                for k, v in meta.items()
                if k not in {"display_name", "group_name", "name", "id", "synthetic", "source"}
            ):
                fields.append(row(k, v))

        return html.Div(
            [html.Div("Selected node", style={"fontWeight": 700, "marginBottom": "8px"}), html.Div(fields)],
            style={**CARD_BASE, "padding": "12px", "overflowWrap": "anywhere", "wordBreak": "break-word"},
        )
