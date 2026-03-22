"""
Phase 1.4: Plugin manifest schema validation tests (#7).
Validates that all plugin manifests conform to the expected schema.
"""
import json
import sys
import pytest

sys.path.insert(0, ".")
from wickerman_plugins import ALL_PLUGINS, PLUGIN_HOSTS


REQUIRED_KEYS = {"name", "description", "container_name", "ports", "nginx_host", "help"}
OPTIONAL_KEYS = {"icon", "env", "volumes", "image", "build", "build_context", "files", "gpu", "networks"}
ALL_VALID_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS


class TestPluginSchema:
    """Every plugin manifest must have required keys and valid types."""

    @pytest.fixture(params=list(ALL_PLUGINS.keys()))
    def manifest_entry(self, request):
        return request.param, ALL_PLUGINS[request.param]

    def test_has_required_keys(self, manifest_entry):
        fname, manifest = manifest_entry
        missing = REQUIRED_KEYS - set(manifest.keys())
        assert not missing, f"{fname} missing required keys: {missing}"

    def test_no_unknown_keys(self, manifest_entry):
        fname, manifest = manifest_entry
        unknown = set(manifest.keys()) - ALL_VALID_KEYS
        assert not unknown, f"{fname} has unknown keys: {unknown}"

    def test_name_is_string(self, manifest_entry):
        fname, manifest = manifest_entry
        assert isinstance(manifest["name"], str)
        assert len(manifest["name"]) > 0

    def test_container_name_starts_with_wm(self, manifest_entry):
        fname, manifest = manifest_entry
        assert manifest["container_name"].startswith("wm-")

    def test_ports_is_list_of_strings(self, manifest_entry):
        fname, manifest = manifest_entry
        assert isinstance(manifest["ports"], list)
        for p in manifest["ports"]:
            assert isinstance(p, str)
            assert ":" in p, f"Port mapping should contain ':' — got {p}"

    def test_nginx_host_is_string(self, manifest_entry):
        fname, manifest = manifest_entry
        assert isinstance(manifest["nginx_host"], str)
        assert ".wickerman.local" in manifest["nginx_host"]

    def test_has_image_or_build(self, manifest_entry):
        fname, manifest = manifest_entry
        has_image = "image" in manifest
        has_build = "build" in manifest
        assert has_image or has_build, f"{fname} must have either 'image' or 'build'"
        assert not (has_image and has_build), f"{fname} has both 'image' and 'build'"

    def test_build_plugins_have_files(self, manifest_entry):
        fname, manifest = manifest_entry
        if "build" in manifest:
            assert "files" in manifest, f"{fname} has 'build' but no 'files'"
            assert isinstance(manifest["files"], dict)
            assert len(manifest["files"]) > 0

    def test_image_plugins_have_no_files(self, manifest_entry):
        fname, manifest = manifest_entry
        if "image" in manifest:
            assert "files" not in manifest, f"{fname} has 'image' and should not have 'files'"

    def test_volumes_use_valid_tokens(self, manifest_entry):
        fname, manifest = manifest_entry
        valid_tokens = {"{self}", "{models}", "{datasets}", "{loras}", "{cache}", "{workspace}"}
        for vol in manifest.get("volumes", []):
            host_part = vol.split(":")[0]
            for token in valid_tokens:
                host_part = host_part.replace(token, "")
            # After removing valid tokens, remaining { } would indicate invalid tokens
            assert "{" not in host_part, f"{fname} volume has invalid token in: {vol}"

    def test_json_serializable(self, manifest_entry):
        fname, manifest = manifest_entry
        serialized = json.dumps(manifest, indent=2)
        roundtripped = json.loads(serialized)
        assert roundtripped["name"] == manifest["name"]
        assert roundtripped["container_name"] == manifest["container_name"]

    def test_help_is_nonempty_string(self, manifest_entry):
        fname, manifest = manifest_entry
        assert isinstance(manifest["help"], str)
        assert len(manifest["help"]) > 10


class TestPluginHosts:
    """PLUGIN_HOSTS must have correct format."""

    def test_has_five_entries(self):
        assert len(PLUGIN_HOSTS) == 5

    def test_all_tuples_with_ip_and_hostname(self):
        for entry in PLUGIN_HOSTS:
            assert isinstance(entry, tuple)
            assert len(entry) == 2
            ip, hostname = entry
            assert ip == "127.0.0.1"
            assert hostname.endswith(".wickerman.local")

    def test_hostnames_match_manifests(self):
        host_names = {h for _, h in PLUGIN_HOSTS}
        manifest_hosts = {m["nginx_host"] for m in ALL_PLUGINS.values()}
        assert host_names == manifest_hosts


class TestAllPlugins:
    """ALL_PLUGINS dict has correct structure."""

    def test_has_five_entries(self):
        assert len(ALL_PLUGINS) == 5

    def test_filenames_match_container_names(self):
        for fname, manifest in ALL_PLUGINS.items():
            expected = manifest["container_name"] + ".json"
            assert fname == expected, f"Filename {fname} doesn't match container {manifest['container_name']}"
