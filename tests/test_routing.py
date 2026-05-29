from agents.report_router import suggest_report_types


def test_routes_arrest_and_force_reports() -> None:
    extraction = {
        "subjects": [{"role": "suspect", "arrested": True}],
        "force_used": True,
        "charges": ["domestic_battery"],
    }

    assert suggest_report_types(extraction) == [
        "incident_report",
        "arrest_report",
        "use_of_force",
    ]


def test_incident_report_is_always_included() -> None:
    assert suggest_report_types({}) == ["incident_report"]

