import pulumi
import pulumi_aws as aws
import os

# variables
instance_type = 't2.micro'
ami = 'ami-01811d4912b4ccb26'  # Ubuntu 22.04 LTS in ap-southeast-1
key_name = "url-shortener-key-pair"

# Create a VPC
vpc = aws.ec2.Vpc(
    'url-shortener-vpc',
    cidr_block='10.0.0.0/16',
    enable_dns_support=True,
    enable_dns_hostnames=True,
    tags={'Name': 'url-shortener-vpc'}
)

# Create public and private subnets
public_subnet = aws.ec2.Subnet(
    'url-shortener-public-subnet',
    vpc_id=vpc.id,
    cidr_block='10.0.1.0/24',
    map_public_ip_on_launch=True,
    availability_zone='ap-southeast-1a',  
    tags={'Name': 'url-shortener-public-subnet'}
)

private_subnet = aws.ec2.Subnet(
    'url-shortener-private-subnet',
    vpc_id=vpc.id,
    cidr_block='10.0.2.0/24',
    map_public_ip_on_launch=False,
    availability_zone='ap-southeast-1a',  
    tags={'Name': 'url-shortener-private-subnet'}
)

# Create an EIP
eip = aws.ec2.Eip(
    'url-shortener-eip',
    tags={'Name': 'url-shortener-eip'}
)

# Create an internet gateway
internet_gateway = aws.ec2.InternetGateway(
    'url-shortener-internet-gateway',
    vpc_id=vpc.id,
    tags={'Name': 'url-shortener-internet-gateway'}
)

# Create a NAT gateway
nat_gateway = aws.ec2.NatGateway(
    'url-shortener-nat-gateway',
    subnet_id=public_subnet.id,
    allocation_id=eip.id,
    tags={'Name': 'url-shortener-nat-gateway'}
)

# Create a public route table
public_route_table = aws.ec2.RouteTable(
    'url-shortener-public-route-table',
    vpc_id=vpc.id,
    routes=[aws.ec2.RouteTableRouteArgs(
        cidr_block='0.0.0.0/0',
        gateway_id=internet_gateway.id
    )],
    tags={'Name': 'url-shortener-public-route-table'}
)

# Create a private route table
private_route_table = aws.ec2.RouteTable(
    'url-shortener-private-route-table',
    vpc_id=vpc.id,
    routes=[aws.ec2.RouteTableRouteArgs(
        cidr_block='0.0.0.0/0',
        nat_gateway_id=nat_gateway.id
    )],
    tags={'Name': 'url-shortener-private-route-table'}
)

# Associate route tables with subnets
public_route_table_association = aws.ec2.RouteTableAssociation(
    'url-shortener-public-route-table-association',
    subnet_id=public_subnet.id,
    route_table_id=public_route_table.id
)

private_route_table_association = aws.ec2.RouteTableAssociation(
    'url-shortener-private-route-table-association',
    subnet_id=private_subnet.id,
    route_table_id=private_route_table.id
)



# Create a security group for the load balancer
lb_security_group = aws.ec2.SecurityGroup(
    'url-shortener-lb-security-group',
    vpc_id=vpc.id,
    ingress=[
    aws.ec2.SecurityGroupIngressArgs(
        cidr_blocks=['0.0.0.0/0'],
        from_port=22,
        to_port=22,
        protocol='tcp'
    ),
    aws.ec2.SecurityGroupIngressArgs(
        cidr_blocks=['0.0.0.0/0'],
        from_port=80,
        to_port=80,
        protocol='tcp'
    ),
    aws.ec2.SecurityGroupIngressArgs(
        cidr_blocks=['0.0.0.0/0'],
        from_port=443,
        to_port=443,
        protocol='tcp'
    )],
    egress=[aws.ec2.SecurityGroupEgressArgs(
        cidr_blocks=['0.0.0.0/0'],
        from_port=0,
        to_port=0,
        protocol='-1'
    )],
    tags={'Name': 'url-shortener-lb-security-group'}
)

# Create a security group for the application
app_security_group = aws.ec2.SecurityGroup(
    'url-shortener-app-security-group',
    vpc_id=vpc.id,
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
        cidr_blocks=['10.0.1.0/24'],
        from_port=8000,
        to_port=8000,
        protocol='tcp'
    ),
    # SSH access from bastion server (will be updated after bastion SG is created)
    aws.ec2.SecurityGroupIngressArgs(
        cidr_blocks=['10.0.1.0/24'],  # Temporary - will update with bastion SG reference
        from_port=22,
        to_port=22,
        protocol='tcp'
    ),
        aws.ec2.SecurityGroupIngressArgs(
        cidr_blocks=['10.0.0.0/16'],
        from_port=80,
        to_port=80,
        protocol='tcp'
    ),
    aws.ec2.SecurityGroupIngressArgs(
        cidr_blocks=['10.0.0.0/16'],
        from_port=443,
        to_port=443,
        protocol='tcp'
    )],

    egress=[aws.ec2.SecurityGroupEgressArgs(
        cidr_blocks=['0.0.0.0/0'],
        security_groups=[],
        from_port=0,
        to_port=0,
        protocol='-1'
    )],
    tags={'Name': 'url-shortener-app-security-group'}
)

# Create a security group for the redis
redis_security_group = aws.ec2.SecurityGroup(
    'url-shortener-redis-security-group',
    vpc_id=vpc.id,
    ingress=[aws.ec2.SecurityGroupIngressArgs(
        cidr_blocks=['10.0.2.0/24'],
        from_port=6379,
        to_port=6379,
        protocol='tcp'
    ),
    # SSH access from bastion server only
    aws.ec2.SecurityGroupIngressArgs(
        cidr_blocks=['10.0.1.0/24'],  # Temporary - will update with bastion SG reference
        from_port=22,
        to_port=22,
        protocol='tcp'
    )],
    egress=[aws.ec2.SecurityGroupEgressArgs(
        cidr_blocks=['0.0.0.0/0'],
        from_port=0,
        to_port=0,
        protocol='-1'
    )],
    tags={'Name': 'url-shortener-redis-security-group'}
)

# Create a security group for the postgres
postgres_security_group = aws.ec2.SecurityGroup(
    'url-shortener-postgres-security-group',
    vpc_id=vpc.id,
    ingress=[aws.ec2.SecurityGroupIngressArgs(
        cidr_blocks=['10.0.2.0/24'],
        from_port=5432,
        to_port=5432,
        protocol='tcp'
    ),
    # SSH access from bastion server only
    aws.ec2.SecurityGroupIngressArgs(
        cidr_blocks=['10.0.1.0/24'],  # Temporary - will update with bastion SG reference
        from_port=22,
        to_port=22,
        protocol='tcp'
    )],
    egress=[aws.ec2.SecurityGroupEgressArgs(
        cidr_blocks=['0.0.0.0/0'],
        from_port=0,
        to_port=0,
        protocol='-1'
    )],
    tags={'Name': 'url-shortener-postgres-security-group'}
)

# Create a security group for the mongo
mongo_security_group = aws.ec2.SecurityGroup(
    'url-shortener-mongo-security-group',
    vpc_id=vpc.id,
    ingress=[aws.ec2.SecurityGroupIngressArgs(
        cidr_blocks=['10.0.2.0/24'],
        from_port=27017,
        to_port=27017,
        protocol='tcp'
    ),
    # SSH access from bastion server only
    aws.ec2.SecurityGroupIngressArgs(
        cidr_blocks=['10.0.1.0/24'],  # Temporary - will update with bastion SG reference
        from_port=22,
        to_port=22,
        protocol='tcp'
    )],
    egress=[aws.ec2.SecurityGroupEgressArgs(
        cidr_blocks=['0.0.0.0/0'],
        from_port=0,
        to_port=0,
        protocol='-1'
    )],
    tags={'Name': 'url-shortener-mongo-security-group'}
)

# Create a unified security group for all Celery services (Beat, Worker, Flower)
celery_services_security_group = aws.ec2.SecurityGroup(
    'url-shortener-celery-services-security-group',
    vpc_id=vpc.id,
    ingress=[
        # Celery Flower monitoring UI (only needed if accessing from outside VPC)
        aws.ec2.SecurityGroupIngressArgs(
            cidr_blocks=['10.0.0.0/16'],  # Allow from entire VPC
            from_port=5555,
            to_port=5555,
            protocol='tcp',
            description='Celery Flower monitoring UI'
        ),
        # SSH access from bastion server only
        aws.ec2.SecurityGroupIngressArgs(
            cidr_blocks=['10.0.1.0/24'],  # Temporary - will update with bastion SG reference
            from_port=22,
            to_port=22,
            protocol='tcp',
            description='SSH access from bastion server'
        )
    ],
    egress=[
        # Allow all outbound traffic (needed for Redis, PostgreSQL, MongoDB connections)
        aws.ec2.SecurityGroupEgressArgs(
            cidr_blocks=['0.0.0.0/0'],
            from_port=0,
            to_port=0,
            protocol='-1',
            description='All outbound traffic for database connections'
        )
    ],
    tags={'Name': 'url-shortener-celery-services-security-group'}
)

# Create a security group for the bastion server
bastion_security_group = aws.ec2.SecurityGroup(
    'url-shortener-bastion-security-group',
    vpc_id=vpc.id,
    ingress=[
        # SSH access from internet (restrict to your IP in production)
        aws.ec2.SecurityGroupIngressArgs(
            cidr_blocks=['0.0.0.0/0'],  # Restrict to your IP: ['YOUR_IP/32']
            from_port=22,
            to_port=22,
            protocol='tcp',
            description='SSH access from internet'
        )
    ],
    egress=[
        # Allow SSH to private instances
        aws.ec2.SecurityGroupEgressArgs(
            cidr_blocks=['10.0.0.0/16'],
            from_port=22,
            to_port=22,
            protocol='tcp',
            description='SSH to private instances'
        ),
        # Allow HTTPS for package updates
        aws.ec2.SecurityGroupEgressArgs(
            cidr_blocks=['0.0.0.0/0'],
            from_port=443,
            to_port=443,
            protocol='tcp',
            description='HTTPS for package updates'
        )
    ],
    tags={'Name': 'url-shortener-bastion-security-group'}
)

# Create the bastion server in public subnet
bastion_instance = aws.ec2.Instance(
    'url-shortener-bastion-instance',
    ami=ami,
    instance_type='t2.micro',  # Bastion doesn't need much power
    subnet_id=public_subnet.id,
    vpc_security_group_ids=[bastion_security_group.id],
    associate_public_ip_address=True,
    key_name=key_name,
    tags={'Name': 'url-shortener-bastion-server'}
)

# Create a load balancer instance
lb_instance = aws.ec2.Instance(
    'url-shortener-lb-instance',
    ami=ami,
    instance_type=instance_type,
    subnet_id=public_subnet.id,
    vpc_security_group_ids=[lb_security_group.id],
    associate_public_ip_address=True,
    key_name=key_name,
    tags={'Name': 'url-shortener-lb-instance'}
)

# App server instances (private - no public IP)
app_server_instances = []
for i in range(3):
    app_instance = aws.ec2.Instance(
        f'url-shortener-app-server-instance-{i+1}',
        ami=ami,
        instance_type=instance_type,
        subnet_id=private_subnet.id,
        vpc_security_group_ids=[app_security_group.id],
        associate_public_ip_address=False,  # No public IP
        key_name=key_name,
        tags={'Name': f'url-shortener-app-server-{i+1}'}
    )
    app_server_instances.append(app_instance)

# Redis instance (private - no public IP)
redis_instance = aws.ec2.Instance(
    'url-shortener-redis-instance',
    ami=ami,
    instance_type=instance_type,
    subnet_id=private_subnet.id,
    vpc_security_group_ids=[redis_security_group.id],
    associate_public_ip_address=False,  # No public IP
    key_name=key_name,
    tags={'Name': 'url-shortener-redis-instance'}
)

# MongoDB instance (private - no public IP)
mongo_instance = aws.ec2.Instance(
    'url-shortener-mongo-instance',
    ami=ami,
    instance_type=instance_type,
    subnet_id=private_subnet.id,
    vpc_security_group_ids=[mongo_security_group.id],
    associate_public_ip_address=False,  # No public IP
    key_name=key_name,
    tags={'Name': 'url-shortener-mongo-instance'}
)

# PostgreSQL instance (private - no public IP)
postgres_instance = aws.ec2.Instance(
    'url-shortener-postgres-instance',
    ami=ami,
    instance_type=instance_type,
    subnet_id=private_subnet.id,
    vpc_security_group_ids=[postgres_security_group.id],
    associate_public_ip_address=False,  # No public IP
    key_name=key_name,
    tags={'Name': 'url-shortener-postgres-instance'}
)

# Celery Worker instance (private - no public IP)
celery_worker_instance = aws.ec2.Instance(
    'url-shortener-celery-worker-instance',
    ami=ami,
    instance_type=instance_type,
    subnet_id=private_subnet.id,
    vpc_security_group_ids=[celery_services_security_group.id],
    associate_public_ip_address=False,  # No public IP
    key_name=key_name,
    tags={'Name': 'url-shortener-celery-worker-instance'}
)

# Celery Beat instance (private - no public IP)
celery_beat_instance = aws.ec2.Instance(
    'url-shortener-celery-beat-instance',
    ami=ami,
    instance_type=instance_type,
    subnet_id=private_subnet.id,
    vpc_security_group_ids=[celery_services_security_group.id],
    associate_public_ip_address=False,  # No public IP
    key_name=key_name,
    tags={'Name': 'url-shortener-celery-beat-instance'}
)   

# Celery Flower instance (private - no public IP)
celery_flower_instance = aws.ec2.Instance(
    'url-shortener-celery-flower-instance',
    ami=ami,
    instance_type=instance_type,
    subnet_id=private_subnet.id,
    vpc_security_group_ids=[celery_services_security_group.id],
    associate_public_ip_address=False,  # No public IP
    key_name=key_name,
    tags={'Name': 'url-shortener-celery-flower-instance'}
)   

# Add security group rules to allow SSH from bastion to private instances
# (These rules are added after bastion security group is created)

# Allow bastion to access app servers
app_bastion_rule = aws.ec2.SecurityGroupRule(
    'app-bastion-ssh-rule',
    type='ingress',
    from_port=22,
    to_port=22,
    protocol='tcp',
    source_security_group_id=bastion_security_group.id,
    security_group_id=app_security_group.id,
    description='SSH access from bastion to app servers'
)

# Allow bastion to access database servers
redis_bastion_rule = aws.ec2.SecurityGroupRule(
    'redis-bastion-ssh-rule',
    type='ingress',
    from_port=22,
    to_port=22,
    protocol='tcp',
    source_security_group_id=bastion_security_group.id,
    security_group_id=redis_security_group.id,
    description='SSH access from bastion to Redis'
)

postgres_bastion_rule = aws.ec2.SecurityGroupRule(
    'postgres-bastion-ssh-rule',
    type='ingress',
    from_port=22,
    to_port=22,
    protocol='tcp',
    source_security_group_id=bastion_security_group.id,
    security_group_id=postgres_security_group.id,
    description='SSH access from bastion to PostgreSQL'
)

mongo_bastion_rule = aws.ec2.SecurityGroupRule(
    'mongo-bastion-ssh-rule',
    type='ingress',
    from_port=22,
    to_port=22,
    protocol='tcp',
    source_security_group_id=bastion_security_group.id,
    security_group_id=mongo_security_group.id,
    description='SSH access from bastion to MongoDB'
)

# Allow bastion to access celery services
celery_bastion_rule = aws.ec2.SecurityGroupRule(
    'celery-bastion-ssh-rule',
    type='ingress',
    from_port=22,
    to_port=22,
    protocol='tcp',
    source_security_group_id=bastion_security_group.id,
    security_group_id=celery_services_security_group.id,
    description='SSH access from bastion to Celery services'
)

# Export public IPs (only for public instances)
pulumi.export('bastion_public_ip', bastion_instance.public_ip)
pulumi.export('lb_public_ip', lb_instance.public_ip)

# Export private IPs for internal reference
pulumi.export('bastion_private_ip', bastion_instance.private_ip)
for i in range(3):
    pulumi.export(f'app_server_{i+1}_private_ip', app_server_instances[i].private_ip)

pulumi.export('redis_private_ip', redis_instance.private_ip)
pulumi.export('mongo_private_ip', mongo_instance.private_ip)
pulumi.export('postgres_private_ip', postgres_instance.private_ip)
pulumi.export('celery_worker_private_ip', celery_worker_instance.private_ip)
pulumi.export('celery_beat_private_ip', celery_beat_instance.private_ip)
pulumi.export('celery_flower_private_ip', celery_flower_instance.private_ip)

# Export connection information
pulumi.export('ssh_bastion_command', pulumi.Output.concat(
    'ssh -i ../', key_name, '.pem ubuntu@', bastion_instance.public_ip
))
pulumi.export('ssh_via_bastion_example', pulumi.Output.concat(
    'ssh -i ../', key_name, '.pem -o ProxyCommand="ssh -i ../', key_name, 
    '.pem -W %h:%p ubuntu@', bastion_instance.public_ip, '" ubuntu@'
))

