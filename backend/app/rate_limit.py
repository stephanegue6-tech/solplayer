"""Limitation de débit (anti brute-force), notamment sur /auth/login.

Défini dans son propre module pour être importable à la fois par main.py
(rattachement à l'app + gestionnaire d'erreur) et par les routers (décorateur
`@limiter.limit(...)`) sans import circulaire.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
