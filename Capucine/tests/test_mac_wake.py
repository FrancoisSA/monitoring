import pytest

from capucine.mac_wake import MacConfig, is_ssh_reachable, send_wol_packet, wait_for_mac


def _config(**overrides) -> MacConfig:
    defaults = dict(
        host="10.0.0.8",
        ssh_user="francoissalazar",
        ssh_key_path="/home/fsalazar/.ssh/id_ed25519",
        mac_address="84:2f:57:d3:48:6c",
        model="qwen3-coder-30b-a3b-instruct-mlx",
        wake_timeout_s=30,
        retry_interval_s=10,
    )
    defaults.update(overrides)
    return MacConfig(**defaults)


def test_send_wol_packet_builds_the_correct_magic_packet():
    sent = {}

    def fake_send_udp(data: bytes, addr) -> None:
        sent["data"] = data
        sent["addr"] = addr

    send_wol_packet("84:2f:57:d3:48:6c", send_udp=fake_send_udp)

    mac_bytes = bytes.fromhex("842f57d3486c")
    assert sent["data"] == b"\xff" * 6 + mac_bytes * 16
    assert sent["addr"] == ("255.255.255.255", 9)


def test_send_wol_packet_rejects_an_invalid_mac_address():
    with pytest.raises(ValueError, match="Adresse MAC invalide"):
        send_wol_packet("pas-une-mac", send_udp=lambda data, addr: None)


def test_is_ssh_reachable_true_on_exit_code_zero():
    assert is_ssh_reachable(_config(), run=lambda command: 0) is True


def test_is_ssh_reachable_false_on_nonzero_exit_code():
    assert is_ssh_reachable(_config(), run=lambda command: 1) is False


def test_wait_for_mac_returns_immediately_when_already_reachable():
    wol_calls = []
    sleep_calls = []

    result = wait_for_mac(
        _config(),
        is_reachable=lambda config: True,
        send_wol=lambda mac: wol_calls.append(mac),
        sleep=lambda seconds: sleep_calls.append(seconds),
    )

    assert result is True
    assert wol_calls == []
    assert sleep_calls == []


def test_wait_for_mac_sends_wol_once_and_retries_until_reachable():
    wol_calls = []
    attempts = iter([False, False, True])  # injoignable, injoignable, puis OK

    result = wait_for_mac(
        _config(wake_timeout_s=60, retry_interval_s=10),
        is_reachable=lambda config: next(attempts),
        send_wol=lambda mac: wol_calls.append(mac),
        sleep=lambda seconds: None,
        now=_fake_clock(step=10),
    )

    assert result is True
    assert wol_calls == ["84:2f:57:d3:48:6c"]


def test_wait_for_mac_gives_up_after_the_timeout_budget():
    wol_calls = []

    result = wait_for_mac(
        _config(wake_timeout_s=30, retry_interval_s=10),
        is_reachable=lambda config: False,
        send_wol=lambda mac: wol_calls.append(mac),
        sleep=lambda seconds: None,
        now=_fake_clock(step=10),
    )

    assert result is False
    assert wol_calls == ["84:2f:57:d3:48:6c"]  # un seul réveil, pas un par tentative


def _fake_clock(step: float):
    """Horloge factice : chaque appel avance le temps de `step` secondes,
    pour piloter deadline `now() + wake_timeout_s` sans vraie attente."""
    state = {"t": 0.0}

    def now() -> float:
        state["t"] += step
        return state["t"]

    return now
