#!/bin/bash

# Debug web service script
echo "🔍 Debugging web service issues..."

# Set variables
INVENTORY="inventory/hosts.yml"
KEY_FILE="~/.ssh/url-shortener-keypair.id_rsa"

echo "1. Checking .env file..."
ansible app_servers -m shell -a "ls -la /app/.env && echo '--- .env content ---' && cat /app/.env" -i $INVENTORY --private-key $KEY_FILE

echo -e "\n2. Checking systemd service file..."
ansible app_servers -m shell -a "cat /etc/systemd/system/web.service" -i $INVENTORY --private-key $KEY_FILE

echo -e "\n3. Checking if uv is accessible..."
ansible app_servers -m shell -a "which uv && uv --version" -i $INVENTORY --private-key $KEY_FILE

echo -e "\n4. Checking application structure..."
ansible app_servers -m shell -a "ls -la /app/ && ls -la /app/app/" -i $INVENTORY --private-key $KEY_FILE

echo -e "\n5. Testing manual run with same environment..."
ansible app_servers -m shell -a "cd /app && PYTHONPATH=/app UV_CACHE_DIR=/app/.uv_cache /usr/local/bin/uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 1" -i $INVENTORY --private-key $KEY_FILE

echo -e "\n6. Checking recent logs..."
ansible app_servers -m shell -a "journalctl -u web.service --no-pager -n 10" -i $INVENTORY --private-key $KEY_FILE
