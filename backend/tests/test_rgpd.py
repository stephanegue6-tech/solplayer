from datetime import datetime, timedelta

from app import models, rgpd


def _make_incident(db_session, *, statut, jours_anciennete):
    incident = models.Incident(
        type_infraction="vol",
        date_heure=datetime.utcnow() - timedelta(days=jours_anciennete),
        statut=statut,
        gravite="faible",
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)
    return incident


def _make_personne(db_session, *, nom="Dupont", prenom="Jean"):
    personne = models.Personne(nom=nom, prenom=prenom, role="suspect", statut="actif")
    db_session.add(personne)
    db_session.commit()
    db_session.refresh(personne)
    return personne


def test_dossier_ouvert_jamais_purge_meme_ancien(client, auth_headers, db_session):
    incident = _make_incident(db_session, statut="ouvert", jours_anciennete=5000)
    personne = _make_personne(db_session)
    incident.personnes.append(personne)
    db_session.commit()

    candidats = rgpd.identifier_candidats(db_session, retention_days=1095)
    assert incident.id not in {c.incident_id for c in candidats}


def test_dossier_clos_recent_pas_encore_purgeable(client, db_session):
    incident = _make_incident(db_session, statut="clos", jours_anciennete=10)
    personne = _make_personne(db_session, nom="Recent")
    incident.personnes.append(personne)
    db_session.commit()

    candidats = rgpd.identifier_candidats(db_session, retention_days=1095)
    assert incident.id not in {c.incident_id for c in candidats}


def test_dossier_clos_ancien_est_purge_et_personne_anonymisee(client, auth_headers, db_session):
    incident = _make_incident(db_session, statut="clos", jours_anciennete=2000)
    personne = _make_personne(db_session, nom="Ancien", prenom="Suspect")
    incident.personnes.append(personne)
    db_session.commit()
    personne_id = personne.id

    headers = auth_headers("administrateur")
    response = client.post("/rgpd/purge", params={"retention_days": 1095}, headers=headers)
    assert response.status_code == 200
    resume = response.json()
    assert resume["personnes_anonymisees"] >= 1

    db_session.expire_all()
    personne_purgee = db_session.query(models.Personne).filter(models.Personne.id == personne_id).first()
    assert personne_purgee.nom == rgpd.ANONYMISATION_NOM
    assert personne_purgee.prenom == ""
    assert personne_purgee.signalement is None
    # Le rôle (donnée statistique, non ré-identifiante) est conservé.
    assert personne_purgee.role == "suspect"


def test_personne_liee_a_un_dossier_encore_actif_nest_pas_anonymisee(client, auth_headers, db_session):
    vieux_dossier_clos = _make_incident(db_session, statut="clos", jours_anciennete=2000)
    dossier_actif = _make_incident(db_session, statut="ouvert", jours_anciennete=2000)
    personne = _make_personne(db_session, nom="Double", prenom="Implique")
    vieux_dossier_clos.personnes.append(personne)
    dossier_actif.personnes.append(personne)
    db_session.commit()
    personne_id = personne.id

    headers = auth_headers("administrateur")
    client.post("/rgpd/purge", params={"retention_days": 1095}, headers=headers)

    db_session.expire_all()
    personne_toujours_identifiee = db_session.query(models.Personne).filter(models.Personne.id == personne_id).first()
    assert personne_toujours_identifiee.nom == "Double"


def test_seul_administrateur_peut_lancer_la_purge(client, auth_headers):
    response = client.post("/rgpd/purge", headers=auth_headers("opj"))
    assert response.status_code == 403

    response = client.get("/rgpd/candidats", headers=auth_headers("enqueteur"))
    assert response.status_code == 403
