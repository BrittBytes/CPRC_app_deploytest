# cprc_app/app/utils.py
import base64, dataclasses, re, numpy as np
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Dict
from dash import html
from app.theme import THEME, CARD_BASE

def _as_list(x):
    if x is None: return []
    return x if isinstance(x, (list, tuple)) else [x]

def json_safe(o: Any) -> Any:
    if o is None or isinstance(o, (bool, int, float, str)): return o
    from decimal import Decimal
    if isinstance(o, Decimal): return float(o)
    if isinstance(o, (datetime, date)): return o.isoformat()
    if dataclasses.is_dataclass(o): return {k: json_safe(v) for k, v in dataclasses.asdict(o).items()}
    if hasattr(o, "model_dump"): return {k: json_safe(v) for k, v in o.model_dump().items()}
    if hasattr(o, "dict"):
        try: return {k: json_safe(v) for k, v in o.dict().items()}
        except Exception: pass
    if hasattr(o, "value"):
        try: return json_safe(o.value)
        except Exception: pass
    if isinstance(o, dict): return {json_safe(k): json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)): return [json_safe(v) for v in o]
    try:
        if isinstance(o, (np.integer,)): return int(o)
        if isinstance(o, (np.floating,)): return float(o)
        if isinstance(o, (np.bool_,)): return bool(o)
    except Exception:
        pass
    return str(o)

def decode_xml_contents(contents: str) -> bytes:
    if not contents or "," not in contents:
        raise ValueError("Invalid upload contents.")
    _, b64data = contents.split(",", 1)
    return base64.b64decode(b64data)

def meta_row(label: str, value: str, allow_wrap: bool = False):
    style_value = {"fontSize": "14px","fontWeight": 600}
    if allow_wrap:
        style_value.update({"whiteSpace": "normal","wordBreak": "break-all"})
    else:
        style_value.update({"overflow": "hidden","textOverflow": "ellipsis","whiteSpace": "nowrap"})
    return html.Div([
        html.Div(label, style={"fontSize": "11px", "opacity": 0.85}),
        html.Div(value or "—", style=style_value)
    ], style={"display": "grid","gridTemplateColumns": "110px 1fr","gap": "4px","pointerEvents": "auto"})

def _collect_group_names(group_obj) -> List[str]:
    names = []
    if not group_obj: return names
    def _one(g):
        if isinstance(g, dict):
            return (g.get("display_name") or g.get("group_name") or g.get("name") or g.get("id") or str(g))
        return str(g)
    items = group_obj if isinstance(group_obj, list) else [group_obj]
    for g in items:
        n = _one(g)
        if n: names.append(str(n).strip())
    dedup, seen = [], set()
    for n in names:
        k = n.lower()
        if k not in seen:
            seen.add(k); dedup.append(n)
    return dedup

def clean_id_text(s: str) -> str:
    s = str(s or "")
    s = re.sub(r'^(?:esp|profile)-', '', s, flags=re.IGNORECASE)
    s = s.replace("esp-a43f351a-e35d-47ed-82b1-37b7444003ba_", "")
    return s

def card_container(children, **extra_style):
    return html.Div(children, style={**CARD_BASE, **extra_style})
