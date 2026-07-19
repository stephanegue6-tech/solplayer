from app import models


def _create_incident(client, headers):
    payload = {
        "type_infraction": "cambriolage",
        "date_heure": "2026-02-01T10:00:00",
        "statut": "en_cours",
        "gravite": "moyenne",
    }
    response = client.post("/incidents", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


def _create_preuve(client, headers, incident_id):
    payload = {"incident_id": incident_id, "type": "objet", "description": "Pied de biche"}
    response = client.post("/preuves", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


def test_chaine_de_custody_hash_chain(client, auth_headers):
    headers = auth_headers("opj")
    incident_id = _create_incident(client, headers)
    preuve_id = _create_preuve(client, headers, incident_id)

    for action in ("collecte", "transfert", "analyse"):
        response = client.post(f"/preuves/{preuve_id}/custody", json={"action": action}, headers=headers)
        assert response.status_code == 201

    chain = client.get(f"/preuves/{preuve_id}/custody", headers=headers).json()
    assert len(chain["evenements"]) == 3
    assert chain["chaine_intacte"] is True
    assert chain["alerte_rupture"] is False


def test_falsification_de_la_chaine_est_detectee(client, auth_headers, db_session):
    headers = auth_headers("opj")
    incident_id = _create_incident(client, headers)
    preuve_id = _create_preuve(client, headers, incident_id)

    client.post(f"/preuves/{preuve_id}/custody", json={"action": "collecte"}, headers=headers)
    client.post(f"/preuves/{preuve_id}/custody", json={"action": "transfert"}, headers=headers)

    # Falsifie directement en base le premier maillon (simule une
    # altération a posteriori du journal).
    evt = (
        db_session.query(models.ChaineCustody)
        .filter(models.ChaineCustody.preuve_id == preuve_id)
        .order_by(models.ChaineCustody.date_heure.asc())
        .first()
    )
    evt.action = "collecte_modifiee"
    db_session.commit()

    chain = client.get(f"/preuves/{preuve_id}/custody", headers=headers).json()
    assert chain["chaine_intacte"] is False
    assert chain["alerte_rupture"] is True


def test_agent_de_custody_toujours_derive_du_token(client, auth_headers):
    """Le payload de /custody n'accepte pas de personne_id : l'agent est
    TOUJOURS l'utilisateur authentifié (voir app/routers/preuves.py)."""
    headers = auth_headers("opj")
    incident_id = _create_incident(client, headers)
    preuve_id = _create_preuve(client, headers, incident_id)

    response = client.post(
        f"/preuves/{preuve_id}/custody",
        json={"action": "collecte", "personne_id": "un-suspect-quelconque"},
        headers=headers,
    )
    assert response.status_code == 201
    evenement = response.json()
    assert "personne_id" not in evenement


def test_export_csv_et_pdf_historique_custody(client, auth_headers):
    headers = auth_headers("opj")
    incident_id = _create_incident(client, headers)
    preuve_id = _create_preuve(client, headers, incident_id)
    client.post(f"/preuves/{preuve_id}/custody", json={"action": "collecte"}, headers=headers)

    csv_response = client.get(f"/preuves/{preuve_id}/custody/export.csv", headers=headers)
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert b"collecte" in csv_response.content

    pdf_response = client.get(f"/preuves/{preuve_id}/custody/export.pdf", headers=headers)
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.content[:4] == b"%PDF"
