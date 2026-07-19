def test_route_metier_refuse_sans_token(client):
    response = client.get("/incidents")
    assert response.status_code == 401


def test_lecture_seule_analyste_ne_peut_pas_creer_incident(client, auth_headers):
    headers = auth_headers("analyste")
    payload = {
        "type_infraction": "vol",
        "date_heure": "2026-01-01T10:00:00",
        "statut": "ouvert",
        "gravite": "faible",
    }
    response = client.post("/incidents", json=payload, headers=headers)
    assert response.status_code == 403


def test_enqueteur_peut_creer_incident(client, auth_headers):
    headers = auth_headers("enqueteur")
    payload = {
        "type_infraction": "vol",
        "date_heure": "2026-01-01T10:00:00",
        "statut": "ouvert",
        "gravite": "faible",
    }
    response = client.post("/incidents", json=payload, headers=headers)
    assert response.status_code == 201
    assert response.json()["type_infraction"] == "vol"


def test_seul_administrateur_accede_au_journal_audit(client, auth_headers):
    response = client.get("/audit", headers=auth_headers("enqueteur"))
    assert response.status_code == 403

    response = client.get("/audit", headers=auth_headers("administrateur"))
    assert response.status_code == 200
