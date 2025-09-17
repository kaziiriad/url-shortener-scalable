"""
Ansible configuration generation for URL Shortener deployment.
This module handles the creation of Ansible inventory and group variables.
"""

import pulumi
from pulumi_command import local


def create_ansible_inventory(
    bastion_instance,
    lb_instance,
    app_server_instances,
    redis_instance,
    postgres_instance,
    mongo_instance,
    celery_worker_instance,
    celery_beat_instance,
    celery_flower_instance,
    key_name
):
    """Create Ansible inventory file with all server configurations."""
    
    inventory_content = pulumi.Output.all(
        bastion_public_ip=bastion_instance.public_ip,
        lb_public_ip=lb_instance.public_ip,
        app_server_1_private_ip=app_server_instances[0].private_ip,
        app_server_2_private_ip=app_server_instances[1].private_ip,
        app_server_3_private_ip=app_server_instances[2].private_ip,
        redis_private_ip=redis_instance.private_ip,
        postgres_private_ip=postgres_instance.private_ip,
        mongo_private_ip=mongo_instance.private_ip,
        celery_worker_private_ip=celery_worker_instance.private_ip,
        celery_beat_private_ip=celery_beat_instance.private_ip,
        celery_flower_private_ip=celery_flower_instance.private_ip,
    ).apply(lambda args: f"""---
all:
  children:
    load_balancer:
      hosts:
        lb-server:
          ansible_host: "{args['lb_public_ip']}"
          ansible_user: ubuntu
          ansible_ssh_private_key_file: "~/.ssh/{key_name}.id_rsa"
          server_type: load_balancer
          nginx_config: nginx-lb.conf
          ports:
            - 80
            - 443
            - 22

    app_servers:
      hosts:
        app-server-1:
          ansible_host: "{args['app_server_1_private_ip']}"
          ansible_user: ubuntu
          ansible_ssh_private_key_file: "~/.ssh/{key_name}.id_rsa"
          ansible_ssh_common_args: '-o ProxyCommand="ssh -i ../{key_name}.pem -W %h:%p ubuntu@{args['bastion_public_ip']}"'
          server_type: application
          instance_id: 1
          ports:
            - 8000
            - 22
        app-server-2:
          ansible_host: "{args['app_server_2_private_ip']}"
          ansible_user: ubuntu
          ansible_ssh_private_key_file: "~/.ssh/{key_name}.id_rsa"
          ansible_ssh_common_args: '-o ProxyCommand="ssh -i ../{key_name}.pem -W %h:%p ubuntu@{args['bastion_public_ip']}"'
          server_type: application
          instance_id: 2
          ports:
            - 8000
            - 22
        app-server-3:
          ansible_host: "{args['app_server_3_private_ip']}"
          ansible_user: ubuntu
          ansible_ssh_private_key_file: "~/.ssh/{key_name}.id_rsa"
          ansible_ssh_common_args: '-o ProxyCommand="ssh -i ../{key_name}.pem -W %h:%p ubuntu@{args['bastion_public_ip']}"'
          server_type: application
          instance_id: 3
          ports:
            - 8000
            - 22

    databases:
      hosts:
        redis-server:
          ansible_host: "{args['redis_private_ip']}"
          ansible_user: ubuntu
          ansible_ssh_private_key_file: "~/.ssh/{key_name}.id_rsa"
          ansible_ssh_common_args: '-o ProxyCommand="ssh -i ../{key_name}.pem -W %h:%p ubuntu@{args['bastion_public_ip']}"'
          server_type: redis
          ports:
            - 6379
            - 22
        postgres-server:
          ansible_host: "{args['postgres_private_ip']}"
          ansible_user: ubuntu
          ansible_ssh_private_key_file: "~/.ssh/{key_name}.id_rsa"
          ansible_ssh_common_args: '-o ProxyCommand="ssh -i ../{key_name}.pem -W %h:%p ubuntu@{args['bastion_public_ip']}"'
          server_type: postgres
          ports:
            - 5432
            - 22
        mongo-server:
          ansible_host: "{args['mongo_private_ip']}"
          ansible_user: ubuntu
          ansible_ssh_private_key_file: "~/.ssh/{key_name}.id_rsa"
          ansible_ssh_common_args: '-o ProxyCommand="ssh -i ../{key_name}.pem -W %h:%p ubuntu@{args['bastion_public_ip']}"'
          server_type: mongodb
          ports:
            - 27017
            - 22

    celery_services:
      hosts:
        celery-worker:
          ansible_host: "{args['celery_worker_private_ip']}"
          ansible_user: ubuntu
          ansible_ssh_private_key_file: "~/.ssh/{key_name}.id_rsa"
          ansible_ssh_common_args: '-o ProxyCommand="ssh -i ../{key_name}.pem -W %h:%p ubuntu@{args['bastion_public_ip']}"'
          server_type: celery_worker
          ports:
            - 22
        celery-beat:
          ansible_host: "{args['celery_beat_private_ip']}"
          ansible_user: ubuntu
          ansible_ssh_private_key_file: "~/.ssh/{key_name}.id_rsa"
          ansible_ssh_common_args: '-o ProxyCommand="ssh -i ../{key_name}.pem -W %h:%p ubuntu@{args['bastion_public_ip']}"'
          server_type: celery_beat
          ports:
            - 22
        celery-flower:
          ansible_host: "{args['celery_flower_private_ip']}"
          ansible_user: ubuntu
          ansible_ssh_private_key_file: "~/.ssh/{key_name}.id_rsa"
          ansible_ssh_common_args: '-o ProxyCommand="ssh -i ../{key_name}.pem -W %h:%p ubuntu@{args['bastion_public_ip']}"'
          server_type: celery_flower
          ports:
            - 5555
            - 22

    bastion:
      hosts:
        bastion-server:
          ansible_host: "{args['bastion_public_ip']}"
          ansible_user: ubuntu
          ansible_ssh_private_key_file: "~/.ssh/{key_name}.id_rsa"
          server_type: bastion
          ports:
            - 22
""")

    # Create the inventory file using a local command
    create_inventory = local.Command("create-inventory",
        create=pulumi.Output.concat("echo '", inventory_content, "' > ../ansible/inventory/hosts.yml"),
        opts=pulumi.ResourceOptions(depends_on=[
            bastion_instance, lb_instance, 
            app_server_instances[0], app_server_instances[1], app_server_instances[2],
            redis_instance, postgres_instance, mongo_instance,
            celery_worker_instance, celery_beat_instance, celery_flower_instance
        ])
    )
    
    return create_inventory


def create_ansible_group_vars(
    bastion_instance,
    lb_instance,
    app_server_instances,
    redis_instance,
    postgres_instance,
    mongo_instance,
    celery_worker_instance,
    celery_beat_instance,
    celery_flower_instance,
    private_subnet,
    key_name,
    playbook_dir,
    project_dir
):
    """Create Ansible group variables file with all configuration."""
    
    group_vars_content = pulumi.Output.all(
        bastion_public_ip=bastion_instance.public_ip,
        lb_public_ip=lb_instance.public_ip,
        app_server_1_private_ip=app_server_instances[0].private_ip,
        app_server_2_private_ip=app_server_instances[1].private_ip,
        app_server_3_private_ip=app_server_instances[2].private_ip,
        redis_private_ip=redis_instance.private_ip,
        postgres_private_ip=postgres_instance.private_ip,
        mongo_private_ip=mongo_instance.private_ip,
        celery_worker_private_ip=celery_worker_instance.private_ip,
        celery_beat_private_ip=celery_beat_instance.private_ip,
        celery_flower_private_ip=celery_flower_instance.private_ip,
        private_subnet_cidr=private_subnet.cidr_block,
        playbook_dir=playbook_dir,
        key_name=key_name,
        project_dir=project_dir
    ).apply(lambda args: f"""# =============================================================================
# PULUMI STACK OUTPUTS (Auto-generated)
# =============================================================================
bastion_public_ip: {args['bastion_public_ip']}
lb_public_ip: {args['lb_public_ip']}
app_server_1_private_ip: {args['app_server_1_private_ip']}
app_server_2_private_ip: {args['app_server_2_private_ip']}
app_server_3_private_ip: {args['app_server_3_private_ip']}
redis_private_ip: {args['redis_private_ip']}
postgres_private_ip: {args['postgres_private_ip']}
mongo_private_ip: {args['mongo_private_ip']}
celery_worker_private_ip: {args['celery_worker_private_ip']}
celery_beat_private_ip: {args['celery_beat_private_ip']}
celery_flower_private_ip: {args['celery_flower_private_ip']}
private_subnet_cidr: {args['private_subnet_cidr']}

# =============================================================================
# SSH CONFIGURATION
# =============================================================================
key_file_path: "~/.ssh/{key_name}.id_rsa"

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================
postgres_user: "url_shortener_user"
postgres_password: "pgpassword"
postgres_db: "url_shortener_keys"

redis_password: ""

mongo_db_name: "url_shortener_db"



# =============================================================================
# APPLICATION CONFIGURATION
# =============================================================================
app_name: "url_shortener"
app_user: "ubuntu"
app_group: "ubuntu"
app_home: "/home/{{{{ app_user }}}}/{{{{ app_name }}}}"
app_source_dir: "/opt/{{{{ app_name }}}}"
playbook_dir: {args['playbook_dir']}
project_dir: {args['project_dir']}
# =============================================================================
# DOCKER CONFIGURATION
# =============================================================================
docker_compose_version: "2.24.0"
docker_compose_install_path: "/usr/local/bin/docker-compose"

# =============================================================================
# NETWORK PORTS
# =============================================================================
app_port: 8000
redis_port: 6379
postgres_port: 5432
mongo_port: 27017
flower_port: 5555

# =============================================================================
# CELERY CONFIGURATION
# =============================================================================
celery_worker_concurrency: 4
celery_beat_schedule_file: "/tmp/celerybeat-schedule"
key_population_count: 50
key_population_schedule: 300  # seconds
cleanup_expired_schedule: 86400  # daily

# =============================================================================
# NGINX CONFIGURATION
# =============================================================================
nginx_user: "www-data"
nginx_group: "www-data"
nginx_log_dir: "/var/log/nginx"
nginx_cache_dir: "/var/cache/nginx"

# =============================================================================
# SYSTEM CONFIGURATION
# =============================================================================
timezone: "UTC"
locale: "en_US.UTF-8"

# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================
ssh_port: 22
fail2ban_enabled: true
ufw_enabled: true

# =============================================================================
# MONITORING & LOGGING
# =============================================================================
log_level: "INFO"
""")

    # Create the group_vars file using a local command
    create_group_vars = local.Command("create-group-vars",
        create=pulumi.Output.concat("echo '", group_vars_content, "' > ../ansible/group_vars/all.yml"),
        opts=pulumi.ResourceOptions(depends_on=[
            bastion_instance, lb_instance, 
            app_server_instances[0], app_server_instances[1], app_server_instances[2],
            redis_instance, postgres_instance, mongo_instance,
            celery_worker_instance, celery_beat_instance, celery_flower_instance
        ])
    )
    
    return create_group_vars

def create_ansible_inventory_and_group_vars(
    bastion_instance,
    lb_instance,
    app_server_instances,
    redis_instance,
    postgres_instance,
    mongo_instance,
    celery_worker_instance,
    celery_beat_instance,
    celery_flower_instance,
    private_subnet,
    key_name,
    playbook_dir,
    project_dir
):
    """Create Ansible inventory and group variables files."""
    
    # create_inventory = create_ansible_inventory(
    #     bastion_instance=bastion_instance,
    #     lb_instance=lb_instance,
    #     app_server_instances=app_server_instances,
    #     redis_instance=redis_instance,
    #     postgres_instance=postgres_instance,
    #     mongo_instance=mongo_instance,
    #     celery_worker_instance=celery_worker_instance,
    #     celery_beat_instance=celery_beat_instance,
    #     celery_flower_instance=celery_flower_instance,
    #     key_name=key_name
    # )
    
    create_group_vars = create_ansible_group_vars(
        bastion_instance=bastion_instance,
        lb_instance=lb_instance,
        app_server_instances=app_server_instances,
        redis_instance=redis_instance,
        postgres_instance=postgres_instance,
        mongo_instance=mongo_instance,
        celery_worker_instance=celery_worker_instance,
        celery_beat_instance=celery_beat_instance,
        celery_flower_instance=celery_flower_instance,
        private_subnet=private_subnet,
        key_name=key_name,
        playbook_dir=playbook_dir,
        project_dir=project_dir
    )
    
    return create_group_vars

# Run ansible playbook
def run_ansible_playbook(create_group_vars, ssh_tunneling, key_name):
    """Run Ansible playbook."""
    print(key_name)
    ansible_playbook = local.Command("ansible-playbook",
        create="cd ../ansible && ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook -vvv -i inventory/hosts.yml playbook.yml -e 'ansible_ssh_private_key_file=~/.ssh/{key_name}.id_rsa'",
        opts=pulumi.ResourceOptions(depends_on=[create_group_vars, ssh_tunneling])
    )
    
    return ansible_playbook

# ansible test ssh tunneling
def ansible_test_ssh_tunneling(create_group_vars, key_name):
    """Test SSH tunneling through Ansible."""
    print("key_name")
    print(key_name)
    ansible_test_ssh_tunneling = local.Command("ansible-test-ssh-tunneling",
        create="cd ../ansible && ANSIBLE_CONFIG=ansible/ansible.cfg ansible all -m ping",
        opts=pulumi.ResourceOptions(depends_on=[create_group_vars])
    )
    
    return ansible_test_ssh_tunneling