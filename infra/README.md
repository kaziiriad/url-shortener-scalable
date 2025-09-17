# Infrastructure as Code - URL Shortener

This directory contains the Pulumi infrastructure code for deploying the URL Shortener application to AWS.

## File Structure

```
infra/
├── __main__.py          # Main Pulumi infrastructure code
├── ansible_config.py    # Ansible configuration generation
├── requirements.txt     # Python dependencies
├── Pulumi.yaml         # Pulumi project configuration
└── README.md           # This file
```

## Key Components

### `__main__.py`
- **VPC Configuration**: Creates VPC with public and private subnets
- **Security Groups**: Configures firewall rules for all services
- **EC2 Instances**: Deploys all required servers (load balancer, app servers, databases, etc.)
- **Ansible Integration**: Automatically generates inventory and group variables

### `ansible_config.py`
- **Inventory Generation**: Creates `ansible/inventory/hosts.yml` with all server IPs
- **Group Variables**: Creates `ansible/group_vars/all.yml` with all configuration
- **Provisioning**: Optional automatic Ansible deployment

## Architecture

The infrastructure deploys:

- **1 Bastion Host** (public subnet) - SSH access point
- **1 Load Balancer** (public subnet) - Nginx load balancer
- **3 App Servers** (private subnet) - FastAPI application instances
- **1 Redis Server** (private subnet) - Cache and message broker
- **1 PostgreSQL Server** (private subnet) - Key management database
- **1 MongoDB Server** (private subnet) - URL storage database
- **1 Celery Worker** (private subnet) - Background task processor
- **1 Celery Beat** (private subnet) - Task scheduler
- **1 Celery Flower** (private subnet) - Task monitoring dashboard

## Deployment

### Prerequisites
1. **AWS Credentials**: Configure with `aws configure`
2. **Pulumi**: Install Pulumi CLI
3. **Python Dependencies**: `pip install -r requirements.txt`

### Deploy Infrastructure
```bash
cd infra
pulumi up --yes
```

### Deploy Application
```bash
cd ../ansible
ansible-playbook -i inventory/hosts.yml site.yml
```

## Features

### Automatic Ansible Integration
- **Inventory Generation**: Automatically creates Ansible inventory with all server IPs
- **Group Variables**: Populates all configuration variables
- **SSH Configuration**: Sets up proper bastion host access
- **Dependency Management**: Ensures proper deployment order

### Security
- **Private Subnets**: All application servers are in private subnets
- **Bastion Host**: Secure SSH access through bastion host only
- **Security Groups**: Restrictive firewall rules
- **No Public IPs**: Database and app servers have no direct internet access

### Scalability
- **Load Balancing**: Nginx distributes traffic across 3 app servers
- **Horizontal Scaling**: Easy to add more app servers
- **Microservices**: Each service runs on dedicated instances

## Configuration

### Environment Variables
The infrastructure uses these key variables:
- `instance_type`: EC2 instance type (default: t2.micro)
- `ami`: Ubuntu AMI ID
- `key_name`: SSH key pair name

### Ansible Variables
All Ansible variables are automatically generated in `group_vars/all.yml`:
- Server IP addresses
- Database credentials
- Application configuration
- Network ports
- Security settings

## Monitoring

### Health Checks
- Application health: `http://<lb-ip>/health`
- Load balancer status: Check Nginx logs
- Database connectivity: Check service logs

### Logs
- Application logs: `/var/log/url_shortener/`
- Load balancer logs: `/var/log/nginx/`
- Database logs: Service-specific log directories

## Troubleshooting

### Common Issues
1. **AWS Credentials**: Ensure credentials are properly configured
2. **SSH Access**: Use bastion host for private instance access
3. **Security Groups**: Check firewall rules if services can't connect
4. **Dependencies**: Ensure all instances are running before Ansible deployment

### Useful Commands
```bash
# Check Pulumi stack status
pulumi stack output

# SSH to bastion host
ssh -i <key>.pem ubuntu@<bastion-ip>

# SSH to private instance via bastion
ssh -i <key>.pem -o ProxyCommand="ssh -i <key>.pem -W %h:%p ubuntu@<bastion-ip>" ubuntu@<private-ip>

# Check Ansible inventory
ansible all -i inventory/hosts.yml -m ping
```

## Cost Optimization

- **t2.micro instances**: Free tier eligible
- **Single AZ deployment**: Reduces costs
- **EBS volumes**: Only for necessary data persistence
- **NAT Gateway**: Consider NAT Instance for cost savings

## Security Considerations

- **Change default passwords** in production
- **Use AWS Secrets Manager** for sensitive data
- **Enable VPC Flow Logs** for monitoring
- **Regular security updates** on all instances
- **Restrict bastion host access** to specific IP ranges
