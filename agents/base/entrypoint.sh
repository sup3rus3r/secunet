#!/bin/bash
set -e

echo "[SecuNet] Running apt-get update && upgrade..."
apt-get update -qq && apt-get upgrade -y -qq
echo "[SecuNet] System up to date."

exec "$@"
