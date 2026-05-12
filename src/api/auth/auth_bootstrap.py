"""Single entrypoint for assembling the auth subsystem at startup.

Encapsulates three things the rest of ``server.py`` shouldn't have
to know about:

1. Auto-generating ``jwt_secret`` on first run and persisting it to
   ``local.yaml`` via ``save_section_to_yaml`` (preserves any other
   ``web_auth`` keys).
2. Wiring ``PasswordHasher`` / ``JwtSessionService`` / ``LockoutTracker``
   into a single ``AuthService`` instance.
3. Returning the ``JwtSessionService`` separately so ``init_auth``
   in the dependencies module can share the exact same instance --
   no chance of two services with mismatched ``session_version``.

Production callers use ``build_auth_subsystem(config)``. Tests build
the pieces directly so they never touch the filesystem.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.api.auth.auth_service import AuthService
from src.api.auth.jwt_session import JwtSessionService
from src.api.auth.lockout_tracker import LockoutTracker
from src.api.auth.password_hasher import PasswordHasher
from src.config import AppConfig, save_section_to_yaml

logger = logging.getLogger(__name__)


@dataclass
class AuthSubsystem:
    service: AuthService
    jwt_service: JwtSessionService


def build_auth_subsystem(config: AppConfig) -> AuthSubsystem:
    """Assemble the auth subsystem from a loaded ``AppConfig``."""
    web_auth = config.web_auth
    _ensure_jwt_secret(web_auth)

    jwt_service = JwtSessionService(
        secret=web_auth.jwt_secret,
        expiry_minutes=web_auth.jwt_expiry_minutes,
        session_version=web_auth.session_version,
    )
    auth_service = AuthService(
        web_auth=web_auth,
        hasher=PasswordHasher(),
        lockout=LockoutTracker(
            max_attempts=web_auth.lockout_attempts,
            cooldown_minutes=web_auth.lockout_cooldown_minutes,
        ),
        jwt_service=jwt_service,
        persist=_make_persister(),
    )
    return AuthSubsystem(service=auth_service, jwt_service=jwt_service)


def _ensure_jwt_secret(web_auth) -> None:
    """Generate and persist a secret on first run if none is set."""
    if web_auth.jwt_secret:
        return
    secret = JwtSessionService.generate_secret()
    web_auth.jwt_secret = secret
    save_section_to_yaml("web_auth", {"jwt_secret": secret})
    logger.info(
        "web_auth: generated jwt_secret on first run; persisted to local.yaml"
    )


def _make_persister():
    """Return a callable that writes web_auth field updates to local.yaml."""
    def _persist(values: dict) -> None:
        save_section_to_yaml("web_auth", values)
    return _persist
