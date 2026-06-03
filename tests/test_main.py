"""Tests for main.py argument parsing and pipeline orchestration."""

import sys
from unittest.mock import MagicMock, patch

import lib.config as cfg_mod


def _setup_config(tmp_path):
    import yaml
    config = {
        "storage": {"db_path": str(tmp_path / "test.db"), "output_dir": str(tmp_path / "output")},
        "processor": {"categories": ["AI"], "min_score": 3, "max_items_per_category": 20, "batch_size": 5},
        "collectors": {},
        "distributors": {},
        "web": {"host": "127.0.0.1", "port": 3456},
    }
    with open(tmp_path / "config.yaml", "w") as f:
        yaml.dump(config, f)
    cfg_mod._config = None
    cfg_mod._project_root = tmp_path


class TestArgParsing:
    def test_collect_flag(self):
        import main
        with patch("sys.argv", ["main.py", "--collect"]):
            with patch("main.load_config"):
                with patch("main.run_collectors") as mock:
                    main.main()
                    mock.assert_called_once()

    def test_run_flag(self):
        import main
        with patch("sys.argv", ["main.py", "--run"]):
            with patch("main.load_config"):
                with patch("main.run_full_pipeline") as mock:
                    main.main()
                    mock.assert_called_once()

    def test_no_args_exits(self):
        import main
        with patch("sys.argv", ["main.py"]):
            with patch("main.load_config"):
                try:
                    main.main()
                    assert False, "Should have exited"
                except SystemExit as e:
                    assert e.code == 1

    def test_date_flag(self):
        import main
        with patch("sys.argv", ["main.py", "--report", "--date", "2026-01-01"]):
            with patch("main.load_config"):
                with patch("main.run_report") as mock:
                    main.main()
                    mock.assert_called_once_with("2026-01-01")


class TestFullPipeline:
    def test_calls_all_steps(self, tmp_path):
        _setup_config(tmp_path)
        import main

        with patch("main.run_collectors") as mock_c, \
             patch("main.run_analysis") as mock_a, \
             patch("main.run_report") as mock_r, \
             patch("main.run_push") as mock_p:
            main.run_full_pipeline("2026-01-01")
            mock_c.assert_called_once()
            mock_a.assert_called_once()
            mock_r.assert_called_once_with("2026-01-01")
            mock_p.assert_called_once_with("2026-01-01")
        cfg_mod._config = None
