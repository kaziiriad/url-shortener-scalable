#!/bin/bash

# MongoDB Complete Cleanup and Reinstall Script
# This script will completely remove MongoDB and reinstall it properly

echo "Starting MongoDB cleanup and reinstall..."

# Connect to MongoDB server
MONGO_SERVER="10.0.2.77"
SSH_KEY="~/.ssh/url-shortener-keypair.id_rsa"
BASTION_SERVER="13.229.184.71"

echo "Connecting to MongoDB server via bastion..."

# Create cleanup script to run on MongoDB server
cat > /tmp/mongodb_cleanup.sh << 'EOF'
#!/bin/bash

echo "=== MongoDB Cleanup Script ==="

# Stop MongoDB services
echo "Stopping MongoDB services..."
sudo systemctl stop mongodb 2>/dev/null || true
sudo systemctl stop mongod 2>/dev/null || true

# Disable services
echo "Disabling MongoDB services..."
sudo systemctl disable mongodb 2>/dev/null || true
sudo systemctl disable mongod 2>/dev/null || true

# Remove MongoDB packages
echo "Removing MongoDB packages..."
sudo apt-get remove --purge -y mongodb-org* mongodb* 2>/dev/null || true

# Remove MongoDB directories
echo "Removing MongoDB directories..."
sudo rm -rf /var/lib/mongodb
sudo rm -rf /var/log/mongodb
sudo rm -rf /etc/mongodb*
sudo rm -rf /etc/mongod*

# Remove MongoDB repositories
echo "Removing MongoDB repositories..."
sudo rm -f /etc/apt/sources.list.d/mongodb*
sudo rm -f /usr/share/keyrings/mongodb*

# Remove MongoDB user
echo "Removing MongoDB user..."
sudo userdel -r mongodb 2>/dev/null || true

# Clean up systemd files
echo "Cleaning up systemd files..."
sudo rm -f /etc/systemd/system/mongodb.service
sudo rm -f /etc/systemd/system/mongod.service
sudo systemctl daemon-reload

# Clean apt cache
echo "Cleaning apt cache..."
sudo apt-get update
sudo apt-get autoremove -y
sudo apt-get autoclean

echo "=== MongoDB cleanup completed ==="
EOF

# Copy and run cleanup script on MongoDB server
echo "Copying cleanup script to MongoDB server..."
scp -i $SSH_KEY -o ProxyCommand="ssh -i $SSH_KEY -W %h:%p ubuntu@$BASTION_SERVER" /tmp/mongodb_cleanup.sh ubuntu@$MONGO_SERVER:/tmp/

echo "Running cleanup script on MongoDB server..."
ssh -i $SSH_KEY -o ProxyCommand="ssh -i $SSH_KEY -W %h:%p ubuntu@$BASTION_SERVER" ubuntu@$MONGO_SERVER "chmod +x /tmp/mongodb_cleanup.sh && sudo /tmp/mongodb_cleanup.sh"

echo "Cleanup completed. Now running Ansible playbook to reinstall MongoDB..."

# Run Ansible playbook to reinstall MongoDB
cd /mnt/e/url_shortener_scalable
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbook.yml --limit mongo-server

echo "MongoDB cleanup and reinstall completed!"
