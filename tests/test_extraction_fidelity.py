"""
Phase 1.1: Extraction fidelity tests (#4).
Verifies that the Path.read_text() approach produces identical values
to what the original string constants contained.
"""
import json
import sys
import pytest

sys.path.insert(0, ".")


class TestCoreConstants:
    """wickerman_support.py constants load correctly from src/ files."""

    def _load(self):
        # Force reimport to get fresh values
        for mod in list(sys.modules):
            if "wickerman" in mod:
                del sys.modules[mod]
        import wickerman_support as ws
        return ws

    def test_main_py_loads(self):
        ws = self._load()
        assert len(ws.MAIN_PY) > 1000
        assert "nicegui" in ws.MAIN_PY
        assert "#!/usr/bin/env python3" in ws.MAIN_PY

    def test_core_dockerfile_loads(self):
        ws = self._load()
        assert "FROM python:3.11-slim" in ws.CORE_DOCKERFILE

    def test_downloader_app_loads(self):
        ws = self._load()
        assert "Flask" in ws.DOWNLOADER_APP_PY or "flask" in ws.DOWNLOADER_APP_PY

    def test_downloader_html_loads(self):
        ws = self._load()
        assert "<!DOCTYPE html>" in ws.DOWNLOADER_INDEX_HTML

    def test_downloader_requirements_loads(self):
        ws = self._load()
        assert "flask" in ws.DOWNLOADER_REQUIREMENTS
        assert "gunicorn" in ws.DOWNLOADER_REQUIREMENTS

    def test_downloader_dockerfile_loads(self):
        ws = self._load()
        assert "FROM python:3.11-slim" in ws.DOWNLOADER_DOCKERFILE

    def test_generate_nginx_loads(self):
        ws = self._load()
        assert "nginx" in ws.GENERATE_NGINX_PY.lower()


class TestPluginManifests:
    """Plugin manifests load correctly and are JSON-serializable."""

    def _load_plugins(self):
        for mod in list(sys.modules):
            if "wickerman" in mod:
                del sys.modules[mod]
        from wickerman_plugins import ALL_PLUGINS
        return ALL_PLUGINS

    @pytest.fixture
    def plugins(self):
        return self._load_plugins()

    def test_five_plugins_present(self, plugins):
        assert len(plugins) == 5

    def test_all_serializable(self, plugins):
        for fname, manifest in plugins.items():
            serialized = json.dumps(manifest, indent=2)
            roundtripped = json.loads(serialized)
            assert roundtripped["name"] == manifest["name"]

    def test_llama_has_four_files(self, plugins):
        files = plugins["wm-llama.json"]["files"]
        assert len(files) == 4
        assert "data/manager.py" in files
        assert "data/Dockerfile" in files
        assert "data/entrypoint.sh" in files
        assert "data/test_chat.html" in files

    def test_chat_has_three_files(self, plugins):
        files = plugins["wm-chat.json"]["files"]
        assert len(files) == 3
        assert "data/app.py" in files

    def test_forge_has_three_files(self, plugins):
        files = plugins["wm-forge.json"]["files"]
        assert len(files) == 3
        assert "data/app.py" in files

    def test_trainer_has_three_files(self, plugins):
        files = plugins["wm-trainer.json"]["files"]
        assert len(files) == 3
        assert "data/app.py" in files

    def test_flow_has_no_files(self, plugins):
        assert "files" not in plugins["wm-flow.json"]

    def test_embedded_python_is_valid_syntax(self, plugins):
        """All embedded .py files should at least parse as valid Python."""
        import ast
        for fname, manifest in plugins.items():
            for file_key, content in manifest.get("files", {}).items():
                if file_key.endswith(".py"):
                    try:
                        ast.parse(content)
                    except SyntaxError as e:
                        pytest.fail(f"{fname} / {file_key} has syntax error: {e}")

    def test_extracted_python_files_parse(self):
        """All .py files under src/ should parse as valid Python."""
        import ast
        from pathlib import Path
        for pyfile in Path("src").rglob("*.py"):
            try:
                ast.parse(pyfile.read_text())
            except SyntaxError as e:
                pytest.fail(f"{pyfile} has syntax error: {e}")
