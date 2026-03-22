#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# ── Outbound allowlist ──────────────────────────────────────────────────
# Only these domains can be reached from inside the container.
# Edit this list to add/remove access. DNS resolution happens at
# container start, so changes require a restart.
#
# Why allowlist?  This container may run with --dangerously-skip-permissions,
# meaning Claude Code can execute arbitrary commands without prompting.
# The firewall is the compensating control — even if code tries to
# exfiltrate data, it can only reach these destinations.

ALLOWED_DOMAINS=(
    # Anthropic — Claude Code API, docs, and telemetry
    "api.anthropic.com"
    "claude.ai"
    "code.claude.com"
    "statsig.anthropic.com"
    "sentry.io"

    # GitHub — git push/pull and API only
    # Note: githubusercontent.com deliberately excluded (serves arbitrary
    # user content). If a gh command fails needing it, add it back knowingly.
    "github.com"
    "api.github.com"

    # npm — Claude Code is installed via npm
    "registry.npmjs.org"

    # PyPI — pip install for Python dev deps
    "pypi.org"
    "files.pythonhosted.org"
)

# ── Firewall setup ──────────────────────────────────────────────────────

# Preserve Docker's internal DNS rules before flushing
DOCKER_DNS_RULES=$(iptables-save -t nat | grep "127\.0\.0\.11" || true)

# Clean slate
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X
ipset destroy allowed-domains 2>/dev/null || true

# Restore Docker DNS (containers need this to resolve service names)
if [ -n "$DOCKER_DNS_RULES" ]; then
    iptables -t nat -N DOCKER_OUTPUT 2>/dev/null || true
    iptables -t nat -N DOCKER_POSTROUTING 2>/dev/null || true
    while IFS= read -r rule; do
        iptables -t nat $rule 2>/dev/null || true
    done <<< "$DOCKER_DNS_RULES"
fi

# Always allow: DNS queries, localhost, SSH
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A INPUT -p udp --sport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --sport 22 -m state --state ESTABLISHED -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Allow host network (needed for Docker<->host communication)
HOST_IP=$(ip route | grep default | cut -d" " -f3)
if [ -n "$HOST_IP" ]; then
    HOST_NETWORK=$(echo "$HOST_IP" | sed "s/\.[0-9]*$/.0\/24/")
    iptables -A INPUT -s "$HOST_NETWORK" -j ACCEPT
    iptables -A OUTPUT -d "$HOST_NETWORK" -j ACCEPT
fi

# Resolve allowed domains to IPs and build the ipset
ipset create allowed-domains hash:net
echo "Resolving ${#ALLOWED_DOMAINS[@]} allowed domains..."

for domain in "${ALLOWED_DOMAINS[@]}"; do
    ips=$(dig +noall +answer A "$domain" 2>/dev/null | awk '$4 == "A" {print $5}')
    if [ -n "$ips" ]; then
        count=0
        while IFS= read -r ip; do
            ipset add allowed-domains "$ip" 2>/dev/null || true
            count=$((count + 1))
        done <<< "$ips"
        echo "  $domain -> $count IPs"
    else
        echo "  $domain -> FAILED to resolve (will be blocked)"
    fi
done

# Default policy: drop everything, then poke holes
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# Allow responses to connections we initiated
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow outbound only to whitelisted IPs
iptables -A OUTPUT -m set --match-set allowed-domains dst -j ACCEPT

# Reject (not drop) everything else — gives immediate feedback instead of timeout
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited

echo ""
echo "Firewall active. Outbound restricted to:"
printf '  - %s\n' "${ALLOWED_DOMAINS[@]}"
echo ""
echo "To test: 'curl https://example.com' should fail immediately."
echo "         'curl https://api.anthropic.com' should succeed."
