"""Authentication and Granular Permission Management for Vision Internal REST API.

Provides:
- Granular permission scopes (control:flash, control:quality, control:fps, control:audio, stream:video, stream:audio, admin)
- Role-based token management (admin, operator, viewer, controller)
- Persistent JSON token storage with automatic bootstrapping
- FastAPI dependency injection for endpoint permission enforcement
- WebSocket permission authentication
"""

import json
import os
import secrets
import time
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import Header, Query, Request, HTTPException, WebSocket, status

from config import API_AUTH_ENABLED, ALLOW_LOCAL_LOOPBACK_BYPASS, PERMISSIONS_FILE


class PermissionScope:
    """Pre-defined granular permission scopes for internal API and stream access."""
    ALL = "*"
    ADMIN = "admin"
    CONTROL_ALL = "control:*"
    CONTROL_FLASH = "control:flash"
    CONTROL_QUALITY = "control:quality"
    CONTROL_FPS = "control:fps"
    CONTROL_AUDIO = "control:audio"
    STREAM_ALL = "stream:*"
    STREAM_VIDEO = "stream:video"
    STREAM_AUDIO = "stream:audio"
    STATUS_READ = "status:read"

    @classmethod
    def all_scopes(cls) -> List[str]:
        return [
            cls.ALL,
            cls.ADMIN,
            cls.CONTROL_ALL,
            cls.CONTROL_FLASH,
            cls.CONTROL_QUALITY,
            cls.CONTROL_FPS,
            cls.CONTROL_AUDIO,
            cls.STREAM_ALL,
            cls.STREAM_VIDEO,
            cls.STREAM_AUDIO,
            cls.STATUS_READ,
        ]


ROLE_DEFINITIONS: Dict[str, List[str]] = {
    "admin": [PermissionScope.ALL],
    "operator": [
        PermissionScope.CONTROL_ALL,
        PermissionScope.STREAM_ALL,
        PermissionScope.STATUS_READ,
    ],
    "viewer": [
        PermissionScope.STREAM_ALL,
        PermissionScope.STATUS_READ,
    ],
    "controller": [
        PermissionScope.CONTROL_ALL,
        PermissionScope.STATUS_READ,
    ],
}


class TokenData(BaseModel):
    """Represents a validated API token with its assigned roles and permissions."""
    id: str
    token: str
    name: str
    role: str = "custom"
    permissions: List[str] = Field(default_factory=list)
    created_at: str
    description: Optional[str] = ""

    def has_permission(self, required_permission: str) -> bool:
        """Evaluates whether this token satisfies the requested permission scope."""
        perms = set(self.permissions)
        # Superuser wildcards
        if PermissionScope.ALL in perms or PermissionScope.ADMIN in perms:
            return True
        # Exact match
        if required_permission in perms:
            return True
        # Domain wildcards
        if required_permission.startswith("control:") and PermissionScope.CONTROL_ALL in perms:
            return True
        if required_permission.startswith("stream:") and PermissionScope.STREAM_ALL in perms:
            return True
        return False


class TokenCreateRequest(BaseModel):
    name: str = Field(..., description="Descriptive identifier for the client or program")
    role: Optional[str] = Field("custom", description="Preset role: 'admin', 'operator', 'viewer', 'controller', or 'custom'")
    permissions: Optional[List[str]] = Field(default_factory=list, description="Explicit permissions if role is 'custom'")
    description: Optional[str] = Field("", description="Optional purpose note")


class PermissionsManager:
    """Manages token issuance, validation, revocation, and persistence."""

    def __init__(self, file_path: str = PERMISSIONS_FILE):
        self.file_path = file_path
        self.auth_enabled: bool = API_AUTH_ENABLED
        self.allow_local_loopback_bypass: bool = ALLOW_LOCAL_LOOPBACK_BYPASS
        self._tokens: Dict[str, TokenData] = {}
        self.load()

    def load(self):
        """Loads tokens from disk or initializes defaults if not present."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.auth_enabled = data.get("auth_enabled", self.auth_enabled)
                    self.allow_local_loopback_bypass = data.get("allow_local_loopback_bypass", self.allow_local_loopback_bypass)
                    self._tokens = {
                        tok_str: TokenData(**tok_val)
                        for tok_str, tok_val in data.get("tokens", {}).items()
                    }
                    if self._tokens:
                        return
            except Exception as e:
                print(f"[Auth] Notice reading permissions file: {e}. Reinitializing.")

        # Initialize default secure tokens if empty or file doesn't exist
        self._bootstrap_defaults()

    def save(self):
        """Persists tokens to disk."""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.file_path)), exist_ok=True)
            data = {
                "auth_enabled": self.auth_enabled,
                "allow_local_loopback_bypass": self.allow_local_loopback_bypass,
                "tokens": {
                    tok_str: tok.model_dump()
                    for tok_str, tok in self._tokens.items()
                },
            }
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Auth] Warning: Could not persist permissions file: {e}")

    def _bootstrap_defaults(self):
        """Creates initial administrative, service, and viewer keys."""
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        # Check environment override
        env_admin_key = os.environ.get("VISION_ADMIN_KEY")
        admin_token = env_admin_key if env_admin_key else f"adm_{secrets.token_hex(16)}"
        service_token = f"srv_{secrets.token_hex(16)}"
        viewer_token = f"view_{secrets.token_hex(16)}"

        self._tokens[admin_token] = TokenData(
            id="tok_admin_root",
            token=admin_token,
            name="System Master Admin",
            role="admin",
            permissions=[PermissionScope.ALL],
            created_at=now,
            description="Full unrestricted administrative and hardware access",
        )

        self._tokens[service_token] = TokenData(
            id="tok_internal_service",
            token=service_token,
            name="Internal Desktop GUI & Services",
            role="operator",
            permissions=ROLE_DEFINITIONS["operator"],
            created_at=now,
            description="Default internal token for desktop GUI and automation scripts",
        )

        self._tokens[viewer_token] = TokenData(
            id="tok_media_viewer",
            token=viewer_token,
            name="Media Stream Viewer",
            role="viewer",
            permissions=ROLE_DEFINITIONS["viewer"],
            created_at=now,
            description="Read-only access for VLC, OpenCV, and browser players",
        )

        self.save()
        print(f"[Auth] Initialized permissions with Master Key: {admin_token[:6]}... (stored in permissions.json)")

    def get_token(self, token_str: str) -> Optional[TokenData]:
        """Retrieves a token by its secret token string."""
        if not token_str:
            return None
        return self._tokens.get(token_str)

    def verify_token(self, token_str: str, required_permission: str) -> bool:
        """Validates token and checks if it satisfies the required permission."""
        tok = self.get_token(token_str)
        if not tok:
            return False
        return tok.has_permission(required_permission)

    def get_service_token(self) -> str:
        """Returns the internal service token for local GUI and automated components."""
        for tok in self._tokens.values():
            if tok.role == "operator" or tok.id == "tok_internal_service":
                return tok.token
        # Fallback to admin token
        for tok in self._tokens.values():
            if tok.role == "admin":
                return tok.token
        return ""

    def get_admin_token(self) -> str:
        """Returns the primary admin token."""
        for tok in self._tokens.values():
            if tok.role == "admin":
                return tok.token
        return ""

    def get_viewer_token(self) -> str:
        """Returns the primary viewer token."""
        for tok in self._tokens.values():
            if tok.role == "viewer":
                return tok.token
        return ""

    def get_token_by_role(self, role: str) -> str:
        """Returns the first token matching the requested role."""
        for tok in self._tokens.values():
            if tok.role == role:
                return tok.token
        return ""

    def create_token(
        self,
        name: str,
        role: str = "custom",
        permissions: Optional[List[str]] = None,
        description: str = "",
    ) -> TokenData:
        """Issues a new permission token."""
        prefix = "adm_" if role == "admin" else ("srv_" if role in ("operator", "controller") else "tok_")
        token_str = f"{prefix}{secrets.token_hex(16)}"
        token_id = f"tok_{secrets.token_hex(4)}"
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        assigned_perms = list(permissions or [])
        if role in ROLE_DEFINITIONS and not assigned_perms:
            assigned_perms = ROLE_DEFINITIONS[role].copy()

        new_tok = TokenData(
            id=token_id,
            token=token_str,
            name=name,
            role=role,
            permissions=assigned_perms,
            created_at=now,
            description=description,
        )
        self._tokens[token_str] = new_tok
        self.save()
        return new_tok

    def revoke_token(self, identifier: str) -> bool:
        """Revokes a token by secret string or ID."""
        target_key = None
        for tok_str, tok in self._tokens.items():
            if tok_str == identifier or tok.id == identifier:
                target_key = tok_str
                break

        if target_key:
            del self._tokens[target_key]
            self.save()
            return True
        return False

    def list_tokens(self) -> List[dict]:
        """Returns all configured tokens with masked secret values for security."""
        result = []
        for tok in self._tokens.values():
            masked_token = f"{tok.token[:6]}...{tok.token[-4:]}" if len(tok.token) > 10 else "***"
            result.append({
                "id": tok.id,
                "name": tok.name,
                "role": tok.role,
                "permissions": tok.permissions,
                "created_at": tok.created_at,
                "description": tok.description,
                "masked_token": masked_token,
            })
        return result


# Singleton manager
auth_manager = PermissionsManager()


def extract_token_from_request(
    request: Request,
    x_api_key: Optional[str] = None,
    authorization: Optional[str] = None,
    token_query: Optional[str] = None,
    api_key_query: Optional[str] = None,
) -> Optional[str]:
    """Extracts authentication token from headers or query parameters."""
    if x_api_key:
        return x_api_key.strip()
    if authorization:
        parts = authorization.strip().split(" ")
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        return authorization.strip()
    if token_query:
        return token_query.strip()
    if api_key_query:
        return api_key_query.strip()
    return None


def require_permission(required_permission: str):
    """
    FastAPI dependency enforcing that the request holds an API token
    possessing the required permission scope.
    """
    async def permission_checker(
        request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        authorization: Optional[str] = Header(None),
        token_query: Optional[str] = Query(None, alias="token"),
        api_key_query: Optional[str] = Query(None, alias="api_key"),
    ) -> TokenData:
        # If API auth is completely disabled in config, bypass check
        if not auth_manager.auth_enabled:
            return TokenData(
                id="tok_unrestricted",
                token="unrestricted",
                name="Unrestricted System",
                role="admin",
                permissions=[PermissionScope.ALL],
                created_at="",
            )

        token_str = extract_token_from_request(
            request,
            x_api_key=x_api_key,
            authorization=authorization,
            token_query=token_query,
            api_key_query=api_key_query,
        )

        client_host = request.client.host if request.client else "unknown"

        # Local loopback bypass check (if enabled in config and no key was provided)
        if not token_str and auth_manager.allow_local_loopback_bypass:
            if client_host in ("127.0.0.1", "::1", "localhost"):
                return TokenData(
                    id="tok_local_loopback",
                    token="local_loopback",
                    name="Localhost Loopback",
                    role="operator",
                    permissions=ROLE_DEFINITIONS["operator"],
                    created_at="",
                )

        if not token_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "code": "UNAUTHORIZED",
                    "message": "Authentication required. Provide 'X-API-Key' header, 'Authorization: Bearer <token>', or '?token=' query parameter.",
                    "required_permission": required_permission,
                },
            )

        token_data = auth_manager.get_token(token_str)
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "code": "INVALID_TOKEN",
                    "message": "The provided API key is invalid or has been revoked.",
                },
            )

        if not token_data.has_permission(required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "code": "PERMISSION_DENIED",
                    "message": f"Permission denied: operation requires '{required_permission}'.",
                    "required_permission": required_permission,
                    "granted_permissions": token_data.permissions,
                    "role": token_data.role,
                },
            )

        return token_data

    return permission_checker


def check_websocket_permission(websocket: WebSocket, required_permission: str) -> Optional[TokenData]:
    """Validates permissions for an incoming WebSocket connection."""
    if not auth_manager.auth_enabled:
        return TokenData(
            id="tok_ws_unrestricted",
            token="unrestricted",
            name="Unrestricted WebSocket",
            role="admin",
            permissions=[PermissionScope.ALL],
            created_at="",
        )

    token_str = (
        websocket.query_params.get("token")
        or websocket.query_params.get("api_key")
        or websocket.headers.get("x-api-key")
    )

    client_host = websocket.client.host if websocket.client else "unknown"
    if not token_str and auth_manager.allow_local_loopback_bypass:
        if client_host in ("127.0.0.1", "::1", "localhost"):
            return TokenData(
                id="tok_local_ws",
                token="local_ws",
                name="Localhost WebSocket",
                role="operator",
                permissions=ROLE_DEFINITIONS["operator"],
                created_at="",
            )

    if not token_str:
        return None

    token_data = auth_manager.get_token(token_str)
    if not token_data or not token_data.has_permission(required_permission):
        return None

    return token_data
