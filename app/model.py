# cprc_app/app/model.py
import os
import re
from typing import Any, Optional, List, Tuple, Dict
from classes.xml_processor import XMLProcessor
from app.utils import _as_list, json_safe, _collect_group_names

def extract_region_customername(xml_name: str) -> Tuple[str, str]:
    base_filename = os.path.basename(xml_name).strip()
    base_filename = os.path.splitext(base_filename)[0]  # type: ignore[attr-defined]
    match = re.match(r"^([A-Za-z]+)-([^.]+)", base_filename, re.IGNORECASE)
    if match:
        return match.group(1).upper(), match.group(2).upper()
    return "Unknown", "Unknown"

def map_esp(e, is_auad: bool) -> dict:
    return {
        "id": e.id,
        "name": e.display_name,
        "type": "AUAD" if is_auad else (getattr(e, "description", None) or "ESP"),
        "meta": {
            "priority": getattr(e, "priority", None),
            "show_install_progress": getattr(e, "show_install_progress", None),
            "timeout_mins": getattr(e, "timeout_mins", None),
            "allow_log_collection": getattr(e, "allow_log_collection", None),
            "block_device_by_user": getattr(e, "block_device_by_user", None),
            "selected_apps_to_wait_on": getattr(e, "selected_apps_to_wait_on", None),
            "allow_device_reset_on_failure": getattr(e, "allow_device_reset_on_failure", None),
            "allow_device_use_on_failure": getattr(e, "allow_device_use_on_failure", None),
            "assigned_group_name": getattr(e, "assigned_group_name", None),
        },
    }

def map_profiles_and_groups(p) -> dict:
    return {
        "profile_id": p.profile_id,
        "name": p.display_name,
        "meta": {
            "join_to_azure_ad_as": getattr(p, "join_to_azure_ad_as", None),
            "deployment_mode": getattr(p, "deployment_mode", None),
            "language": getattr(p, "language", None),
            "extract_hardware_hash": getattr(p, "extract_hardware_hash", None),
            "device_name_template": getattr(p, "device_name_template", None),
            "device_type": getattr(p, "device_type", None),
            "enable_pre_provisioning": getattr(p, "enable_pre_provisioning", None),
            "role_scop_tag_ids": getattr(p, "role_scope_tag_ids", None),
            "hide_privacy_settings": getattr(p, "hide_privacy_settings", None),
            "hide_eula": getattr(p, "hide_eula", None),
            "user_type": getattr(p, "user_type", None),
            "skip_keyboard_selection": getattr(p, "", None),
            "hide_escape_link": getattr(p, "hide_escape_link", None),
            "assignment_target": getattr(p, "assignment_target", None),
            "groups": json_safe(getattr(p, "groups", None)),
            "excluded_groups": json_safe(getattr(p, "excluded_groups", None)),
        },
    }

def infer_profile_esp_edges(model: dict) -> List[dict]:
    esps = model.get("esps") or []
    profiles = model.get("profiles") or []

    esp_by_group = {}
    for e in esps:
        meta = (e.get("meta") or {})
        g = meta.get("assigned_group_name")
        if g:
            esp_by_group.setdefault(str(g).lower(), []).append(e)

    edges = []
    for p in profiles:
        p_label = p.get("name") or p.get("profile_id") or "profile"
        meta = p.get("meta") or {}
        groups = _collect_group_names(meta.get("groups"))
        at = meta.get("assignment_target")
        if at:
            groups.append(str(at))
        matches = set()
        for g in groups:
            key = str(g).lower()
            for esp in esp_by_group.get(key, []):
                esp_label = esp.get("name") or esp.get("id")
                if esp_label:
                    matches.add(esp_label)
        for esp_label in sorted(matches):
            edges.append({"profile": p_label, "esp": esp_label})
    return edges

def _normalize_app_row(app: Any, source: str = "unknown") -> Optional[dict]:
    """
    Turn various shapes (str/dict/object) into a canonical row:
      { name, id, source, meta:{} }
    """
    if app is None:
        return None
    # dict-like
    if isinstance(app, dict):
        name = (app.get("display_name") or app.get("name") or app.get("appName") or app.get("ApplicationName") or "").strip()
        aid  = (app.get("id") or app.get("app_id") or app.get("applicationId") or app.get("AzureAppId") or "").strip() or None
        meta = {k: v for k, v in app.items() if k not in {"display_name","name","appName","ApplicationName","id","app_id","applicationId","AzureAppId"}}
        if not name and not aid:
            return None
        return {"name": name or aid or "(unnamed)", "id": aid, "source": source, "meta": meta}

    # pydantic-like / obj
    name = getattr(app, "display_name", None) or getattr(app, "name", None)
    aid  = getattr(app, "id", None) or getattr(app, "app_id", None)
    if isinstance(name, str) or isinstance(aid, str):
        return {"name": (name or aid or "(unnamed)"), "id": aid, "source": source, "meta": {}}

    # string-ish
    s = str(app).strip()
    if not s:
        return None
    return {"name": s, "id": None, "source": source, "meta": {}}

def _collect_applications(processor: XMLProcessor, model_so_far: dict) -> List[dict]:
    rows: List[dict] = []

    # 1) Prefer explicit application getters when available.
    for getter in ("get_applications", "get_application_inventory", "get_win32_apps"):
        fn = getattr(processor, getter, None)
        if callable(fn):
            try:
                for app in (fn() or []):
                    r = _normalize_app_row(app, source=getter)
                    if r:
                        rows.append(r)
            except Exception:
                # Be tolerant of shape mismatches in mixed XMLs
                pass

    # 2) Also include ESP-selected "apps to wait on".
    for e in (model_so_far.get("esps") or []):
        meta = (e.get("meta") or {})
        apps = meta.get("selected_apps_to_wait_on")
        if isinstance(apps, (list, tuple)):
            for a in apps:
                r = _normalize_app_row(a, source="esp_selected_apps")
                if r:
                    rows.append(r)
        elif apps:
            r = _normalize_app_row(apps, source="esp_selected_apps")
            if r:
                rows.append(r)

    # de-dup by (name,id,source)
    seen = set()
    out: List[dict] = []
    for r in rows:
        key = (r.get("name", "").lower(), (r.get("id") or "").lower(), r.get("source", "").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out

# ------------------------------
# New: Applications & Dependencies (table-ready)
# ------------------------------

def _normalize_return_codes(rc: Any) -> str:
    """Return codes can be list/dict/str; emit a readable string."""
    if isinstance(rc, list):
        return ", ".join(map(str, rc))
    if isinstance(rc, dict):
        if "Code" in rc:
            v = rc["Code"]
            return ", ".join(map(str, v)) if isinstance(v, list) else str(v)
        return ", ".join(f"{k}:{v}" for k, v in rc.items())
    return str(rc or "")

def _normalize_dependency_apps(dep_apps_raw: Any) -> str:
    """
    dependency_apps may be list[dict], dict, str, or empty.
    Prefer DisplayName/Name/ID as a visible label.
    """
    items: List[str] = []
    if isinstance(dep_apps_raw, dict):
        dep_apps_raw = [dep_apps_raw]
    if isinstance(dep_apps_raw, list):
        for item in dep_apps_raw:
            if isinstance(item, dict):
                name = item.get("DisplayName") or item.get("Name") or item.get("ID")
                if name:
                    items.append(str(name))
            else:
                items.append(str(item))
    elif dep_apps_raw:
        items.append(str(dep_apps_raw))
    return ", ".join(items)

def _collect_apps_and_dependencies(processor: XMLProcessor) -> Tuple[List[Dict], List[Dict]]:
    """
    Uses XMLProcessor.get_applications_and_dependencies() to produce
    two normalized lists for tables: applications_table, dependencies.
    """
    apps_table: List[Dict] = []
    deps_table: List[Dict] = []

    fn = getattr(processor, "get_applications_and_dependencies", None)
    if not callable(fn):
        return apps_table, deps_table

    try:
        apps_details, app_dependencies = fn()  # [(count, Application), [AppDependencies,...]]
    except Exception:
        # Fail-safe: return empty tables if XML shape is unexpected
        return apps_table, deps_table

    # Applications
    for app_count, app in (apps_details or []):
        # getattr to be resilient to namedtuples/dataclasses/objects
        apps_table.append({
            "application_count": int(app_count or 0),
            "display_name": getattr(app, "display_name", "Unknown"),
            "app_id": getattr(app, "app_id", None) or getattr(app, "id", None),
            "app_assign_type": getattr(app, "app_assign_type", "Unknown"),
            "description": getattr(app, "description", "No description"),
            "publisher": getattr(app, "publisher", "Unknown"),
            "app_type": getattr(app, "app_type", "Unknown"),
            "filename": getattr(app, "filename", "Unknown"),
            "size": getattr(app, "size", "0"),
            "install_cmd": getattr(app, "install_cmd", "N/A"),
            "uninstall_cmd": getattr(app, "uninstall_cmd", "N/A"),
            "dependent_app_count": int(str(getattr(app, "dependent_app_count", 0)).replace(" ", "") or 0),
            "run_as_acct": getattr(app, "run_as_acct", "System"),
            "restart_behavior": getattr(app, "restart_behavior", "Default"),
            "return_codes": _normalize_return_codes(getattr(app, "return_codes", [])),
            "rule_type": getattr(app, "rule_type", "None"),
        })

    # Dependencies
    for dep in (app_dependencies or []):
        dep_apps_raw = getattr(dep, "dependency_apps", [])
        deps_table.append({
            "target_name": getattr(dep, "target_name", "Unknown"),
            "target_id": getattr(dep, "target_id", None),
            "target_publisher": getattr(dep, "target_publisher", "Unknown"),
            "target_type": getattr(dep, "target_type", "Unknown"),
            "target_dependency_type": getattr(dep, "target_dependency_type", "Unknown"),
            "dependency_app_count": int(str(getattr(dep, "dependency_app_count", 0)).replace(" ", "") or 0),
            "dependency_id": getattr(dep, "dependency_id", None),
            "dependency_apps": _normalize_dependency_apps(dep_apps_raw),
        })

    return apps_table, deps_table

# ------------------------------

def build_model(filename: str, processor: XMLProcessor, raw_doc: dict) -> dict:
    region, customer = extract_region_customername(filename or "")
    formatted_time, tenantName, tenantID, raw_timestamp, cprc_version = processor.get_customer_tenant_details()

    esps = []
    for e in _as_list(processor.get_auad_esp_config()):
        esps.append(map_esp(e, is_auad=True))
    for e in _as_list(processor.get_esp_config()):
        esps.append(map_esp(e, is_auad=False))

    profiles = []
    for p in _as_list(processor.get_autopilot_profiles()):
        profiles.append(map_profiles_and_groups(p))

    model = {
        "file": filename,
        "region": region,
        "customer": customer,
        "tenant_name": tenantName,
        "tenant_id": tenantID,
        "meta": {
            "cprc_timestamp": raw_timestamp,
            "cprc_version": cprc_version,
            "formatted_time": formatted_time,
        },
        "esps": esps,
        "profiles": profiles,
    }
    model["edges"] = infer_profile_esp_edges(model)

    # Existing lightweight application surface
    model["applications"] = _collect_applications(processor, model)

    # New: table-ready Applications & Dependencies from XML
    applications_table, dependencies = _collect_apps_and_dependencies(processor)
    model["applications_table"] = applications_table
    model["dependencies"] = dependencies

    return model
