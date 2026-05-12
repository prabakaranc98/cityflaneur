from app.services.pulse import build_neighborhood_pulses


def test_neighborhood_pulse_returns_expected_shape():
    pulses = build_neighborhood_pulses(["Chelsea", "SoHo"])

    assert len(pulses) == 2
    assert pulses[0].neighborhood == "Chelsea"
    assert pulses[0].trivia
    assert pulses[0].source_note  # either curated trivia or live+curated
    assert pulses[1].neighborhood == "SoHo"
    assert pulses[1].trivia

