# cprc_app/app/data_adapters.py
from typing import Any, Dict, List
from classes.xml_processor import XMLProcessor  # keep import in case you want to use it elsewhere

def _s(v: Any) -> str:
    return "" if v is None else str(v)

def _intish(v: Any) -> int:
    try:
        return int(str(v).replace(" ", "")) if v is not None else 0
    except Exception:
        return 0

def _norm_size(v: Any) -> str:
    return _s(v)

def _as_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]

def build_app_rows_from_xml(xml_dict: dict) -> List[Dict]:
    """
    Build rows for build_applications_table directly from the raw xmltodict output.
    No dedupe. If the XML contains 100 apps, you’ll get 100 rows.
    """
    rows: List[Dict] = []

    mem = (xml_dict or {}).get("MEMConfig") or {}
    ap_profiles = mem.get("APProfiles", {}) or {}
    profiles = ap_profiles.get("APProfile", []) or []
    profiles = _as_list(profiles)

    for prof in profiles:
        assignments = (prof or {}).get("Assignments", {}) or {}
        groups = assignments.get("Group", []) or []
        groups = _as_list(groups)

        for grp in groups:
            apps_assigned = grp.get("ApplicationsAssigned", {}) or {}
            # Sometimes the export keeps a count, sometimes not.
            applications = apps_assigned.get("Application", []) or []
            applications = _as_list(applications)

            for app in applications:
                # app is a dict of fields; normalize with fallbacks
                display_name = app.get("DisplayName") or app.get("Name") or app.get("ApplicationName") or "Unknown"
                publisher = app.get("Publisher") or app.get("Developer") or app.get("Vendor") or "Unknown"
                app_type = app.get("Type") or app.get("AppType") or "Unknown"
                size = app.get("Size") or app.get("TotalContentSize") or "0"
                filename = app.get("Filename") or app.get("FileName") or "Unknown"
                install_cmd = app.get("InstallCmd") or app.get("InstallCommand") or "N/A"
                uninstall_cmd = app.get("UninstallCmd") or app.get("UninstallCommand") or "N/A"
                run_as = app.get("RunAsAccount") or "System"
                restart_behavior = app.get("RestartBehavior") or "Default"
                rule_type = app.get("RuleType") or "None"
                app_id = app.get("ID") or app.get("id") or app.get("AppId") or ""

                # dependent count may be missing or a string with spaces
                dep_cnt = _intish(app.get("DependentAppCount"))

                rows.append({
                    "Display Name": _s(display_name),
                    "Publisher": _s(publisher),
                    "Type": _s(app_type),
                    "Size": _norm_size(size),
                    "Filename": _s(filename),
                    "Install Cmd": _s(install_cmd),
                    "Uninstall Cmd": _s(uninstall_cmd),
                    "Depends On (Count)": dep_cnt,
                    "Run As": _s(run_as),
                    "Restart Behavior": _s(restart_behavior),
                    "Rule Type": _s(rule_type),
                    "Profiles": "",      # can enrich later if needed
                    "Profile IDs": "",   # can enrich later if needed
                    "Groups": "",        # can enrich later if needed
                    "ESPs (wait-on)": "",# can enrich later if needed
                    "App ID": _s(app_id),
                })

    return rows
