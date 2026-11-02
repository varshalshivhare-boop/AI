import asyncio

import pytest

from qm_md.errors import ConfigurationError, ProviderNotImplementedError
from qm_md.models import ProviderState
from qm_md.providers.upstox import UpstoxConfig, UpstoxProvider


def test_missing_credentials_refuse_to_start_and_name_the_variables() -> None:
    with pytest.raises(ConfigurationError, match="UPSTOX_API_KEY, UPSTOX_ACCESS_TOKEN"):
        UpstoxConfig.from_env({})


def test_blank_credentials_count_as_missing() -> None:
    with pytest.raises(ConfigurationError, match="UPSTOX_ACCESS_TOKEN"):
        UpstoxConfig.from_env({"UPSTOX_API_KEY": "k", "UPSTOX_ACCESS_TOKEN": "   "})


def test_complete_credentials_load() -> None:
    cfg = UpstoxConfig.from_env({"UPSTOX_API_KEY": " k ", "UPSTOX_ACCESS_TOKEN": "t"})
    assert cfg.api_key == "k"
    assert cfg.access_token == "t"


def test_secrets_never_appear_in_repr() -> None:
    cfg = UpstoxConfig.from_env({"UPSTOX_API_KEY": "SECRET_KEY", "UPSTOX_ACCESS_TOKEN": "SECRET_T"})
    text = repr(cfg)
    assert "SECRET_KEY" not in text and "SECRET_T" not in text


def test_scaffold_never_produces_data_and_says_why() -> None:
    p = UpstoxProvider(UpstoxConfig(api_key="k", access_token="t"))
    assert p.health() is ProviderState.DISCONNECTED
    with pytest.raises(ProviderNotImplementedError, match="not implemented"):
        asyncio.run(p.connect())
    assert p.health() is ProviderState.ERROR
