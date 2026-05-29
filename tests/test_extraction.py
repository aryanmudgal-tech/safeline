from agents.orchestrator import check_missing_fields, create_empty_extraction, update_extracted_data


def test_missing_fields_prioritize_legal_fields_for_arrest_report() -> None:
    extraction = create_empty_extraction()
    extraction = update_extracted_data(extraction, "officer.name", "Officer Elena Martinez", "badge lookup")
    extraction = update_extracted_data(extraction, "incident.date", "2026-05-30", "narrative")
    extraction = update_extracted_data(extraction, "incident.location", "142 Oak Street", "narrative")

    missing = check_missing_fields("arrest_report", extraction)

    assert missing[0]["priority"] == "legal"
    assert {field["name"] for field in missing} >= {"charges", "miranda_given", "suspect_name"}

