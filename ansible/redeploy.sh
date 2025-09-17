#!/bin/bash

# Redeploy script for URL Shortener application
# This script will clean up existing deployments and redeploy fresh

set -e

echo "🧹 Starting cleanup and redeploy process..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "playbook.yml" ]; then
    print_error "Please run this script from the ansible directory"
    exit 1
fi

# Set variables
INVENTORY="inventory/hosts.yml"
KEY_FILE="~/.ssh/url-shortener-keypair.id_rsa"

print_status "Step 1: Cleaning up existing deployments..."
ansible-playbook cleanup.yml -i $INVENTORY --private-key $KEY_FILE --limit "app_servers:celery_services"

if [ $? -eq 0 ]; then
    print_status "✅ Cleanup completed successfully"
else
    print_warning "⚠️  Cleanup had some issues, but continuing..."
fi

print_status "Step 2: Deploying databases first..."
ansible-playbook playbook.yml -i $INVENTORY --private-key $KEY_FILE --limit "databases"

if [ $? -eq 0 ]; then
    print_status "✅ Database deployment completed"
else
    print_error "❌ Database deployment failed"
    exit 1
fi

print_status "Step 3: Deploying app servers..."
ansible-playbook playbook.yml -i $INVENTORY --private-key $KEY_FILE --limit "app_servers"

if [ $? -eq 0 ]; then
    print_status "✅ App servers deployment completed"
else
    print_error "❌ App servers deployment failed"
    exit 1
fi

print_status "Step 4: Deploying celery services..."
ansible-playbook playbook.yml -i $INVENTORY --private-key $KEY_FILE --limit "celery_services"

if [ $? -eq 0 ]; then
    print_status "✅ Celery services deployment completed"
else
    print_error "❌ Celery services deployment failed"
    exit 1
fi

print_status "Step 5: Deploying load balancer..."
ansible-playbook playbook.yml -i $INVENTORY --private-key $KEY_FILE --limit "load_balancer"

if [ $? -eq 0 ]; then
    print_status "✅ Load balancer deployment completed"
else
    print_error "❌ Load balancer deployment failed"
    exit 1
fi

print_status "🎉 All deployments completed successfully!"
print_status "You can now test the application at: http://54.169.100.144"
