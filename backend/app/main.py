import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from . import models
from .database import Base, engine
from .rate_limit import limiter
from .routers import (
    anpr,
    audit_logs,
    auth,
    incidents,
    integrations_nationales,
    personnes,
    preuves,
    relations,
    rgpd,
    vehicules,
)

# Crée les tables si elles n'existent pas encore. Pratique pour un premier
# démarrage local, mais toute évolution de schéma ultérieure doit passer
# par Alembic (voir migrations/ et README) plutôt que par create_all.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CrimTrack API",
    description="Plateforme intégrée d'analyse et de gestion criminalistique — socle commun.",
    version="0.3.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(incidents.router)
app.include_router(personnes.router)
app.include_router(vehicules.router)
app.include_router(relations.router)
app.include_router(preuves.router)
app.include_router(anpr.router)
app.include_router(audit_logs.router)
app.include_router(rgpd.router)
app.include_router(integrations_nationales.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "service": "crimtrack-api"}


# --- Frontend statique (build desktop uniquement) --------------------------
#
# En usage serveur classique (docker-compose, déploiement web), cette
# variable n'est pas définie : "/" répond alors le petit JSON de santé,
# comme avant. En build desktop, Electron (crimtrack-desktop/electron/
# main.js) positionne CRIMTRACK_FRONTEND_DIR vers le dossier frontend
# embarqué dans l'exécutable, et "/" sert l'interface web à la place —
# les deux ne peuvent pas cohabiter sur le même chemin, donc l'un exclut
# l'autre.
#
# Le montage est fait en DERNIER, après toutes les routes API : Starlette
# résout les routes dans l'ordre d'enregistrement, donc /incidents, /auth,
# etc. restent prioritaires sur ce catch-all.
_frontend_dir = os.getenv("CRIMTRACK_FRONTEND_DIR")
if _frontend_dir and os.path.isdir(_frontend_dir):
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
else:
    @app.get("/", tags=["health"])
    def health_root():
        return {"status": "ok", "service": "crimtrack-api"}
