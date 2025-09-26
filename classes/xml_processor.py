from datetime import datetime
from classes.data_classes import ESPConfig, APProfile, AssignmentGroupsWithinAPProfile, GroupAssignmentNest, Application, AppDependencies

# ------------------------------------------ #
# import json
# import pprint
# pp  =  pprint.PrettyPrinter(indent = 4)   
# pp.pprint(json.dumps(doc))
# ------------------------------------------ #
class XMLProcessor:
    def __init__(self, doc):
        self.data  =  doc

    def get_customer_tenant_details(self):
        # Extract the raw timestamp
        raw_timestamp = self.data['MEMConfig'].get('CPRCTimestamp')
        cprc_version = self.data['MEMConfig'].get('CPRCVersion')        
        # Parse and format the timestamp
        if raw_timestamp:
            try:
                 # Parse the custom timestamp format
                parsed_time = datetime.strptime(raw_timestamp, "%Y_%m_%d_%H_%M")
                # Format the timestamp into a readable format
                formatted_time = parsed_time.strftime("%B %d, %Y")
            except ValueError:
                # Handle parsing error, default to raw timestamp
                formatted_time = raw_timestamp
        else:
            formatted_time = "Unknown Date and Time"

        tenantName  =  self.data['MEMConfig'].get('TenantName')
        tenantID  =  self.data['MEMConfig'].get('TenantID')

        return formatted_time, tenantName, tenantID, raw_timestamp, cprc_version
    
    def get_auad_esp_config(self): #All Users and All Devices
        auad_esp_list  =  self.data['MEMConfig'].get('ESPConfig', {}).get('ESP', [])
        auad_esp_details  =  []

        #Ensure esp list is always a list
        if isinstance(auad_esp_list, dict):
            auad_esp_list = [auad_esp_list]

        for i in auad_esp_list:
            if isinstance(i, dict):
                display_name = i.get('DisplayName', '')
                if display_name and display_name.lower() == "all users and all devices":
                    try:
                       
                        auad_esp_details.append(ESPConfig(
                            id =  i.get('ID', None),
                            display_name =  i.get('DisplayName', None),
                            description =  i.get('Description', None),
                            priority =  i.get('Priority', None),
                            last_modified = i.get('LastModifed', None),
                            show_install_progress =  i.get('ShowInstallProgress', 'False') == 'True',
                            timeout_mins =  int(i.get('TimeOutMins', 0)),
                            custom_error_msg =  i.get('CustomErrorMessage', None),
                            allow_log_collection =  i.get('AllowLogCollection', 'False')  ==  'True',
                            block_device_by_user =  i.get('BlockDeviceByUser', None),
                            allow_device_reset_on_failure =  i.get('AllowDeviceResetOnFailure', None),
                            allow_device_use_on_failure =  i.get('AllowDeviceUseOnFailure', None),
                            assigned_group_name =  i.get('AssignedGroupName'),
                            selected_apps_to_wait_on= i.get('SelectedAppstoWaitOn', None),
                            is_auad = True
                        ))
                        
                    except TypeError as e:
                        print(f" Error creating ESPConfig: {e} | Data: {i}")
        return auad_esp_details
    
    def get_esp_config(self):
        esp_list  =  self.data['MEMConfig'].get('ESPConfig', {}).get('ESP', [])
        esp_details  =  []

        #DEBUG ESP LIST: 
        # print(f"esp_list content: {esp_list}")
       
        # If it's a dict keyed by ESP IDs/names, get the values
        if isinstance(esp_list, dict):
            if "DisplayName" in esp_list:
                esp_list = [esp_list]
            else:
                # It's a dict of ESP dicts — take the values
                esp_list = list(esp_list.values())

        for i in esp_list:
            if isinstance(i, dict):
                display_name = i.get('DisplayName', '')
                if display_name and display_name.lower() == "all users and all devices":
                    continue #skip AUAD ESPs
                try:
                    esp_details.append(ESPConfig(
                    id =  i.get('ID', None),
                    display_name =  i.get('DisplayName', None),
                    description =  i.get('Description', None),
                    priority =  i.get('Priority', None),
                    last_modified = i.get('LastModifed', None),
                    show_install_progress =  i.get('ShowInstallProgress', 'False') == 'True',
                    timeout_mins =  int(i.get('TimeOutMins', 0)),
                    custom_error_msg =  i.get('CustomErrorMessage', None),
                    allow_log_collection =  i.get('AllowLogCollection', 'False')  ==  'True',
                    block_device_by_user =  i.get('BlockDeviceByUser', None),
                    allow_device_reset_on_failure =  i.get('AllowDeviceResetOnFailure', None),
                    allow_device_use_on_failure =  i.get('AllowDeviceUseOnFailure', None),
                    selected_apps_to_wait_on= i.get('SelectedAppstoWaitOn', None),
                    assigned_group_name =  i.get('AssignedGroupName'),
                    is_auad = False
                    ))

                except TypeError as e:
                    print(f"Error creating ESPConig: {e} | Data: {i}")
        return esp_details

    def get_autopilot_profiles(self):
        profiles_list  =  self.data['MEMConfig'].get('APProfiles', {}).get('APProfile', [])
        
        # Ensure profiles_list is always a list
        if isinstance(profiles_list, dict):  # Single profile case
            profiles_list = [profiles_list]
        elif isinstance(profiles_list, str):  # Unexpected case to be handled as an empty list
            profiles_list = []

        profile_details  =  []
        for profile in profiles_list:
            groups_within_profile  =  []
            assignments  =  profile.get('Assignments', {}).get('Group', [])
            if isinstance(assignments, dict):
                assignments  =  [assignments]

            for group in assignments:
                # Compliance Policies
                compliance_policies_data  =  group.get('CompliancePolicies', {})
                compliance_count  =  int(compliance_policies_data.get('NumberOfCompliancePolicies', 0))

                # Device Configurations
                device_configs  =  []
                device_config_data  =  group.get('DeviceConfigurations', {})
                device_config_count  =  int(device_config_data.get('NumberOfDeviceConfigurations', 0))
                
                if isinstance(device_config_data, dict):
                    device_config_data  =  [device_config_data]

                for config in device_config_data:
                    device_configuration  =  config.get('DeviceConfiguration')
                    if isinstance(device_configuration, list):
                        for individual_config in device_configuration:
                            device_configs.append(GroupAssignmentNest(
                                count =  device_config_count,
                                name =  individual_config.get('@Name', None),
                                display_name =  individual_config.get('DisplayName', None)
                            ))
                    elif isinstance(device_configuration, dict):
                        device_configs.append(GroupAssignmentNest(
                            count =  device_config_count,
                            name =  device_configuration.get('@Name', None),
                            display_name =  device_configuration.get('DisplayName', None)
                        ))

                # PowerShell Scripts
                ps_scripts  =  []
                ps_scripts_data  =  group.get('DevicePowerShellScripts', {})
                ps_script_count  =  int(ps_scripts_data.get('NumberOfPowerShellScripts', 0))

                if isinstance(ps_scripts_data, dict):
                    ps_scripts_data  =  [ps_scripts_data]

                for script in ps_scripts_data:
                    ps_script  =  script.get('PowerShellScript')
                    if isinstance(ps_script, list):
                        for individual_script in ps_script:
                            ps_scripts.append(GroupAssignmentNest(
                                count =  ps_script_count,
                                name =  individual_script.get('@Name', None),
                                display_name =  individual_script.get('DisplayName', None)
                            ))
                    elif isinstance(ps_script, dict):
                        ps_scripts.append(GroupAssignmentNest(
                            count =  ps_script_count,
                            name =  ps_script.get('@Name', None),
                            display_name =  ps_script.get('DisplayName', None)
                        ))

                # Administrative Templates
                admin_templates  =  []
                admin_templates_data  =  group.get('DeviceAdministrativeTemplates', {})
                admin_template_count  =  int(admin_templates_data.get('NumberOfAdminTemplates', 0))

                if isinstance(admin_templates_data, dict):
                    admin_templates_data  =  [admin_templates_data]

                for template in admin_templates_data:
                    admin_template  =  template.get('AdministrativeTemplate')
                    if isinstance(admin_template, list):
                        for individual_template in admin_template:
                            admin_templates.append(GroupAssignmentNest(
                                count =  admin_template_count,
                                name =  individual_template.get('@Name', None),
                                display_name =  individual_template.get('DisplayName', None)
                            ))
                    elif isinstance(admin_template, dict):
                        admin_templates.append(GroupAssignmentNest(
                            count =  admin_template_count,
                            name =  admin_template.get('@Name', None),
                            display_name =  admin_template.get('DisplayName', None)
                        ))

                groups_list  =  AssignmentGroupsWithinAPProfile(
                    display_name =  group.get('DisplayName', None),
                    id =  group.get('ID', None),
                    description =  group.get('Description', None),
                    type =  group.get('Type', None),
                    membership_rule =  group.get('MembershipRule', None),
                    security_enabled =  group.get('SecurityEnabled', None),
                    device_members_count =  int(group.get('DeviceMembers', 0)),
                    config_man_policy =  group.get('ConfigManPolicyAssigned', 'False')  ==  'True',
                    nested_groups =  group.get('NestedGroups', 'False')  ==  'True',
                    compliance_policies  =  [compliance_count],  # Store count only once
                    device_configs =  device_configs,
                    ps_scripts =  ps_scripts,
                    admin_templates =  admin_templates,
                    win32_lob_app_mix = group.get('Win32LOBAppMix', 'False') == 'True',
                    num_of_apps_assigned = int(group.get('ApplicationsAssigned',{}).get('NumberofApplications', 0))
                )
                groups_within_profile.append(groups_list)

            ap_profile  =  APProfile(
                display_name =  profile.get('DisplayName', None),
                profile_id =  profile.get('ID', None),
                description =  profile.get('Description', None),
                join_to_azure_ad_as =  profile.get('JointoAzureADAs', None),
                deployment_mode =  profile.get('DeploymentMode', None),
                language =  profile.get('Language', None),
                extract_hardware_hash =  profile.get('ExtractHardwareHash', 'False')  ==  'True',
                device_name_template =  profile.get('DeviceNameTemplate', None),
                device_type =  profile.get('DeviceType', None),
                enable_pre_provisioning = profile.get('EnablePreProvisioning', 'False')  ==  'True',
                role_scope_tag_ids = profile.get('RoleScoprTagIds', None),
                hide_privacy_settings = profile.get('HidePrivacySettings', 'False')  ==  'True',
                hide_eula = profile.get('HideEULA', 'False')  ==  'True',
                user_type = profile.get('UserType', None),
                skip_keyboard_selection = profile.get('SkipKeyboardSelection', 'False')  ==  'True',
                hide_escape_link = profile.get('HideEscapeLink', 'False')  ==  'True',
                assignment_target = profile.get('AssignmentTarget', None),
                excluded_groups = profile.get('ExcludedGroups', None),
                groups = groups_within_profile
            )
            profile_details.append(ap_profile)
        return profile_details
    
    def get_applications_and_dependencies(self):
        applications_list = self.data['MEMConfig'].get('APProfiles', {}).get('APProfile', [])

        # Ensure applications_list is always a list
        if isinstance(applications_list, dict):  # Single profile case
            applications_list = [applications_list]
        elif isinstance(applications_list, str):
            applications_list = []

        apps_details = []
        app_dependencies = []

        for apps in applications_list:
            app_count_data = apps.get('Assignments', {}).get('Group', [])
            if isinstance(app_count_data, dict):  # Single group case
                app_count_data = [app_count_data]

            for group in app_count_data:
                applications_assigned = group.get('ApplicationsAssigned', {})
                if not isinstance(applications_assigned, dict):
                    continue

                application_count = int(applications_assigned.get('NumberOfApplications', 0) or 0)
                applications = applications_assigned.get('Application', [])
                if isinstance(applications, dict):
                    applications = [applications]

                for app in applications:
                    dependencies_data = app.get('DependencyApps', [])
                    if isinstance(dependencies_data, dict):
                        dependencies_data = [dependencies_data]

                    # Process dependencies
                    for dependencies in dependencies_data:
                        app_dependencies_details = AppDependencies(
                            target_name=dependencies.get('TargetName', 'Unknown'),
                            target_id=dependencies.get('TargetID', None),
                            target_publisher=dependencies.get('TargetPublisher', 'Unknown'),
                            target_type=dependencies.get('TargetType', 'Unknown'),
                            target_dependency_type=dependencies.get('TargetDependencyType', 'Unknown'),
                            dependency_apps=dependencies.get('DependencyApps', []),
                            dependency_app_count=int(dependencies.get('DependentAppCount', 0).replace(' ', '')) if dependencies.get('DependentAppCount') else 0,
                            dependency_id=dependencies.get('DependencyID', None),
                        )
                        app_dependencies.append(app_dependencies_details)

                    # Process application details
                    app_details = Application(
                        display_name=app.get('DisplayName', 'Unknown'),
                        app_id=app.get('ID', None),
                        app_assign_type=app.get('AppAssignType', 'Unknown'),
                        description=app.get('Description', 'No description'),
                        publisher=app.get('Publisher', 'Unknown'),
                        app_type=app.get('Type', 'Unknown'),
                        filename=app.get('Filename', 'Unknown'),
                        size=app.get('Size', '0'),
                        install_cmd=app.get('InstallCmd', 'N/A'),
                        uninstall_cmd=app.get('UninstallCmd', 'N/A'),
                        dependent_app_count=int(app.get('DependentAppCount', 0).replace(' ', '')) if app.get('DependentAppCount') else 0,
                        run_as_acct=app.get('RunAsAccount', 'System'),
                        restart_behavior=app.get('RestartBehavior', 'Default'),
                        return_codes=app.get('ReturnCode', []),
                        rule_type=app.get('RuleType', 'None'),
                        app_dependencies=app_dependencies
                    )
                    apps_details.append((application_count, app_details))

        return apps_details, app_dependencies

