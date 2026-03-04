#!/bin/bash

# Script to generate PgBouncer userlist.txt with MD5 password hash
# Usage: ./generate-pgbouncer-auth.sh [username] [password]

USERNAME="${1:-postgres}"
PASSWORD="${2:-pgpassword}"

# Generate MD5 hash in PostgreSQL format: md5(password + username)
# This matches PostgreSQL's auth system
HASH=$(echo -n "${PASSWORD}${USERNAME}" | md5sum | cut -d' ' -f1)
MD5_HASH="md5${HASH}"

echo "Generating PgBouncer authentication file..."
echo ""
echo "Username: ${USERNAME}"
echo "Password: ${PASSWORD}"
echo "MD5 Hash: ${MD5_HASH}"
echo ""

# Create userlist.txt
cat > userlist.txt << EOF
"${USERNAME}" "${MD5_HASH}"
EOF

echo "✅ Created userlist.txt with authentication credentials"
echo ""
echo "File contents:"
cat userlist.txt
echo ""
echo "You can now use this file with PgBouncer"
