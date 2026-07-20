from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Any, Mapping


class AuthenticationRequiredError(RuntimeError):
    """Raised when a request has no authenticated OIDC principal."""


class VerifiedEmailRequiredError(RuntimeError):
    """Raised when Authing has not supplied a verified email address."""


@dataclass(frozen=True)
class AuthIdentity:
    user_id: str
    issuer: str
    subject: str
    email: str
    name: str


def _claim(claims: Any, name: str, default: Any = None) -> Any:
    if isinstance(claims, Mapping):
        if name in claims:
            return claims.get(name, default)
        return getattr(claims, name, default)
    return getattr(claims, name, default)


def _is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def internal_user_id(issuer: str, subject: str) -> str:
    """Return the non-reversible application id for an OIDC principal."""
    normalized_issuer = issuer.strip().rstrip("/")
    normalized_subject = subject.strip()
    if not normalized_issuer or not normalized_subject:
        raise AuthenticationRequiredError("OIDC claims are missing issuer or subject.")
    return hashlib.sha256(f"{normalized_issuer}\0{normalized_subject}".encode("utf-8")).hexdigest()


def identity_from_claims(claims: Any) -> AuthIdentity:
    """Validate Authing/OIDC claims and construct the application's identity."""
    issuer = str(_claim(claims, "iss", "") or "").strip()
    subject = str(_claim(claims, "sub", "") or "").strip()
    email = str(_claim(claims, "email", "") or "").strip().lower()
    if not issuer or not subject:
        raise AuthenticationRequiredError("OIDC claims are missing issuer or subject.")
    if not email or not _is_true(_claim(claims, "email_verified", False)):
        raise VerifiedEmailRequiredError("请先在 Authing 中绑定并验证邮箱，然后重新登录。")
    name = str(_claim(claims, "name", "") or _claim(claims, "nickname", "") or email).strip()
    return AuthIdentity(
        user_id=internal_user_id(issuer, subject),
        issuer=issuer.rstrip("/"),
        subject=subject,
        email=email,
        name=name or email,
    )


def authentication_mode() -> str:
    """Return ``oidc`` by default; local access must be explicitly enabled."""
    configured = os.getenv("APP_AUTH_MODE")
    if configured is None:
        try:
            import streamlit as st

            configured = str(st.secrets.get("app", {}).get("auth_mode", "oidc"))
        except Exception:
            configured = "oidc"
    return configured.strip().lower()


def development_identity() -> AuthIdentity:
    if authentication_mode() != "disabled":
        raise AuthenticationRequiredError("Development identity is disabled.")
    issuer = "urn:doi1:development"
    subject = os.getenv("DEV_USER_ID", "local-developer").strip() or "local-developer"
    email = os.getenv("DEV_USER_EMAIL", "developer@localhost.invalid").strip().lower()
    name = os.getenv("DEV_USER_NAME", "本地开发者").strip() or email
    return AuthIdentity(internal_user_id(issuer, subject), issuer, subject, email, name)


def current_identity(st_module: Any | None = None) -> AuthIdentity | None:
    """Read the current identity without rendering or stopping the Streamlit app."""
    if authentication_mode() == "disabled":
        return development_identity()
    if st_module is None:
        import streamlit as st_module  # type: ignore[no-redef]
    user = getattr(st_module, "user", None)
    if user is None or not bool(_claim(user, "is_logged_in", False)):
        return None
    return identity_from_claims(user)


def require_authenticated_user(st_module: Any | None = None) -> AuthIdentity:
    """Full-site Streamlit gate. It returns only after a verified login."""
    if st_module is None:
        import streamlit as st_module  # type: ignore[no-redef]
    try:
        identity = current_identity(st_module)
    except VerifiedEmailRequiredError as exc:
        st_module.error(str(exc))
        if st_module.button("退出并重新绑定账号", type="primary"):
            st_module.logout()
        st_module.stop()
        raise
    if identity is not None:
        return identity
    st_module.title("生物医学文献分析工作台")
    st_module.info("请使用微信、QQ 或邮箱完成 Authing 登录。微信/QQ 首次登录需绑定并验证邮箱。")
    if st_module.button("登录 / 注册", type="primary"):
        st_module.login("authing")
    st_module.stop()
    raise AuthenticationRequiredError("Authentication is required.")
