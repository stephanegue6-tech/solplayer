#!/usr/bin/env python3
"""
Générateur de codes de licence SolPlay Pro.

Ce script génère des codes d'activation compatibles avec la logique de
vérification embarquée dans l'app (TrialManager.kt -> validateCodeOffline).

RÈGLE DE VALIDATION UTILISÉE PAR L'APP :
- Le code doit faire au moins 10 caractères
- Les 2 derniers caractères doivent être les 2 premiers caractères hexadécimaux
  du SHA-256 du reste du code (une sorte de "clé de contrôle")

⚠️ IMPORTANT :
Ce système est volontairement simple pour démarrer rapidement. Il n'empêche
pas un utilisateur technique de générer lui-même des codes valides s'il
regarde le code source de l'app (le code est en clair dans l'APK).
Pour une vraie protection commerciale, il faudra migrer vers une vérification
côté serveur (voir suggestion en bas de ce fichier).

Utilisation :
    python3 generate_license_codes.py 20
    -> génère 20 codes valides et les affiche + les sauvegarde dans
       licenses_output.csv (avec une colonne "utilisé" à remplir toi-même
       pour garder trace de ce qui a été vendu).
"""

import hashlib
import random
import string
import sys
import csv
from datetime import datetime

PREFIX = "SOLPLAY-"  # préfixe visuel, purement cosmétique (pas vérifié par l'app)
BODY_LENGTH = 8       # longueur de la partie aléatoire avant la clé de contrôle


def compute_checksum(body: str) -> str:
    """Reproduit exactement la logique de TrialManager.validateCodeOffline()."""
    digest = hashlib.sha256(body.encode("utf-8")).digest()
    return digest[:1].hex()[:2]


def generate_one_code() -> str:
    body = "".join(random.choices(string.ascii_uppercase + string.digits, k=BODY_LENGTH))
    checksum = compute_checksum(body)
    return f"{body}{checksum}".upper()


def full_display_code(code: str) -> str:
    """Ajoute le préfixe SOLPLAY- pour l'affichage/l'envoi au client.
    Note : l'app attend le code SANS préfixe dans le champ d'activation
    (elle ne vérifie que 'body + checksum'). Si tu veux que l'utilisateur
    colle le code avec le préfixe, adapte TrialManager.kt pour retirer le
    préfixe avant validation."""
    return f"{PREFIX}{code}"


def verify_code(code: str) -> bool:
    """Vérifie un code comme le ferait l'app (utile pour tester)."""
    code = code.strip().upper()
    if len(code) < 10:
        return False
    body, checksum = code[:-2], code[-2:]
    return compute_checksum(body) == checksum.lower()


def main():
    count = 10
    if len(sys.argv) > 1:
        try:
            count = int(sys.argv[1])
        except ValueError:
            print("Usage: python3 generate_license_codes.py [nombre_de_codes]")
            sys.exit(1)

    codes = [generate_one_code() for _ in range(count)]

    filename = "licenses_output.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["code_a_activer_dans_l_app", "code_affichage_avec_prefixe", "date_generation", "utilise", "client", "email_client"])
        for code in codes:
            writer.writerow([code, full_display_code(code), datetime.now().strftime("%Y-%m-%d"), "non", "", ""])

    print(f"{count} codes générés avec succès.\n")
    header_label = "Code a entrer dans l'app"
    print(f"{header_label:30} | Affichage client")
    print("-" * 60)
    for code in codes:
        print(f"{code:30} | {full_display_code(code)}")

    print(f"\nFichier sauvegardé : {filename}")
    print("\nVérification interne (tous doivent être True) :")
    print(all(verify_code(c) for c in codes))


if __name__ == "__main__":
    main()

# ---------------------------------------------------------------------------
# ÉVOLUTION RECOMMANDÉE POUR LA PRODUCTION (protection anti-piratage réelle)
# ---------------------------------------------------------------------------
# 1. Héberger une petite API (ex: Firebase Cloud Functions, ou un simple
#    serveur Node/Python) qui stocke les codes générés ici dans une base
#    de données avec leur statut (utilisé / non utilisé / lié à quel appareil).
# 2. Modifier TrialManager.kt (activateLicense) pour faire un appel réseau
#    vers cette API au lieu de valider hors-ligne, en envoyant le code +
#    un identifiant unique de l'appareil (Settings.Secure.ANDROID_ID).
# 3. L'API répond "valide" seulement si le code existe, n'a jamais été
#    utilisé (ou est déjà lié à ce même appareil), puis elle marque le
#    code comme consommé.
# Cela empêche un même code d'être partagé/réutilisé sur plusieurs appareils.
