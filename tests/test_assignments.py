def test_assignment_change_detection_includes_status_department_and_location(app_module):
    old_assignment = {
        "person_id": 12,
        "assignment_department": "FINANCE HLF",
        "location_id": 3,
        "assignment_date": "2026-07-01",
        "status": "functional",
        "assignment_scope": "personal",
    }
    new_assignment = {
        "person_id": 12,
        "assignment_department": "PROGRAM",
        "location_id": 4,
        "assignment_date": "2026-07-01",
        "status": "Not functional",
        "assignment_scope": "personal",
    }

    changes = app_module.build_assignment_field_changes(old_assignment, new_assignment)
    labels = {change["label"] for change in changes}

    assert labels == {"Department", "Office / location", "Status"}


def test_assignment_change_detection_handles_none_values(app_module):
    changes = app_module.build_assignment_field_changes(
        {"location_id": None, "status": None},
        {"location_id": 4, "status": "functional"},
    )
    assert {change["field_name"] for change in changes} == {"location_id", "status"}


def test_assignment_scope_normalization(app_module):
    assert app_module.normalize_assignment_scope("department_shared") == "department_shared"
    assert app_module.normalize_assignment_scope("warehouse") == "warehouse"
    assert app_module.normalize_assignment_scope("unexpected") == "personal"

