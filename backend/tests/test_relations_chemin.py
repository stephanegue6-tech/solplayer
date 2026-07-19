def _create_personne(client, headers, nom, prenom):
    response = client.post("/personnes", json={"nom": nom, "prenom": prenom, "role": "suspect"}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


def _create_relation(client, headers, a_id, b_id, type_relation="connaissance", poids=1):
    response = client.post(
        "/relations",
        json={"personne_a_id": a_id, "personne_b_id": b_id, "type_relation": type_relation, "poids": poids},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_chemin_direct_entre_deux_personnes(client, auth_headers):
    write_headers = auth_headers("enqueteur")
    a = _create_personne(client, write_headers, "Martin", "Alice")
    b = _create_personne(client, write_headers, "Durand", "Bob")
    _create_relation(client, write_headers, a, b, "complice", 5)

    response = client.get("/relations/chemin", params={"depart_id": a, "arrivee_id": b}, headers=write_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["trouve"] is True
    assert data["longueur"] == 1
    assert [n["id"] for n in data["nodes"]] == [a, b]


def test_chemin_indirect_via_intermediaire(client, auth_headers):
    headers = auth_headers("enqueteur")
    a = _create_personne(client, headers, "Nord", "A")
    b = _create_personne(client, headers, "Milieu", "B")
    c = _create_personne(client, headers, "Sud", "C")
    _create_relation(client, headers, a, b, "connaissance", 3)
    _create_relation(client, headers, b, c, "famille", 4)

    response = client.get("/relations/chemin", params={"depart_id": a, "arrivee_id": c}, headers=headers)
    data = response.json()
    assert data["trouve"] is True
    assert data["longueur"] == 2
    assert [n["id"] for n in data["nodes"]] == [a, b, c]


def test_aucun_chemin_entre_deux_personnes_isolees(client, auth_headers):
    headers = auth_headers("enqueteur")
    a = _create_personne(client, headers, "Isole1", "X")
    b = _create_personne(client, headers, "Isole2", "Y")

    response = client.get("/relations/chemin", params={"depart_id": a, "arrivee_id": b}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["trouve"] is False
    assert data["nodes"] == []


def test_depart_et_arrivee_identiques_est_rejete(client, auth_headers):
    headers = auth_headers("enqueteur")
    a = _create_personne(client, headers, "Seul", "Z")
    response = client.get("/relations/chemin", params={"depart_id": a, "arrivee_id": a}, headers=headers)
    assert response.status_code == 400
