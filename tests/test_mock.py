import asyncio

from swarm_kit import mock


def test_get_turn_cycles_through_script():
    line0, mood0 = mock.get_turn("pizza-debate", "optimist", 0)
    assert "Pineapple" in line0
    assert mood0 == "smug"
    # rounds beyond script length should cycle, not crash
    assert mock.get_turn("pizza-debate", "optimist", 4) == (line0, mood0)


def test_every_scripted_line_has_a_mood():
    for scenario in mock.SCRIPTS.values():
        for lines in scenario.values():
            for line, mood in lines:
                assert isinstance(line, str) and line
                assert isinstance(mood, str) and mood


def test_stream_line_reassembles_to_original_text():
    async def run() -> str:
        text = ""
        async for chunk in mock.stream_line("hello world", delay=0):
            text += chunk
        return text

    assert asyncio.run(run()).strip() == "hello world"


def test_unknown_persona_returns_placeholder_not_crash():
    text, mood = mock.get_turn("pizza-debate", "nonexistent", 0)
    assert "no mock script" in text
    assert mood == "confused"


def test_unknown_scenario_returns_placeholder_not_crash():
    text, mood = mock.get_turn("nonexistent-scenario", "optimist", 0)
    assert "no mock script" in text
