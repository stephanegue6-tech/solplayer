import io

from app import storage


def _create_incident_and_preuve(client, headers):
    incident = client.post(
        "/incidents",
        json={
            "type_infraction": "cambriolage",
            "date_heure": "2026-02-01T10:00:00",
            "statut": "en_cours",
            "gravite": "moyenne",
        },
        headers=headers,
    ).json()
    preuve = client.post(
        "/preuves",
        json={"incident_id": incident["id"], "type": "document", "description": "Facture"},
        headers=headers,
    ).json()
    return preuve["id"]


def test_upload_puis_telechargement_piece_jointe(client, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)
    headers = auth_headers("enqueteur")
    preuve_id = _create_incident_and_preuve(client, headers)

    fichier = io.BytesIO(b"%PDF-1.4 contenu factice de test")
    response = client.post(
        f"/preuves/{preuve_id}/pieces-jointes",
        files={"fichier": ("piece.pdf", fichier, "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 201
    piece = response.json()
    assert piece["nom_fichier"] == "piece.pdf"
    assert piece["hash_sha256"]

    listing = client.get(f"/preuves/{preuve_id}/pieces-jointes", headers=headers).json()
    assert len(listing) == 1

    download = client.get(
        f"/preuves/{preuve_id}/pieces-jointes/{piece['id']}/telechargement", headers=headers
    )
    assert download.status_code == 200
    assert download.content == b"%PDF-1.4 contenu factice de test"

    # L'ajout d'une pièce jointe est aussi tracé dans la chaîne de custody.
    chain = client.get(f"/preuves/{preuve_id}/custody", headers=headers).json()
    assert any("ajout_piece_jointe" in e["action"] for e in chain["evenements"])


def test_upload_type_mime_non_autorise_est_rejete(client, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)
    headers = auth_headers("enqueteur")
    preuve_id = _create_incident_and_preuve(client, headers)

    fichier = io.BytesIO(b"#!/bin/sh\necho not-a-real-script")
    response = client.post(
        f"/preuves/{preuve_id}/pieces-jointes",
        files={"fichier": ("script.sh", fichier, "application/x-sh")},
        headers=headers,
    )
    assert response.status_code == 415


def test_suppression_piece_jointe_reservee_opj_admin(client, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)
    headers_enq = auth_headers("enqueteur")
    preuve_id = _create_incident_and_preuve(client, headers_enq)

    fichier = io.BytesIO(b"contenu")
    piece = client.post(
        f"/preuves/{preuve_id}/pieces-jointes",
        files={"fichier": ("note.txt", fichier, "text/plain")},
        headers=headers_enq,
    ).json()

    refuse = client.delete(
        f"/preuves/{preuve_id}/pieces-jointes/{piece['id']}", headers=headers_enq
    )
    assert refuse.status_code == 403

    headers_opj = auth_headers("opj")
    accepte = client.delete(
        f"/preuves/{preuve_id}/pieces-jointes/{piece['id']}", headers=headers_opj
    )
    assert accepte.status_code == 204


def test_alteration_du_fichier_sur_disque_bloque_le_telechargement(
    client, auth_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)
    headers = auth_headers("enqueteur")
    preuve_id = _create_incident_and_preuve(client, headers)

    fichier = io.BytesIO(b"contenu original")
    piece = client.post(
        f"/preuves/{preuve_id}/pieces-jointes",
        files={"fichier": ("note.txt", fichier, "text/plain")},
        headers=headers,
    ).json()

    # PieceJointeOut n'expose pas chemin_stockage (détail interne) : on
    # retrouve le fichier écrit sur disque directement pour le corrompre.
    fichiers = list(tmp_path.glob("*.bin"))
    assert len(fichiers) == 1
    fichiers[0].write_bytes(b"contenu altere")

    response = client.get(
        f"/preuves/{preuve_id}/pieces-jointes/{piece['id']}/telechargement", headers=headers
    )
    assert response.status_code == 409
