def _create_personne(client, headers, nom, prenom):
    response = client.post("/personnes", json={"nom": nom, "prenom": prenom, "role": "suspect"}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


def _create_vehicule(client, headers, plaque, proprietaire_id=None):
    payload = {"plaque_immatriculation": plaque, "statut": "normal"}
    if proprietaire_id:
        payload["proprietaire_id"] = proprietaire_id
    response = client.post("/vehicules", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


def test_le_graphe_inclut_un_noeud_lieu_pour_l_adresse_de_l_incident(client, auth_headers, db_session):
    """Cahier des charges 3.3 : le graphe doit relier individus, véhicules
    ET lieux — pas seulement des personnes entre elles ou via la propriété
    d'un véhicule."""
    import app.models as models

    headers = auth_headers("enqueteur")
    p = _create_personne(client, headers, "Petit", "Jean")

    incident = models.Incident(
        type_infraction="vol",
        date_heure="2026-03-01T10:00:00",
        adresse="12 rue des Lilas",
        statut="ouvert",
        gravite="moyenne",
    )
    personne = db_session.query(models.Personne).filter(models.Personne.id == p).first()
    incident.personnes.append(personne)
    db_session.add(incident)
    db_session.commit()

    graphe = client.get("/relations/graphe", headers=headers).json()
    lieux = [n for n in graphe["nodes"] if n["type"] == "lieu"]
    assert len(lieux) == 1
    assert lieux[0]["label"] == "12 rue des Lilas"
    liens_lieu = [e for e in graphe["edges"] if e["type_relation"] == "lieu_incident"]
    assert any(e["source"] == p and e["target"] == lieux[0]["id"] for e in liens_lieu)


def test_le_graphe_relie_personne_et_vehicule_co_impliques_dans_un_incident(client, auth_headers, db_session):
    """Un véhicule impliqué dans un incident avec une personne qui n'en est
    pas le propriétaire (ex. véhicule volé/prêté) doit quand même apparaître
    relié à cette personne, pas seulement à son propriétaire."""
    import app.models as models

    headers = auth_headers("enqueteur")
    conducteur = _create_personne(client, headers, "Roux", "Sam")
    proprietaire = _create_personne(client, headers, "Blanc", "Eva")
    vehicule_id = _create_vehicule(client, headers, "AB-123-CD", proprietaire_id=proprietaire)

    incident = models.Incident(
        type_infraction="conduite sans permis",
        date_heure="2026-03-02T08:00:00",
        statut="ouvert",
        gravite="faible",
    )
    conducteur_obj = db_session.query(models.Personne).filter(models.Personne.id == conducteur).first()
    vehicule_obj = db_session.query(models.Vehicule).filter(models.Vehicule.id == vehicule_id).first()
    incident.personnes.append(conducteur_obj)
    incident.vehicules.append(vehicule_obj)
    db_session.add(incident)
    db_session.commit()

    graphe = client.get("/relations/graphe", headers=headers).json()
    co_edges = [e for e in graphe["edges"] if e["type_relation"] == "vu_ensemble"]
    assert any(e["source"] == conducteur and e["target"] == vehicule_id for e in co_edges)
    # Le lien de propriété (avec Eva) doit coexister avec le lien "vu_ensemble" (avec Sam).
    own_edges = [e for e in graphe["edges"] if e["type_relation"] == "proprietaire"]
    assert any(e["source"] == proprietaire and e["target"] == vehicule_id for e in own_edges)


def test_filtre_type_relation_lieu_incident_isole_les_lieux(client, auth_headers, db_session):
    import app.models as models

    headers = auth_headers("enqueteur")
    p = _create_personne(client, headers, "Vert", "Tom")
    incident = models.Incident(
        type_infraction="tapage",
        date_heure="2026-03-03T22:00:00",
        adresse="Place du Marché",
        statut="ouvert",
        gravite="faible",
    )
    personne = db_session.query(models.Personne).filter(models.Personne.id == p).first()
    incident.personnes.append(personne)
    db_session.add(incident)
    db_session.commit()

    graphe = client.get(
        "/relations/graphe", params={"type_relation": "lieu_incident"}, headers=headers
    ).json()
    assert all(e["type_relation"] == "lieu_incident" for e in graphe["edges"])
    assert any(n["type"] == "lieu" for n in graphe["nodes"])
