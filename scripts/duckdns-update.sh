#!/bin/bash

# Project Nexus - DuckDNS Auto-Updater
# Usage: ./duckdns-update.sh <domain> <token>

DOMAIN=${1:-"project-nexus"}
TOKEN=${2:-"YOUR_DUCKDNS_TOKEN"}

echo "Updating DuckDNS for ${DOMAIN}..."
RESULT=$(curl -s "https://www.duckdns.org/update?domains=${DOMAIN}&token=${TOKEN}&ip=")

if [ "$RESULT" = "OK" ]; then
    echo "Successfully updated DuckDNS!"
else
    echo "Failed to update DuckDNS: $RESULT"
    exit 1
fi
