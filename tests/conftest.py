"""Shared setup of the live tests: skip them unless LM Studio answers and a model is set.

The settings are the environment over the values of .env, read without changing os.environ,
so the other tests keep a clean environment (D-35, D-45). The fixtures hand the live tests
a real client and the settings main.py would use.
"""

import os
from functools import cache

import openai
import pytest
from dotenv import dotenv_values

from main import read_config

# Short, so a missing LM Studio costs the live tests seconds, not the client's default minutes.
REACHABILITY_TIMEOUT = 3


def live_settings() -> dict:
    """Return the settings for the live tests: the environment over the values of .env."""
    file_values = {name: value for name, value in dotenv_values().items() if value is not None}
    return {**file_values, **os.environ}


# Checked once per session; otherwise every live test would wait for the timeout again.
@cache
def live_skip_reason() -> str | None:
    """Return why the live tests cannot run, or None if a model is set and LM Studio answers."""
    try:
        config = read_config(live_settings())
    except ValueError as err:
        return str(err)
    client = openai.OpenAI(
        base_url=config["base_url"],
        api_key=config["api_key"],
        timeout=REACHABILITY_TIMEOUT,
        max_retries=0,
    )
    try:
        client.models.list()
    except openai.APIConnectionError:
        return f"LM Studio not reachable at {config['base_url']}"
    except openai.APIError as err:
        # The server may echo part of a wrong key in its message, so only the class is named.
        return f"LM Studio at {config['base_url']} rejected the request: {type(err).__name__}"
    return None


def pytest_runtest_setup(item):
    """Skip a test marked live when it cannot reach a model; other tests never check (D-35)."""
    if item.get_closest_marker("live") is None:
        return
    reason = live_skip_reason()
    if reason is not None:
        pytest.skip(reason)


@pytest.fixture(scope="session")
def live_config() -> dict:
    """Return the settings main.py would use: model, round limit, reasoning effort (D-15, D-19)."""
    config = read_config(live_settings())
    # pytest prints the fixture values of a failing test; the key must not end up in that output.
    del config["api_key"]
    return config


@pytest.fixture(scope="session")
def live_client():
    """Return a real openai client for the configured endpoint."""
    config = read_config(live_settings())
    return openai.OpenAI(base_url=config["base_url"], api_key=config["api_key"])
