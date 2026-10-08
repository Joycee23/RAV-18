import uuid


def test_reviewer_can_approve_once_and_review_persists_on_detail(client):
    api, sessions = client
    from test_incidents import make_incident

    incident_id = make_incident(sessions)
    run = api.post(f"/api/incidents/{incident_id}/analyze").json()
    run_id = run["id"]
    payload = {"decision": "approve", "actor_role": "reviewer", "actor_name": "Reviewer A", "note": "Evidence checked."}

    reviewed = api.post(f"/api/incidents/{incident_id}/actions/{run_id}/review", json=payload)
    assert reviewed.status_code == 200
    assert reviewed.json()["decision"] == "approve"
    persisted = api.get(f"/api/incidents/{incident_id}").json()["runs"][0]
    assert persisted["status"] == "approved"
    assert persisted["reviews"][0]["actor_name"] == "Reviewer A"

    duplicate = api.post(f"/api/incidents/{incident_id}/actions/{run_id}/review", json=payload)
    assert duplicate.status_code == 409


def test_review_rejects_non_reviewer_invalid_payload_and_wrong_run(client):
    api, sessions = client
    from test_incidents import make_incident

    incident_id = make_incident(sessions)
    run_id = api.post(f"/api/incidents/{incident_id}/analyze").json()["id"]
    path = f"/api/incidents/{incident_id}/actions/{run_id}/review"

    forbidden = api.post(path, json={"decision": "approve", "actor_role": "engineer", "actor_name": "Engineer"})
    assert forbidden.status_code == 403
    invalid_decision = api.post(path, json={"decision": "maybe", "actor_role": "reviewer", "actor_name": "Reviewer"})
    assert invalid_decision.status_code == 422
    blank_name = api.post(path, json={"decision": "reject", "actor_role": "reviewer", "actor_name": "   "})
    assert blank_name.status_code == 422
    wrong_run = api.post(f"/api/incidents/{incident_id}/actions/{uuid.uuid4()}/review", json={"decision": "reject", "actor_role": "reviewer", "actor_name": "Reviewer"})
    assert wrong_run.status_code == 404
