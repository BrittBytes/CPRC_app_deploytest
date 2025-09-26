from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ESPConfig:
    id: str
    display_name: str
    description: str
    priority: int
    last_modified: str
    show_install_progress: bool
    timeout_mins: int
    custom_error_msg: str
    allow_log_collection: bool
    block_device_by_user: bool
    selected_apps_to_wait_on: str #blocking apps
    allow_device_reset_on_failure: bool
    allow_device_use_on_failure: bool
    assigned_group_name: str
    is_auad: bool = False

@dataclass
class GroupAssignmentNest:
    count: int
    name: str
    display_name: str

@dataclass
class AssignmentGroupsWithinAPProfile:
    display_name: str
    id: str
    description: str
    type: str
    membership_rule: str
    security_enabled: bool
    device_members_count: int
    config_man_policy: bool
    nested_groups: bool
    win32_lob_app_mix: bool
    num_of_apps_assigned: int
    all_devices_assignments: bool = False
    compliance_policies: Optional[List[GroupAssignmentNest]] = None
    device_configs: Optional[List[GroupAssignmentNest]] = None
    ps_scripts: Optional[List[GroupAssignmentNest]] = None
    admin_templates: Optional[List[GroupAssignmentNest]] = None
    assigned_apps: Optional[List['Application']] = None
    

@dataclass
class APProfile:
    profile_id: str
    display_name: str
    description: str
    join_to_azure_ad_as: str
    deployment_mode: str
    language: str
    extract_hardware_hash: bool
    device_name_template: Optional[str]
    device_type: str
    enable_pre_provisioning: bool
    role_scope_tag_ids: str
    hide_privacy_settings: bool
    hide_eula: bool
    user_type: str
    skip_keyboard_selection: bool
    hide_escape_link: bool
    assignment_target: str
    excluded_groups: Optional[str] = None
    groups: Optional[List[AssignmentGroupsWithinAPProfile]] = None


@dataclass
class Application:
    display_name: str
    app_id: str
    app_assign_type: str
    description: str
    publisher: str
    app_type: str
    filename: str
    size: str
    install_cmd: str
    uninstall_cmd: str
    dependent_app_count: Optional[int] = None
    run_as_acct: Optional[str] = None
    restart_behavior: Optional[str] = None
    return_codes: Optional[str] = None
    rule_type: Optional[str] = None
    app_dependencies: List['AppDependencies'] = field(default_factory=list)

@dataclass
class AppDependencies:
    dependency_app_count: int
    dependency_id: str
    target_id: str
    target_name: str
    target_publisher: str
    target_type: str
    target_dependency_type: str
    dependent_app_count: Optional[int] = 0
    dependency_apps: List[str] = field(default_factory=list)
