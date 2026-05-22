import logging
from pathlib import Path

import pytest

from src.config import (
    Config,
    TokenRedactingFilter,
    load_config,
    parse_env_file,
)

VALID_CONFIG_YAML = """
todoist:
  project_id: "1234567890"
  labels:
    daily: "daily-ritual"
ritual_times:
  morning_reading: "06:00"
  anki: "08:30"
sunday_off: true
dashboard:
  github_username: "foo"
  repo_name: "long-way-engine"
"""


def test_parse_env_basic(tmp_path: Path):
    p = tmp_path / ".env"
    p.write_text("TODOIST_TOKEN=abc123\n")
    assert parse_env_file(p) == {"TODOIST_TOKEN": "abc123"}


def test_parse_env_ignores_comments_and_blanks(tmp_path: Path):
    p = tmp_path / ".env"
    p.write_text("# leading comment\n\nTODOIST_TOKEN=abc\n  # indented comment\nFOO=bar\n")
    assert parse_env_file(p) == {"TODOIST_TOKEN": "abc", "FOO": "bar"}


def test_parse_env_keeps_equals_in_value(tmp_path: Path):
    p = tmp_path / ".env"
    p.write_text("KEY=a=b=c\n")
    assert parse_env_file(p) == {"KEY": "a=b=c"}


def test_parse_env_missing_file_returns_empty(tmp_path: Path):
    assert parse_env_file(tmp_path / "nope") == {}


def test_load_config_reads_yaml_and_token(tmp_path: Path):
    yaml_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    yaml_path.write_text(VALID_CONFIG_YAML)
    env_path.write_text("TODOIST_TOKEN=secret-token-xyz\n")

    cfg = load_config(yaml_path, env_path)
    assert cfg.todoist.project_id == "1234567890"
    assert cfg.todoist.labels["daily"] == "daily-ritual"
    assert cfg.ritual_times["morning_reading"] == "06:00"
    assert cfg.sunday_off is True
    assert cfg.dashboard.github_username == "foo"
    assert cfg.todoist_token == "secret-token-xyz"


def test_load_config_falls_back_to_environment(tmp_path: Path, monkeypatch):
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(VALID_CONFIG_YAML)
    monkeypatch.setenv("TODOIST_TOKEN", "from-env")

    cfg = load_config(yaml_path, tmp_path / "missing.env")
    assert cfg.todoist_token == "from-env"


def test_load_config_raises_when_token_missing(tmp_path: Path, monkeypatch):
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(VALID_CONFIG_YAML)
    monkeypatch.delenv("TODOIST_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="TODOIST_TOKEN"):
        load_config(yaml_path, tmp_path / "missing.env")


def test_repr_redacts_token():
    cfg = Config(
        todoist=type("T", (), {"project_id": "1", "labels": {}})(),
        ritual_times={},
        sunday_off=True,
        dashboard=type("D", (), {"github_username": "u", "repo_name": "r"})(),
        todoist_token="super-secret",
    )
    text = repr(cfg)
    assert "super-secret" not in text
    assert "REDACTED" in text


def test_logging_filter_redacts_token(caplog):
    token = "super-secret-12345"
    flt = TokenRedactingFilter(token)
    logger = logging.getLogger("test_logging_filter_redacts_token")
    logger.addFilter(flt)
    with caplog.at_level(logging.INFO, logger=logger.name):
        logger.info("calling api with %s now", token)
        logger.info(f"token literal {token} in fstring")
    for record in caplog.records:
        assert token not in record.getMessage()


def test_config_curriculum_dir_default(tmp_path: Path) -> None:
    """Config defaults curriculum_dir to 'curriculum' when omitted."""
    cfg_yaml = tmp_path / "config.yaml"
    cfg_yaml.write_text(
        "todoist:\n"
        "  project_id: x\n"
        "ritual_times: {}\n"
        "dashboard:\n"
        "  github_username: u\n"
        "  repo_name: r\n",
        encoding="utf-8",
    )
    env = tmp_path / ".env"
    env.write_text("TODOIST_TOKEN=abc\n", encoding="utf-8")
    cfg = load_config(cfg_yaml, env)
    assert cfg.curriculum_dir == Path("curriculum")


def test_config_curriculum_dir_explicit(tmp_path: Path) -> None:
    cfg_yaml = tmp_path / "config.yaml"
    cfg_yaml.write_text(
        "todoist:\n"
        "  project_id: x\n"
        "ritual_times: {}\n"
        "dashboard:\n"
        "  github_username: u\n"
        "  repo_name: r\n"
        "curriculum_dir: examples/ml-engineer-12mo\n",
        encoding="utf-8",
    )
    env = tmp_path / ".env"
    env.write_text("TODOIST_TOKEN=abc\n", encoding="utf-8")
    cfg = load_config(cfg_yaml, env)
    assert cfg.curriculum_dir == Path("examples/ml-engineer-12mo")
