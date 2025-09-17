#!/usr/bin/env python3
"""
Script to populate Ansible inventory with Pulumi stack outputs.
This script should be run after Pulumi deployment to update the Ansible variables.
"""

import subprocess
import json
import os
import sys
import yaml

def get_pulumi_outputs():
    """Get Pulumi stack outputs as JSON."""
    try:
        # Ensure we are in the ansible directory
        infra_path = os.path.join(os.path.dirname(__file__), '..', 'infra')
        result = subprocess.run(
            ['pulumi', 'stack', 'output', '--json'],
            cwd=infra_path,
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error getting Pulumi outputs: {e}\nstderr: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error parsing Pulumi outputs or finding infra dir: {e}", file=sys.stderr)
        sys.exit(1)

def update_group_vars(pulumi_outputs):
    """Update Ansible group_vars/all.yml with Pulumi outputs, preserving comments and structure."""
    vars_file = os.path.join(os.path.dirname(__file__), 'group_vars', 'all.yml')
    try:
        with open(vars_file, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    pulumi_keys = [
        "bastion_public_ip", "lb_public_ip", "app_server_1_private_ip",
        "app_server_2_private_ip", "app_server_3_private_ip", "redis_private_ip",
        "postgres_private_ip", "mongo_private_ip", "celery_worker_private_ip",
        "celery_beat_private_ip", "celery_flower_private_ip", "private_subnet_cidr"
    ]

    new_lines = []
    # Add the new Pulumi section first
    new_lines.append("# =============================================================================\n")
    new_lines.append("# PULUMI STACK OUTPUTS (Auto-generated)\n")
    new_lines.append("# =============================================================================\n")
    for key in pulumi_keys:
        if key in pulumi_outputs and pulumi_outputs[key]:
            new_lines.append(f"{key}: {pulumi_outputs[key]}\n")

    # Now add the rest of the file, skipping the old Pulumi section
    in_pulumi_section = False
    for line in lines:
        if "PULUMI STACK OUTPUTS" in line:
            in_pulumi_section = True
        elif "SSH CONFIGURATION" in line:
            in_pulumi_section = False
        
        if not in_pulumi_section:
            is_pulumi_var = any(line.strip().startswith(k + ':') for k in pulumi_keys)
            if not is_pulumi_var:
                new_lines.append(line)

    with open(vars_file, 'w') as f:
        f.writelines(new_lines)
    print(f"Successfully updated {vars_file}")

def update_inventory(pulumi_outputs):
    """Update Ansible inventory/hosts.yml with Pulumi outputs using yaml parser."""
    inventory_file = os.path.join(os.path.dirname(__file__), 'inventory', 'hosts.yml')
    vars_file = os.path.join(os.path.dirname(__file__), 'group_vars', 'all.yml')

    try:
        with open(inventory_file, 'r') as f:
            # Using safe_load and rebuilding is safer than regex for this file.
            inventory_data = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"Error reading or parsing {inventory_file}: {e}", file=sys.stderr)
        return

    with open(vars_file, 'r') as f:
        group_vars = yaml.safe_load(f)

    key_file_path = group_vars.get("key_file_path")
    bastion_ip = pulumi_outputs.get("bastion_public_ip")

    host_to_ip_map = {
        "lb-server": "lb_public_ip",
        "app-server-1": "app_server_1_private_ip",
        "app-server-2": "app_server_2_private_ip",
        "app-server-3": "app_server_3_private_ip",
        "redis-server": "redis_private_ip",
        "postgres-server": "postgres_private_ip",
        "mongo-server": "mongo_private_ip",
        "celery-worker": "celery_worker_private_ip",
        "celery-beat": "celery_beat_private_ip",
        "celery-flower": "celery_flower_private_ip",
        "bastion-server": "bastion_public_ip",
    }

    # This will modify the loaded inventory_data dictionary
    for group in inventory_data.get("all", {}).get("children", {}).values():
        for host, host_vars in group.get("hosts", {}).items():
            if host in host_to_ip_map:
                ip_key = host_to_ip_map[host]
                if ip_key in pulumi_outputs:
                    host_vars["ansible_host"] = pulumi_outputs[ip_key]
            
            if key_file_path:
                host_vars["ansible_ssh_private_key_file"] = key_file_path
            
            if bastion_ip and "ansible_ssh_common_args" in host_vars:
                host_vars["ansible_ssh_common_args"] = host_vars["ansible_ssh_common_args"].replace("BASTION_IP", bastion_ip)

    with open(inventory_file, 'w') as f:
        f.write("---\n")
        f.write("# Ansible Inventory for URL Shortener\n")
        f.write("# This file is auto-generated by populate_inventory.py\n\n")
        yaml.dump(inventory_data, f, default_flow_style=False, sort_keys=False)
    
    print(f"Successfully updated {inventory_file}")

if __name__ == "__main__":
    outputs = get_pulumi_outputs()
    update_group_vars(outputs)
    update_inventory(outputs)