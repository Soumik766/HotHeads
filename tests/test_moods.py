from swarm_kit.moods import DEFAULT_EMOJI, emoji_for


def test_known_mood_maps_to_specific_emoji():
    assert emoji_for("smug") == "😏"
    assert emoji_for("SMUG") == "😏"  # case-insensitive
    assert emoji_for("  annoyed  ") == "😠"  # whitespace-tolerant


def test_unknown_mood_falls_back_to_default():
    assert emoji_for("existentially bewildered") == DEFAULT_EMOJI


def test_none_or_empty_falls_back_to_default():
    assert emoji_for(None) == DEFAULT_EMOJI
    assert emoji_for("") == DEFAULT_EMOJI


def test_every_mock_scripted_mood_has_a_mapped_emoji():
    """If mock.py scripts a mood word, it should render as something
    other than the generic fallback — otherwise the feature is silently
    doing nothing for that line."""
    from swarm_kit import mock

    for scenario in mock.SCRIPTS.values():
        for lines in scenario.values():
            for _line, mood in lines:
                assert emoji_for(mood) != DEFAULT_EMOJI, f"'{mood}' has no emoji mapping"
