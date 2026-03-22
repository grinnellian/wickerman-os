# Dev Container Firewall — Threat Matrix

## Threat model

The container runs Claude Code with `--dangerously-skip-permissions` (yolo mode),
meaning Claude can execute arbitrary commands as the `dev` user (who has
passwordless sudo). The firewall is the compensating control against data
exfiltration, supply-chain injection, and lateral movement.

**Attacker model:** Claude (or code Claude runs) attempts to reach
unauthorized network destinations from inside the container.

---

## Attack surface by option

| Threat | A: Proxy only (no caps) | B: /sandbox | C: Sidecar | D: Host-side enforcement | Current PR (proxy + iptables) |
|--------|------------------------|-------------|------------|-------------------------|-------------------------------|
| Process ignores `HTTP_PROXY` env vars | **Unrestricted outbound** | Only restricts Claude process, not others | Blocked by network routing | Blocked by host iptables/Docker networking | Blocked by container iptables |
| `sudo iptables -F` (flush rules) | N/A (no iptables) | N/A | N/A (rules not in this container) | N/A (rules on host) | **Firewall disabled** |
| `sudo kill $(pidof tinyproxy)` | Proxy down, direct outbound open | N/A | Proxy not in this container | Proxy not in this container | Proxy down, but iptables still blocks direct outbound |
| `unset HTTP_PROXY` then `curl evil.com` | **Unrestricted** | Sandbox may still enforce | Blocked by network routing | Blocked by host iptables | Blocked by iptables |
| `sudo` to modify proxy config/allowlist | Allowlist widened | Sandbox config writable | Proxy config not in this container | Proxy config not in this container | Allowlist widened |
| Credential theft (GH_TOKEN, API keys) | Exfil to any allowed domain | Exfil to any allowed domain | Exfil to any allowed domain | Exfil to any allowed domain | Exfil to any allowed domain |
| Container escape to host | **Full host access** | **Full host access** | **Full host access** | **Full host access** | **Full host access** |

### Key insight

Every in-container firewall option shares the same weakness: `sudo` can
tamper with it. The only options where Claude **cannot** disable the
firewall are C (sidecar) and D (host-side), because the enforcement
mechanism lives outside the container's control.

---

## Option analysis

### A: Proxy env vars only (no caps, no iptables)
- **Caps needed:** None
- **Enforcement:** Advisory (env vars only)
- **Verdict:** Too weak. Any process that ignores env vars (Node.js native
  fetch <22, direct socket calls, `curl --noproxy`) bypasses everything.

### B: Claude Code `/sandbox` mode
- **Caps needed:** None
- **Enforcement:** Claude Code's built-in proxy + bubblewrap
- **Problems:**
  - Only restricts the Claude process, not other tools in the container
  - Must be enabled per-session (error of omission)
  - Can't run sandbox in one terminal tab and not another for different
    agent types
  - Doesn't protect container-level credentials from non-Claude processes

### C: Sidecar proxy container
- **Caps needed:** None in dev container; NET_ADMIN in sidecar only
- **Enforcement:** Network-level (Docker networking routes traffic through sidecar)
- **Problems:**
  - Devcontainer spec doesn't support sidecar networking well
  - "Fighting the tooling" — complex Docker Compose networking
  - Two containers to manage

### D: Host-side enforcement (Docker network policy)
- **Caps needed:** None in dev container
- **Enforcement:** Host iptables or Docker network rules — invisible to container
- **How it works:**
  - Run tinyproxy on the Docker host (or a host-network container)
  - Create a Docker network with no default outbound route
  - Only route through the host-side proxy
  - Container sees a network that simply doesn't connect to the internet
    except through the proxy — no caps, no in-container config to tamper with
- **Problems:**
  - Setup lives outside the repo (host config, not devcontainer.json)
  - Not portable — each developer's host needs configuration
  - More ops overhead

### Current PR: Proxy + iptables (NET_ADMIN, NET_RAW)
- **Caps needed:** NET_ADMIN (+ maybe NET_RAW for legacy iptables)
- **Enforcement:** iptables blocks direct outbound; proxy filters by domain
- **Problems:**
  - `sudo iptables -F` disables the firewall entirely
  - NET_ADMIN in yolo mode is the fox guarding the henhouse
  - Still a real improvement over IP-based ipset (solves the CDN rotation
    problem) even if the enforcement is tamper-able

---

## Risk assessment: Does NET_ADMIN + yolo endanger the host?

**Inside the container:** NET_ADMIN grants full control over the container's
network namespace (iptables, routing, interfaces). It does NOT grant access
to the host's network namespace — Docker's namespace isolation prevents that.

**Container escape:** NET_ADMIN slightly increases escape surface (e.g.,
CVE-2020-14386 used NET_RAW for a container escape via kernel bug). Dropping
unnecessary caps is defense-in-depth against future kernel vulns.

**Practical risk:** The bigger concern isn't host escape — it's that Claude
can trivially disable its own firewall with `sudo iptables -F`, making the
entire mechanism advisory rather than enforced.

---

## Recommendations

1. **Ship the current PR as-is.** It solves the real CDN/IP-staleness problem
   and is strictly better than the ipset approach. The tamper risk exists but
   requires Claude to actively circumvent the firewall.

2. **Drop NET_RAW** on this PR (test in Step 7). Modern iptables-nft doesn't
   need it. Reduces kernel escape surface.

3. **Track host-side enforcement (Option D) as a future issue.** This is the
   correct long-term architecture but requires host setup outside the repo.
   Could be a setup script or a wrapper docker-compose that creates the
   network policy.

4. **The container will have keys.** Accept this like a dev laptop — scope
   credentials tightly (fine-grained PAT, read/write on one repo only),
   rotate regularly, and monitor for anomalous API usage. The firewall limits
   *where* stolen creds can be sent, not *whether* they exist.
