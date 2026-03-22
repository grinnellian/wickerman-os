#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# -- Forward proxy firewall (fail-closed) ---------------------------------
# Applies iptables default-deny FIRST, then starts tinyproxy.
# If tinyproxy fails to start, the container remains locked down
# (only DNS, SSH, and loopback work) rather than being wide open.
#
# Domain allowlist:  /etc/tinyproxy/allowlist
# Proxy config:      /etc/tinyproxy/tinyproxy.conf
#
# To add a domain at runtime (no restart needed):
#   1. Edit /etc/tinyproxy/allowlist
#   2. sudo kill -HUP $(pidof tinyproxy)

# -- Stop existing tinyproxy if running (handles re-runs) -----------------

if pidof tinyproxy > /dev/null 2>&1; then
    echo "Stopping existing tinyproxy..."
    kill "$(pidof tinyproxy)" 2>/dev/null || true
    sleep 1
fi

# -- iptables setup -------------------------------------------------------

# Preserve Docker's internal DNS NAT rules before flushing
DOCKER_DNS_RULES=$(iptables-save -t nat | grep "127\.0\.0\.11" || true)

# Clean slate
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X

# Restore Docker DNS (containers need 127.0.0.11 for service name resolution)
if [ -n "$DOCKER_DNS_RULES" ]; then
    iptables -t nat -N DOCKER_OUTPUT 2>/dev/null || true
    iptables -t nat -N DOCKER_POSTROUTING 2>/dev/null || true
    while IFS= read -r rule; do
        iptables -t nat $rule 2>/dev/null || true
    done <<< "$DOCKER_DNS_RULES"
fi

# -- Default deny (applied BEFORE proxy starts = fail-closed) -------------

iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# -- Always allowed: loopback, established, DNS, SSH, host network --------

# Loopback (apps connect to local proxy on 127.0.0.1:3128 via this)
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Established/related connections (early in chain for performance)
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# DNS (UDP 53 — needed for tinyproxy to resolve allowed domains)
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A INPUT -p udp --sport 53 -j ACCEPT

# SSH
iptables -A OUTPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --sport 22 -m state --state ESTABLISHED -j ACCEPT

# Host network (Docker gateway — needed for Docker<->host communication)
HOST_IP=$(ip route | grep default | cut -d" " -f3)
if [ -n "$HOST_IP" ]; then
    HOST_NETWORK=$(echo "$HOST_IP" | sed "s/\.[0-9]*$/.0\/24/")
    iptables -A INPUT -s "$HOST_NETWORK" -j ACCEPT
    iptables -A OUTPUT -d "$HOST_NETWORK" -j ACCEPT
fi

# -- Proxy enforcement ----------------------------------------------------
# Only the tinyproxy user can make outbound HTTP/HTTPS connections.
# Everyone else must go through the proxy (via env vars).

TINYPROXY_UID=$(id -u tinyproxy)
iptables -A OUTPUT -m owner --uid-owner "$TINYPROXY_UID" -p tcp --dport 443 -j ACCEPT
iptables -A OUTPUT -m owner --uid-owner "$TINYPROXY_UID" -p tcp --dport 80 -j ACCEPT

# Reject (not drop) unmatched outbound — gives immediate error feedback
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited

echo "iptables applied (default-deny). Starting proxy..."

# -- Start tinyproxy -------------------------------------------------------

# Create PID directory (on tmpfs, lost between container restarts)
mkdir -p /run/tinyproxy
chown tinyproxy:tinyproxy /run/tinyproxy

# Start proxy (daemonizes into background)
tinyproxy -c /etc/tinyproxy/tinyproxy.conf

# Verify it started
sleep 1
if ! pidof tinyproxy > /dev/null 2>&1; then
    echo "ERROR: tinyproxy failed to start. Check /var/log/tinyproxy/tinyproxy.log"
    echo "Firewall IS active (fail-closed). Only DNS, SSH, and loopback work."
    echo "Fix the proxy config, then re-run this script."
    exit 1
fi

echo "Forward proxy started on 127.0.0.1:3128"

# -- Summary ---------------------------------------------------------------

DOMAIN_COUNT=$(grep -cve '^\s*#' -e '^\s*$' /etc/tinyproxy/allowlist)
echo ""
echo "Firewall active. Outbound HTTP/HTTPS filtered by forward proxy."
echo "  Proxy:    http://127.0.0.1:3128"
echo "  Domains:  ${DOMAIN_COUNT} patterns in /etc/tinyproxy/allowlist"
echo "  Log:      /var/log/tinyproxy/tinyproxy.log"
echo ""
echo "To test:"
echo "  curl -x http://127.0.0.1:3128 https://api.anthropic.com  → should succeed"
echo "  curl -x http://127.0.0.1:3128 https://example.com        → should fail (403)"
echo "  curl https://example.com                                  → should fail (REJECT)"
echo ""
echo "To add a domain at runtime:"
echo "  1. sudo nano /etc/tinyproxy/allowlist"
echo "  2. sudo kill -HUP \$(pidof tinyproxy)"
