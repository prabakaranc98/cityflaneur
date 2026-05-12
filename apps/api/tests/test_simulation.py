from scripts.run_simulation import run


def test_simulation_personas_get_three_options():
    results = run()

    assert results
    assert all(result["count"] == 3 for result in results)
    assert all(result["top_score"] > 0.45 for result in results)

