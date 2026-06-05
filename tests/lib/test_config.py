"""Tests for lib.config."""

from unittest.mock import patch
import lib.config as cfg_mod


class TestConfigLoad:
    def test_load_reads_config(self, tmp_config):
        config_path, config_data, tmp_path = tmp_config
        cfg_mod._config = None
        cfg_mod._project_root = tmp_path

        with patch.object(cfg_mod.Path, "exists", return_value=True):
            result = cfg_mod.load()
        assert result["llm"]["model"] == "test-model"
        cfg_mod._config = None

    def test_load_missing_file_raises(self, tmp_path):
        cfg_mod._config = None
        cfg_mod._project_root = tmp_path
        try:
            cfg_mod.load()
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass
        finally:
            cfg_mod._config = None

    def test_expands_environment_variables(self, tmp_path, monkeypatch):
        import yaml

        monkeypatch.setenv("DEEPSEEK_API_KEY", "env-test-key")
        config = {
            "storage": {"db_path": "./test.db", "output_dir": "./output"},
            "llm": {"api_key": "${DEEPSEEK_API_KEY}"},
        }
        with open(tmp_path / "config.yaml", "w") as f:
            yaml.dump(config, f)

        cfg_mod._config = None
        cfg_mod._project_root = tmp_path
        try:
            loaded = cfg_mod.load()
            assert loaded["llm"]["api_key"] == "env-test-key"
        finally:
            cfg_mod._config = None


class TestConfigGet:
    def test_dot_notation(self, loaded_config):
        loaded, _ = loaded_config
        # Use fresh get after load
        assert cfg_mod.get("llm.model") == "test-model"
        assert cfg_mod.get("llm.api_key") == "test-key"

    def test_nested_access(self, loaded_config):
        assert cfg_mod.get("storage.db_path") is not None

    def test_missing_key_returns_default(self, loaded_config):
        assert cfg_mod.get("nonexistent.key") is None
        assert cfg_mod.get("nonexistent.key", "fallback") == "fallback"

    def test_reload(self, loaded_config):
        first = cfg_mod.load()
        second = cfg_mod.reload()
        assert first == second


class TestConfigSingleton:
    def test_load_is_cached(self, tmp_config):
        config_path, _, tmp_path = tmp_config
        cfg_mod._config = None
        cfg_mod._project_root = tmp_path

        with patch.object(cfg_mod.Path, "exists", return_value=True):
            a = cfg_mod.load()
            b = cfg_mod.load()
        assert a is b
        cfg_mod._config = None
