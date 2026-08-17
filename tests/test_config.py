from swarm_kit.config import ROOT, list_scenarios, load_personas, load_scenario


def test_list_scenarios_finds_both_defaults():
    names = {p.stem for p in list_scenarios()}
    assert "pizza_debate" in names
    assert "moon_base_debate" in names


def test_load_scenario_pizza():
    s = load_scenario(ROOT / "scenarios" / "pizza_debate.yaml")
    assert s.name == "pizza-debate"
    assert s.participants == ["optimist", "skeptic"]
    assert s.rounds == 4


def test_load_personas_default_file():
    personas = load_personas(ROOT / "personas" / "debate_default.yaml")
    assert "optimist" in personas
    assert "skeptic" in personas
    assert personas["optimist"].color == "yellow"
    assert personas["optimist"].system_prompt  # non-empty


def test_every_scenario_participant_exists_in_its_persona_file():
    for scenario_path in list_scenarios():
        scenario = load_scenario(scenario_path)
        personas = load_personas(ROOT / "personas" / scenario.persona_file)
        for key in scenario.participants:
            assert key in personas, f"{key} missing from {scenario.persona_file}"
