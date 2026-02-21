"""Tests for the rules engine."""

from unifi_doctor.analysis.rules import (
    channels_overlap_5g,
    get_recommended_5g_channels,
    get_recommended_24g_channels,
    is_valid_24g_channel,
)


def test_valid_24g_channels():
    assert is_valid_24g_channel(1) is True
    assert is_valid_24g_channel(6) is True
    assert is_valid_24g_channel(11) is True
    assert is_valid_24g_channel(3) is False
    assert is_valid_24g_channel(9) is False


def test_recommended_24g_channels():
    assert get_recommended_24g_channels(1) == [1]
    assert get_recommended_24g_channels(3) == [1, 6, 11]
    assert get_recommended_24g_channels(4) == [1, 6, 11, 1]


def test_recommended_5g_channels_no_radar():
    channels = get_recommended_5g_channels(4, has_radar_events=False)
    assert len(channels) == 4
    # Should all be unique
    assert len(set(channels)) == 4


def test_recommended_5g_channels_with_radar():
    channels = get_recommended_5g_channels(4, has_radar_events=True)
    assert len(channels) == 4
    # With radar, should avoid DFS channels
    from unifi_doctor.analysis.rules import DFS_5G_CHANNELS

    for ch in channels:
        assert ch not in DFS_5G_CHANNELS


def test_channel_overlap_same():
    assert channels_overlap_5g(36, 36) is True


def test_channel_overlap_adjacent_40mhz():
    # 36 and 40 at 40 MHz width should overlap
    assert channels_overlap_5g(36, 40, 40, 40) is True


def test_channel_no_overlap_far():
    # 36 and 149 should never overlap
    assert channels_overlap_5g(36, 149, 80, 80) is False
