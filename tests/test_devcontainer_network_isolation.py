"""Tests for the devcontainer network isolation configuration.

Validates that the Docker Compose, proxy, and allowlist configs are
structurally correct and enforce the security properties from issue #20.
These tests run without Docker — they validate config files only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEVCONTAINER = ROOT / ".devcontainer"
COMPOSE_FILE = ROOT / "docker-compose.dev.yml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_yaml_lite(path: Path) -> str:
    """Return raw YAML text (we parse with string checks to avoid a PyYAML dep)."""
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# docker-compose.dev.yml
# ---------------------------------------------------------------------------

class TestDockerCompose:
    """Validate docker-compose.dev.yml enforces network isolation."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.text = _load_yaml_lite(COMPOSE_FILE)

    def test_isolated_network_exists(self) -> None:
        assert "internal: true" in self.text, "isolated network must be internal"

    def test_proxy_on_both_networks(self) -> None:
        # The proxy service must be on both isolated and default networks
        assert "- isolated" in self.text
        assert "- default" in self.text

    def test_dev_not_on_default_network(self) -> None:
        # Find the dev service block and check it only has isolated network.
        # The dev service should NOT reference the default network.
        dev_section = self.text.split("dev:")[1]
        # dev's networks block should only have isolated
        networks_match = re.search(r"networks:\s*\n(\s+-\s+\S+\n?)+", dev_section)
        assert networks_match is not None
        networks_block = networks_match.group(0)
        assert "isolated" in networks_block
        assert "default" not in networks_block

    def test_no_cap_add(self) -> None:
        assert "cap_add" not in self.text, "dev container must not have cap_add"
        assert "NET_ADMIN" not in self.text
        assert "NET_RAW" not in self.text

    def test_proxy_env_vars_set(self) -> None:
        for var in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
            assert var in self.text, f"{var} must be set for dev service"

    def test_no_proxy_set(self) -> None:
        assert "no_proxy=" in self.text
        assert "NO_PROXY=" in self.text

    def test_allowlist_mounted_readonly(self) -> None:
        assert "allowlist.conf:/etc/tinyproxy/allowlist:ro" in self.text

    def test_dev_depends_on_proxy(self) -> None:
        assert "depends_on:" in self.text
        assert "- proxy" in self.text

    def test_no_init_firewall_reference(self) -> None:
        assert "init-firewall" not in self.text
        assert "entrypoint" not in self.text


# ---------------------------------------------------------------------------
# Proxy Dockerfile
# ---------------------------------------------------------------------------

class TestProxyDockerfile:
    """Validate proxy/Dockerfile is minimal and correct."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.text = (DEVCONTAINER / "proxy" / "Dockerfile").read_text(encoding="utf-8")

    def test_base_image_is_alpine(self) -> None:
        assert self.text.startswith("FROM alpine:")

    def test_installs_tinyproxy(self) -> None:
        assert "tinyproxy" in self.text

    def test_runs_in_foreground(self) -> None:
        # -d flag = foreground (no daemonize)
        assert '"-d"' in self.text or "tinyproxy -d" in self.text

    def test_exposes_3128(self) -> None:
        assert "3128" in self.text


# ---------------------------------------------------------------------------
# tinyproxy.conf
# ---------------------------------------------------------------------------

class TestTinyproxyConf:
    """Validate tinyproxy.conf enforces whitelist-only mode."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.text = (DEVCONTAINER / "proxy" / "tinyproxy.conf").read_text(encoding="utf-8")

    def test_filter_default_deny(self) -> None:
        assert "FilterDefaultDeny Yes" in self.text, "Must deny unlisted domains by default"

    def test_filter_file_path(self) -> None:
        assert 'Filter "/etc/tinyproxy/allowlist"' in self.text

    def test_connect_port_443_only(self) -> None:
        assert "ConnectPort 443" in self.text

    def test_listens_on_3128(self) -> None:
        assert "Port 3128" in self.text

    def test_via_header_disabled(self) -> None:
        assert "DisableViaHeader Yes" in self.text


# ---------------------------------------------------------------------------
# allowlist.conf
# ---------------------------------------------------------------------------

class TestAllowlist:
    """Validate allowlist.conf regex patterns are well-formed."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        path = DEVCONTAINER / "allowlist.conf"
        self.lines = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    def test_has_entries(self) -> None:
        assert len(self.lines) > 0, "Allowlist must not be empty"

    def test_all_patterns_anchored(self) -> None:
        for pattern in self.lines:
            assert pattern.startswith("^"), f"Pattern must be anchored with ^: {pattern}"
            assert pattern.endswith("$"), f"Pattern must be anchored with $: {pattern}"

    def test_dots_are_escaped(self) -> None:
        """Literal dots should be escaped as \\. to prevent wildcard matching."""
        for pattern in self.lines:
            # Strip anchors for analysis
            inner = pattern[1:-1]
            # Find unescaped dots (preceded by something other than \)
            # Allow dots in character classes like [a-z]
            unescaped = re.findall(r"(?<!\\)\.", inner)
            # Filter out dots that are inside character classes
            # Simple heuristic: if the pattern has [] groups, those dots are OK
            if "[" not in inner:
                assert len(unescaped) == 0, (
                    f"Unescaped dot in pattern (use \\. for literal): {pattern}"
                )

    def test_required_domains_present(self) -> None:
        """Core domains that must be in the allowlist."""
        all_patterns = "\n".join(self.lines)
        required = [
            "api.anthropic.com",
            "github.com",
            "api.github.com",
            "pypi.org",
            "registry.npmjs.org",
        ]
        for domain in required:
            escaped = domain.replace(".", r"\.")
            assert escaped in all_patterns, f"Required domain missing: {domain}"

    def test_patterns_compile_as_regex(self) -> None:
        """All patterns must be valid regex."""
        for pattern in self.lines:
            try:
                re.compile(pattern)
            except re.error as e:
                pytest.fail(f"Invalid regex pattern '{pattern}': {e}")

    def test_no_overly_broad_patterns(self) -> None:
        """No pattern should match everything (e.g., .* without anchoring to a domain)."""
        for pattern in self.lines:
            # A pattern of just ^.*$ would match anything
            inner = pattern.lstrip("^").rstrip("$")
            assert inner not in (".*", ".+", ""), f"Overly broad pattern: {pattern}"


# ---------------------------------------------------------------------------
# devcontainer.json
# ---------------------------------------------------------------------------

class TestDevcontainerJson:
    """Validate devcontainer.json uses compose and has no elevated caps."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.config = _load_json(DEVCONTAINER / "devcontainer.json")

    def test_uses_docker_compose(self) -> None:
        assert "dockerComposeFile" in self.config

    def test_service_is_dev(self) -> None:
        assert self.config.get("service") == "dev"

    def test_no_run_args(self) -> None:
        assert "runArgs" not in self.config, "No runArgs needed — compose handles caps"

    def test_no_net_admin_anywhere(self) -> None:
        text = json.dumps(self.config)
        assert "NET_ADMIN" not in text
        assert "NET_RAW" not in text

    def test_no_post_start_firewall(self) -> None:
        post_start = self.config.get("postStartCommand", "")
        assert "init-firewall" not in post_start

    def test_workspace_folder(self) -> None:
        assert self.config.get("workspaceFolder") == "/workspace"

    def test_has_post_create_command(self) -> None:
        assert "postCreateCommand" in self.config


# ---------------------------------------------------------------------------
# Dev Dockerfile (no firewall remnants)
# ---------------------------------------------------------------------------

class TestDevDockerfile:
    """Validate the dev Dockerfile has no firewall remnants."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.text = (DEVCONTAINER / "Dockerfile").read_text(encoding="utf-8")

    def test_no_iptables_package(self) -> None:
        assert "iptables" not in self.text

    def test_no_ipset_package(self) -> None:
        assert "ipset" not in self.text

    def test_no_firewall_script(self) -> None:
        assert "init-firewall" not in self.text

    def test_still_has_core_packages(self) -> None:
        for pkg in ["git", "curl", "sudo", "zsh", "nodejs"]:
            assert pkg in self.text, f"Core package {pkg} must still be installed"


# ---------------------------------------------------------------------------
# Deleted files
# ---------------------------------------------------------------------------

class TestDeletedFiles:
    """Verify old firewall script is removed."""

    def test_init_firewall_deleted(self) -> None:
        assert not (DEVCONTAINER / "init-firewall.sh").exists(), (
            "init-firewall.sh should be deleted — replaced by network topology"
        )
