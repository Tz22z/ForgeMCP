from forgemcp.evaluation.compare import compare


def test_compare_reports_calculates_directional_deltas() -> None:
    baseline = {
        "attempted": 120,
        "solve_rate": 0.45,
        "average_tool_calls": 20.0,
        "average_repeated_read_ratio": 0.38,
        "cost_per_solved_usd": 1.0,
    }
    candidate = {
        "attempted": 120,
        "solve_rate": 0.7083,
        "average_tool_calls": 14.0,
        "average_repeated_read_ratio": 0.09,
        "cost_per_solved_usd": 0.66,
    }
    delta = compare(baseline, candidate)
    assert delta["solve_rate_change"] == 0.2583
    assert delta["average_tool_calls_change"] == -6.0
    assert delta["repeated_read_ratio_change"] == -0.29
    assert delta["cost_per_solved_relative_change"] == -0.34
