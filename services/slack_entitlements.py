"""
Who may configure the per-workspace LayerV API key in Slack.

Primary (no admin.* scopes):
  Enterprise Grid — `users.info` → `enterprise_user.is_primary_owner` / `is_owner` / `is_admin`
  (organization-level roles; see Slack user object reference).

Optional fallback:
  `admin.roles.listAssignments` with a **user** OAuth token that has `admin.roles:read`
  (set `SLACK_ADMIN_USER_TOKEN`, `USE_ADMIN_ROLES_API_FALLBACK`, `SLACK_ORG_ADMIN_ROLE_IDS`).
  App must be installed at the Enterprise org; see Slack Admin API docs.

Single workspace (no enterprise_id): optional workspace-level admin fallback (configurable).
"""

from __future__ import annotations

import logging
from typing import Literal

from slack_sdk.web.async_client import AsyncWebClient

from config import settings

logger = logging.getLogger(__name__)

Eligibility = Literal["ok", "enterprise_org_admin_required", "denied"]


def _is_enterprise_org_admin(user: dict) -> bool:
    eu = user.get("enterprise_user") or {}
    if not eu.get("enterprise_id"):
        return False
    return bool(
        eu.get("is_primary_owner")
        or eu.get("is_owner")
        or eu.get("is_admin")
    )


def _is_workspace_admin(user: dict) -> bool:
    return bool(
        user.get("is_primary_owner")
        or user.get("is_owner")
        or user.get("is_admin")
    )


def _configured_org_admin_role_ids() -> list[str]:
    return [r.strip() for r in settings.slack_org_admin_role_ids.split(",") if r.strip()]


async def _admin_roles_confirms_org_admin(user_id: str, enterprise_id: str) -> bool:
    """
    Optional: use Admin API admin.roles.listAssignments (requires user token + admin.roles:read).
    """
    if not settings.use_admin_roles_api_fallback or not settings.slack_admin_user_token:
        return False
    role_ids = _configured_org_admin_role_ids()
    if not role_ids:
        logger.debug("Admin roles API fallback enabled but SLACK_ORG_ADMIN_ROLE_IDS is empty")
        return False
    admin_client = AsyncWebClient(token=settings.slack_admin_user_token)
    cursor: str | None = None
    try:
        while True:
            kwargs: dict = {"limit": 200, "entity_ids": [enterprise_id]}
            if cursor:
                kwargs["cursor"] = cursor
            resp = await admin_client.admin_roles_listAssignments(**kwargs)
            if not resp.get("ok"):
                logger.warning(
                    "admin.roles.listAssignments failed: %s",
                    resp.get("error"),
                )
                return False
            for a in resp.get("role_assignments") or []:
                if a.get("user_id") != user_id:
                    continue
                if a.get("role_id") in role_ids:
                    logger.info(
                        "Admin roles API: user %s has org role %s",
                        user_id,
                        a.get("role_id"),
                    )
                    return True
            cursor = (resp.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break
    except Exception as e:
        logger.warning("admin.roles.listAssignments raised: %s", e)
        return False
    return False


async def classify_layerv_key_eligibility(client: AsyncWebClient, user_id: str) -> Eligibility:
    """
    - ok: may manage LayerV key via DM commands
    - enterprise_org_admin_required: user is on Enterprise Grid but not an org admin/owner
    - denied: not allowed (e.g. member, or fallback disabled and not on Grid)
    """
    try:
        r = await client.users_info(user=user_id)
        if not r.get("ok") or not r.get("user"):
            logger.warning(f"users_info not ok for {user_id}: {r.get('error')}")
            return "denied"
        u = r["user"]

        if _is_enterprise_org_admin(u):
            return "ok"

        eu = u.get("enterprise_user") or {}
        enterprise_id = eu.get("enterprise_id")
        if enterprise_id:
            if await _admin_roles_confirms_org_admin(user_id, enterprise_id):
                return "ok"
            logger.info(
                "User %s in enterprise %s is not an Enterprise org admin/owner (users.info + optional Admin API)",
                user_id,
                enterprise_id,
            )
            return "enterprise_org_admin_required"

        if settings.layerv_key_allow_workspace_admin_if_not_enterprise_grid and _is_workspace_admin(u):
            return "ok"

        logger.info("User %s denied layerv key management (not workspace admin or fallback off)", user_id)
        return "denied"
    except Exception as e:
        logger.warning(f"classify_layerv_key_eligibility failed for {user_id}: {e}")
        return "denied"


async def can_manage_layerv_key(client: AsyncWebClient, user_id: str) -> bool:
    return await classify_layerv_key_eligibility(client, user_id) == "ok"
