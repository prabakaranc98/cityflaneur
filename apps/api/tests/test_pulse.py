from app.services.pulse import build_neighborhood_pulses


def test_neighborhood_pulse_uses_curated_fallback_without_live_key():
    pulses = build_neighborhood_pulses(["Chelsea", "SoHo"])

    assert len(pulses) == 2
    assert pulses[0].neighborhood == "Chelsea"
    assert pulses[0].trivia
    assert pulses[0].source_note == "curated trivia"

