# cprc_app/app/cyto.py
import re
from typing import Any, Dict, List
from app.utils import json_safe

def build_cytoscape_elements(model: dict):
    """
    Builds Cytoscape elements with three-bucket ordering:
      LEFT   : profiles that form full chains (Profile -> Group -> ESP)
      MIDDLE : profiles with groups but no ESPs, and groups with no ESPs
      RIGHT  : vertical lists of orphan ESPs and orphan profiles (no groups)

    Spacing is dynamic to reduce overlap when clusters get large.
    """
    model = json_safe(model)

    esps_raw = (model.get("esps") or [])
    profiles_raw = (model.get("profiles") or [])

    def _norm_id(s: str) -> str:
        s = str(s or "").strip()
        s = re.sub(r"\s+", "-", s)
        s = re.sub(r"[^A-Za-z0-9_.\-]", "_", s)
        return s.lower()

    # ---- Build robust lookup tables so we can backfill meta on edge-created nodes ----
    def _keys_for(obj, kind: str):
        keys = set()
        if kind == "esp":
            keys.add(_norm_id(obj.get("id")))
            keys.add(_norm_id(obj.get("name")))
        else:  # profile
            keys.add(_norm_id(obj.get("profile_id")))
            keys.add(_norm_id(obj.get("name")))
        # GUID_with_suffix => also allow GUID-only
        addl = set()
        for k in list(keys):
            if "_" in k:
                addl.add(k.split("_", 1)[0])
        return keys | addl

    esp_lookup = {}
    for e in esps_raw:
        for k in _keys_for(e, "esp"):
            esp_lookup.setdefault(k, e)

    profile_lookup = {}
    for p in profiles_raw:
        for k in _keys_for(p, "profile"):
            profile_lookup.setdefault(k, p)

    def _attach_data_from_obj(el, obj, kind):
        d = el.setdefault("data", {})
        if kind == "esp":
            d.setdefault("raw_id", obj.get("id"))
            d.setdefault("name", obj.get("name"))
            d.setdefault("type", obj.get("type"))
        elif kind == "profile":
            d.setdefault("raw_id", obj.get("profile_id"))
            d.setdefault("name", obj.get("name"))
        meta = obj.get("meta")
        if isinstance(meta, dict):
            d.setdefault("meta", json_safe(meta))  # copy to avoid mutating model

    def _as_node(obj: Any, kind: str):
        if isinstance(obj, dict):
            node_id = obj.get("id") or obj.get("profile_id") or obj.get("name") or obj.get("label") or obj.get("key")
            label = obj.get("name") or obj.get("label") or obj.get("id") or obj.get("profile_id") or obj.get("key") or str(node_id)
            pos = obj.get("position") or obj.get("pos")
            if not node_id:
                node_id = label
            node_id = f"{kind}-{_norm_id(node_id)}"
            el = {"data": {"id": node_id, "label": str(label)}, "classes": kind}
            if isinstance(pos, dict) and {"x", "y"} <= set(pos):
                el["position"] = {"x": float(pos["x"]), "y": float(pos["y"])}
            _attach_data_from_obj(el, obj, kind)
            return node_id, el
        else:
            node_id = f"{kind}-{_norm_id(obj)}"
            return node_id, {"data": {"id": node_id, "label": str(obj)}, "classes": kind}

    nodes: Dict[str, Dict[str, Any]] = {}

    # ---- Profiles
    profiles_index_by_label = {}
    for p in profiles_raw:
        pid, pel = _as_node(p, "profile")
        # Move group-related data OFF the profile node (so it only shows on group nodes)
        meta = pel.get("data", {}).get("meta")
        if isinstance(meta, dict):
            meta.pop("groups", None)
            meta.pop("excluded_groups", None)
            pel["data"]["meta"] = meta
        nodes.setdefault(pid, pel)
        profiles_index_by_label[pel["data"]["label"]] = pid

    # ---- ESPs
    esps_index_by_label = {}
    for e in esps_raw:
        eid, eel = _as_node(e, "esp")
        nodes.setdefault(eid, eel)
        esps_index_by_label[eel["data"]["label"]] = eid

    edges: List[Dict[str, Any]] = []

    # ---------- GROUP LAYER ----------
    # Map ESP assignment => esp ids (case-insensitive)
    from collections import defaultdict as _dd
    esp_by_assigned = _dd(list)
    for e in esps_raw:
        eid, _eel = _as_node(e, "esp")  # safe if already exists
        meta = (e.get("meta") or {})
        gname = (meta.get("assigned_group_name") or "").strip()
        if gname:
            esp_by_assigned[gname.lower()].append(eid)

    # Helper: case-insensitive pick from dict
    def _pick_ci(d: dict, keys: List[str]):
        if not isinstance(d, dict):
            return None
        lower_map = {str(k).lower(): k for k in d.keys()}
        for k in keys:
            lk = k.lower()
            if lk in lower_map:
                return d[lower_map[lk]]
        return None

    # Helper: extract actual group objects; keep both id and display_name
    def _profile_groups_as_objects(p_obj: dict) -> List[dict]:
        meta = p_obj.get("meta") or {}
        raw_groups = meta.get("groups")

        BAD = {"group", "not assigned", "unassigned", "none", "n/a", "na", "-", "(none)"}

        def _normalize_group(g) -> dict | None:
            # Returns dict with canonical fields: { group_id, display_name, ...orig }
            if isinstance(g, dict):
                gid = _pick_ci(g, ["id", "group_id", "object_id", "groupId", "GroupId"])
                dn  = _pick_ci(
                    g,
                    ["display_name", "displayName", "DisplayName",
                     "group_name", "groupName",
                     "name", "Name", "id"]
                )
                gid = (str(gid).strip() if gid is not None else "") or None
                dn  = (str(dn).strip() if dn is not None else "")
                if not dn or dn.lower() in BAD:
                    return None
                out = {**g}
                out["group_id"] = gid
                out["display_name"] = dn
                return out

            # scalar -> treat as label only; no id
            dn = str(g).strip()
            if not dn or dn.lower() in BAD:
                return None
            return {"group_id": None, "display_name": dn}

        groups_list: List[dict] = []
        if isinstance(raw_groups, list):
            for g in raw_groups:
                ng = _normalize_group(g)
                if ng:
                    groups_list.append(ng)
        elif isinstance(raw_groups, dict):
            ng = _normalize_group(raw_groups)
            if ng:
                groups_list.append(ng)

        # also include assignment_target as a synthetic group if it’s a real name
        at = meta.get("assignment_target")
        if at:
            at_name = str(at).strip()
            if at_name and at_name.lower() not in BAD:
                groups_list.append({
                    "group_id": None,
                    "display_name": at_name,
                    "synthetic": True,
                    "source": "assignment_target"
                })

        # Deduplicate: first by group_id (if present), otherwise by display_name (case-insensitive)
        seen_ids, seen_names, dedup = set(), set(), []
        for g in groups_list:
            gid = g.get("group_id") or None
            dn  = (g.get("display_name") or "").strip()
            if gid:
                if gid in seen_ids:
                    continue
                seen_ids.add(gid)
                dedup.append(g)
            else:
                k = dn.lower()
                if k in seen_names:
                    continue
                seen_names.add(k)
                dedup.append(g)
        return dedup

    # Build Profile -> Group nodes; Group -> ESP edges with per-profile ESP dedupe
    p_to_g = _dd(list)   # profile id -> [group ids]
    g_to_e = _dd(list)   # group id -> [esp ids]
    esp_first_owner: Dict[str, str] = {}  # esp id (per profile) -> group id that claimed it

    # For layout we also need to remember which profile a group belongs to
    group_parent: Dict[str, str] = {}

    # guard against duplicate group nodes per profile (case-insensitive key)
    group_key_to_id: Dict[tuple, str] = {}  # (pid, g_label_lower) -> gid

    # Iterate profiles, create branches
    for p in profiles_raw:
        pid, _pel = _as_node(p, "profile")
        group_objs = _profile_groups_as_objects(p)
        for gobj in group_objs:
            g_label = (gobj.get("display_name") or "").strip()
            if not g_label or g_label.lower() == "group":
                continue

            gkey = (pid, g_label.lower())
            # Reuse existing group node for this profile+name if already created
            if gkey in group_key_to_id:
                gid = group_key_to_id[gkey]
            else:
                gid = f"group-{_norm_id(g_label)}-{_norm_id(pid)}"
                if gid not in nodes:
                    nodes[gid] = {
                        "data": {
                            "id": gid,
                            "label": g_label,                 # exact display name on the node
                            "meta": json_safe(gobj),          # group meta lives here
                            "parent_profile_id": pid,
                            "parent_profile_label": nodes[pid]["data"]["label"],
                        },
                        "classes": "group"
                    }
                group_key_to_id[gkey] = gid

            # Edge: profile -> group
            edges.append({"data": {"source": pid, "target": gid}})
            if gid not in p_to_g[pid]:
                p_to_g[pid].append(gid)
            group_parent[gid] = pid

            # Edge(s): group -> matching ESPs by assigned_group_name (case-insensitive)
            match_key = g_label.strip().lower()
            for eid in sorted(set(esp_by_assigned.get(match_key, []))):
                key = f"{eid}|{pid}"     # per-profile ownership of shared ESPs
                if key in esp_first_owner:
                    continue
                esp_first_owner[key] = gid
                edges.append({"data": {"source": gid, "target": eid}})
                g_to_e[gid].append(eid)

    # ---------- LAYOUT ----------
    elements = list(nodes.values())
    has_any_position = any("position" in n for n in nodes.values())
    if not has_any_position:
        profile_ids = [nid for nid, n in nodes.items() if n.get("classes") == "profile"]
        group_ids   = [nid for nid, n in nodes.items() if n.get("classes") == "group"]
        esp_ids     = [nid for nid, n in nodes.items() if n.get("classes") == "esp"]

        # Profiles with any groups
        mapped_profiles = [pid for pid in profile_ids if p_to_g.get(pid)]
        stray_profiles  = [pid for pid in profile_ids if not p_to_g.get(pid)]

        # Bucket 1: full chains (profile has a group with at least one ESP)
        chain_profiles = []
        for pid in mapped_profiles:
            has_esp = any(g_to_e.get(gid) for gid in p_to_g[pid])
            if has_esp:
                chain_profiles.append(pid)

        # Bucket 2: profiles with groups but no ESPs; and their groups with no ESPs
        mid_profiles = [pid for pid in mapped_profiles if pid not in chain_profiles]
        mid_groups = []
        for pid in mapped_profiles:
            for gid in p_to_g[pid]:
                if not g_to_e.get(gid):
                    mid_groups.append(gid)

        # Bucket 3: orphans (ESPs with no groups; profiles with no groups)
        placed_esps_in_chains = {
            eid
            for gids in (g_to_e.get(g, []) for pid in chain_profiles for g in p_to_g.get(pid, []))
            for eid in gids
        }
        orphan_esps = [
            eid for eid in esp_ids
            if eid not in placed_esps_in_chains and all(eid not in (g_to_e.get(g, []) or []) for g in group_ids)
        ]
        orphan_profiles = stray_profiles[:]  # profiles with no groups

        # --- Layout constants (roomier defaults)
        left_pad   = 440
        base_col_width  = 420    # base distance between profile columns
        top_pad    = 80
        profile_y  = top_pad

        row_step_g = 300         # space between groups under a profile
        row_step_e = 200         # space between ESPs under a group
        branch_dx  = 220         # horizontal spacing between sibling groups
        margin_after_stack = 80  # extra buffer after a group’s ESPs

        node_radius_x = 100      # conservative half-width for node label/shape
        col_gap_min   = 140      # minimum gap between adjacent profile spans

        # Helpers
        def nodes_owned_by_profile(pid: str):
            owned = {pid}
            for gid in p_to_g.get(pid, []):
                owned.add(gid)
                for eid in g_to_e.get(gid, []):
                    owned.add(eid)
            return owned

        # Dynamic column gap based on branch width and vertical stack depth
        def _dynamic_col_gap(pid: str) -> float:
            n_groups = max(1, len(p_to_g.get(pid, [])))
            max_esps_under_any_group = 0
            for gid in p_to_g.get(pid, []):
                max_esps_under_any_group = max(max_esps_under_any_group, len(g_to_e.get(gid, [])))

            cluster_width = (n_groups - 1) * branch_dx + 2 * node_radius_x
            cluster_height = row_step_g + max(0, n_groups - 1) * row_step_g \
                             + max(0, max_esps_under_any_group) * row_step_e

            pad = min(420, 0.20 * cluster_width + 0.08 * cluster_height)
            return max(base_col_width, base_col_width + pad)

        # Pre-compute external targets so profiles with cross-edges don't force-shift neighbors
        external_targets = {pid: set() for pid in chain_profiles}
        for e in edges:
            s = e["data"]["source"]; t = e["data"]["target"]
            for pid in chain_profiles:
                owned = nodes_owned_by_profile(pid)
                if s in owned and t not in owned: external_targets[pid].add(t)
                if t in owned and s not in owned: external_targets[pid].add(s)

        # 1) LEFT: full chains (cascading layout with dynamic column gaps)
        last_span_max = left_pad - col_gap_min
        base_x_for_profile = {}
        chain_profiles.sort(key=lambda pid: (-len(p_to_g.get(pid, ())), pid))
        next_center = left_pad
        placed_nodes = set()

        for pid in chain_profiles:
            groups = p_to_g.get(pid, [])
            n = max(1, len(groups))
            half_span = ((n - 1) / 2.0) * branch_dx

            base_cx = next_center
            has_cross = bool(external_targets[pid] & placed_nodes)
            if not has_cross:
                desired_min_x = last_span_max + col_gap_min + node_radius_x
                current_min_x = (base_cx - half_span) - node_radius_x
                if current_min_x < desired_min_x:
                    base_cx += (desired_min_x - current_min_x)

            base_x_for_profile[pid] = base_cx
            nodes[pid]["position"] = {"x": base_cx, "y": profile_y}

            span_max = (base_cx + half_span) + node_radius_x
            last_span_max = max(last_span_max, span_max)

            # dynamic gap so big clusters push the next profile farther right
            col_gap = _dynamic_col_gap(pid)
            next_center = base_cx + col_gap

            placed_nodes |= nodes_owned_by_profile(pid)

        # Place groups/ESPs under each chain profile (with micro-spread)
        placed_esps = set()
        for pid in chain_profiles:
            base_px = base_x_for_profile[pid]
            groups = p_to_g.get(pid, [])
            n = max(1, len(groups))
            start_offset = -((n - 1) / 2.0) * branch_dx
            y_current = profile_y + row_step_g

            for i, gid in enumerate(groups):
                # Micro-spread based on this group's ESP depth + sibling index
                depth_bonus = 0.06 * row_step_e * len(g_to_e.get(gid, []))
                gx = (
                    base_px
                    + start_offset
                    + i * branch_dx
                    + (i - (n - 1) / 2) * 0.10 * branch_dx
                    + 0.2 * depth_bonus
                )
                nodes[gid]["position"] = {"x": gx, "y": y_current}

                y_cursor = y_current + row_step_e
                for eid in g_to_e.get(gid, []):
                    if eid in placed_esps:
                        continue
                    nodes[eid]["position"] = {"x": gx, "y": y_cursor}
                    y_cursor += row_step_e
                    placed_esps.add(eid)

                y_current = max(y_current + row_step_g, y_cursor + margin_after_stack)

        # 2) MIDDLE: profiles with groups but no ESPs + their no-ESP groups
        middle_x = last_span_max + 240
        mid_col_width = 260
        mid_profile_y = top_pad
        mid_group_y   = top_pad + 40

        for pid in mid_profiles:
            nodes[pid]["position"] = {"x": middle_x, "y": mid_profile_y}
            mid_profile_y += 140

        middle_groups_x = middle_x + mid_col_width
        for gid in mid_groups:
            nodes[gid]["position"] = {"x": middle_groups_x, "y": mid_group_y}
            mid_group_y += 140

        last_span_max = max(last_span_max, middle_groups_x)

        # 3) RIGHT: Orphan lists (vertical stacks)
        right_gutter_x_profiles = last_span_max + 320
        right_gutter_x_esps     = right_gutter_x_profiles + 260

        y_rp = top_pad
        for pid in orphan_profiles:
            nodes[pid]["position"] = {"x": right_gutter_x_profiles, "y": y_rp}
            y_rp += 140

        y_re = top_pad
        for eid in orphan_esps:
            nodes[eid]["position"] = {"x": right_gutter_x_esps, "y": y_re}
            y_re += 140

        elements = list(nodes.values())

    # ---------- APPEND UNIQUE EDGES ----------
    seen = set()
    for e in edges:
        key = (e["data"]["source"], e["data"]["target"])
        if key not in seen:
            seen.add(key)
            elements.append(e)

    return json_safe(elements)
