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


def test_ajout_manuel_a_la_chronologie(client, auth_headers):
    headers = auth_headers("opj")
    incident_id = _create_incident(client, headers)

    payload = {
        "date_heure": "2026-02-01T09:30:00",
        "titre": "Audition du témoin",
        "description": "Le témoin déclare avoir vu deux individus quitter les lieux.",
    }
    response = client.post(f"/incidents/{incident_id}/chronologie", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["origine"] == "manuel"
    assert body["titre"] == "Audition du témoin"

    chrono = client.get(f"/incidents/{incident_id}/chronologie", headers=headers).json()
    assert len(chrono) == 1
    assert chrono[0]["titre"] == "Audition du témoin"


def test_chronologie_fusionne_les_evenements_de_custody(client, auth_headers):
    """La chronologie doit refléter les maillons de la chaîne de custody
    sans qu'il soit nécessaire de les ressaisir manuellement (cahier des
    charges 3.2 : la fiche d'affaire centralise témoins/preuves/chronologie)."""
    headers = auth_headers("opj")
    incident_id = _create_incident(client, headers)
    preuve_id = _create_preuve(client, headers, incident_id)

    client.post(f"/preuves/{preuve_id}/custody", json={"action": "collecte"}, headers=headers)
    client.post(
        f"/incidents/{incident_id}/chronologie",
        json={"date_heure": "2026-02-01T08:00:00", "titre": "Constatation initiale"},
        headers=headers,
    )

    chrono = client.get(f"/incidents/{incident_id}/chronologie", headers=headers).json()
    origines = {e["origine"] for e in chrono}
    assert origines == {"manuel", "auto"}
    # Trié chronologiquement.
    dates = [e["date_heure"] for e in chrono]
    assert dates == sorted(dates)


def test_lecture_seule_ne_permet_pas_d_ajouter_un_evenement(client, auth_headers):
    headers_opj = auth_headers("opj")
    incident_id = _create_incident(client, headers_opj)

    headers_analyste = auth_headers("analyste")
    response = client.post(
        f"/incidents/{incident_id}/chronologie",
        json={"date_heure": "2026-02-01T09:00:00", "titre": "Tentative non autorisée"},
        headers=headers_analyste,
    )
    assert response.status_code == 403
