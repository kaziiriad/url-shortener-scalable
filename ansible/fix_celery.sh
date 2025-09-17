#!/bin/bash

# Fix Celery services script
# This script will clean up and redeploy Celery services

set -e

echo "🔧 Fixing Celery services..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Set variables
INVENTORY="inventory/hosts.yml"
KEY_FILE="~/.ssh/url-shortener-keypair.id_rsa"

print_status "Step 1: Stopping and disabling all Celery services..."
ansible celery_services -m shell -a "sudo systemctl stop celery-worker celery-beat celery-flower || true" -i $INVENTORY --private-key $KEY_FILE
ansible celery_services -m shell -a "sudo systemctl disable celery-worker celery-beat celery-flower || true" -i $INVENTORY --private-key $KEY_FILE

print_status "Step 2: Removing old service files..."
ansible celery_services -m shell -a "sudo rm -f /etc/systemd/system/celery-*.service" -i $INVENTORY --private-key $KEY_FILE

print_status "Step 3: Reloading systemd daemon..."
ansible celery_services -m shell -a "sudo systemctl daemon-reload" -i $INVENTORY --private-key $KEY_FILE

print_status "Step 4: Redeploying Celery services..."
ansible-playbook playbook.yml -i $INVENTORY --private-key $KEY_FILE --limit celery_services

if [ $? -eq 0 ]; then
    print_status "✅ Celery services fixed and deployed successfully!"
else
    print_error "❌ Celery services deployment failed"
    exit 1
fi

print_status "Step 5: Checking service status..."
ansible celery_services -m shell -a "systemctl status celery-worker celery-beat celery-flower --no-pager" -i $INVENTORY --private-key $KEY_FILE
