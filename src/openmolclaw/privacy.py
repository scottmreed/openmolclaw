"""OpenMolClaw — local privacy posture + structure-redaction helpers.

Pure, standard-library-only helpers that (1) describe OpenMolClaw's privacy
posture for a loaded config and (2) keep raw chemical structures out of logs and
traces. Nothing here touches the network or names a model vendor.

Two responsibilities
--------------------
1. **Posture** — resolve the OpenRouter ZDR provider-routing controls, the
   local workspace save-mode, and the combined **Private Structure Mode**
   toggle (ZDR + no external lookups + no disk persistence, no silent
   weakening) into a plain dict that ``/api/privacy`` and the ``openmolclaw
   privacy`` CLI can report, plus the honest, non-overclaiming warnings and
   claim text that go with them.
2. **Redaction** — collapse structure-like text (SMILES / Molfile / InChI) to a
   marker before it can reach a log record or trace. Chemistry logic never uses
   the redactor — only logging/observability does.

Precedence for every privacy flag (highest wins)::

    explicit config value  >  environment variable  >  safe default

Design note: this is a *local-first* privacy story. OpenMolClaw does not send
structures to ChemIllusion servers and has no hosted database. ZDR Mode only
constrains requests made to OpenRouter; it cannot speak for local files, the
user's OpenRouter account logging, the operating system, browser extensions,
proxies, or custom providers. The copy below is deliberately precise about that.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

#: Supported local workspace persistence modes.
WORKSPACE_SAVE_MODES = ("local_json", "memory_only")

_TRUTHY = ("1", "true", "yes", "on")


def coerce_bool(
    value: Any = None,
    *,
    env: Optional[str] = None,
    default: bool = False,
) -> bool:
    """Resolve a boolean with ``config value > env var > default`` precedence.

    ``value`` is the explicit config value (``None`` means "not set"); ``env`` is
    an environment variable name consulted only when ``value`` is ``None``.
    """
    if value is not None:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in _TRUTHY
    if env is not None:
        raw = os.environ.get(env)
        if raw is not None and raw.strip() != "":
            return raw.strip().lower() in _TRUTHY
    return default


def resolve_workspace_save_mode(
    workspace_cfg: Optional[Dict[str, Any]],
    *,
    env: str = "OPENMOLCLAW_WORKSPACE_SAVE_MODE",
    default: str = "local_json",
) -> str:
    """Resolve the workspace save-mode (``local_json`` | ``memory_only``).

    Precedence matches :func:`coerce_bool`: an explicit ``save_mode`` in the
    config wins over the environment variable, which wins over the default.
    Unknown values fall back to ``default`` rather than raising.
    """
    cfg = workspace_cfg or {}
    explicit = cfg.get("save_mode")
    if explicit is None:
        explicit = os.environ.get(env)
    mode = str(explicit or default).strip().lower()
    return mode if mode in WORKSPACE_SAVE_MODES else default


def privacy_warnings(
    provider: str,
    *,
    openrouter_zdr: bool,
    save_mode: str,
) -> List[str]:
    """Honest, non-overclaiming warnings for the active posture.

    These map to PRD §7.3 (in-app warning) and §15 (feature-loss warnings). They
    are intentionally specific about what ZDR Mode does *not* cover.
    """
    warnings: List[str] = []
    provider = (provider or "").strip().lower()

    if provider == "openrouter":
        if openrouter_zdr:
            warnings.append(
                "ZDR (Zero Data Retention) Mode applies only to OpenRouter "
                "requests made by this local OpenMolClaw app. It does not change "
                "your OpenRouter account logging settings, your operating system "
                "logs, browser extensions, proxies, custom providers, or local "
                "workspace files."
            )
            warnings.append(
                "Some models or features may fail if no ZDR-compatible endpoint "
                "supports the required tool parameters; fallbacks are disabled, so "
                "uptime may be lower and requests may cost more."
            )
        else:
            warnings.append(
                "OpenRouter ZDR (Zero Data Retention) routing is OFF. Requests "
                "may be routed to endpoints that can retain data. Enable ZDR "
                "Mode to require Zero Data Retention endpoints."
            )
    elif provider == "local":
        warnings.append(
            "The active provider is local, so no OpenRouter request is made and "
            "OpenRouter ZDR (Zero Data Retention) routing does not apply to this "
            "provider."
        )
    else:
        warnings.append(
            f"The active provider ({provider or 'unknown'}) is a custom "
            "chat-completions endpoint, not OpenRouter, so OpenRouter ZDR (Zero "
            "Data Retention) routing does not apply. That endpoint's own "
            "data-retention policy governs requests sent to it."
        )

    if save_mode == "memory_only":
        warnings.append(
            "Workspace memory-only mode is ON: rendered structures are held in "
            "process memory for this session and are not written to "
            ".openmolclaw/workspaces on disk."
        )
    else:
        warnings.append(
            "Local workspace files may be saved on your own machine under "
            ".openmolclaw/workspaces. Enable memory-only workspace mode to avoid "
            "writing rendered structures to disk."
        )

    return warnings


def private_structure_mode_claim(
    provider: str,
    *,
    private_structure_mode: bool,
    openrouter_zdr: bool,
    blocks_external_lookup: bool,
    save_mode: str,
) -> Optional[str]:
    """The strongest honest claim OpenMolClaw can make, or ``None``.

    Mirrors ChemIllusion's researcher-exclusive "Private Structure Mode" claim,
    scoped down for a single-user local app (no role gating needed — whoever
    runs ``openmolclaw serve`` is the only user). The claim is only returned
    when every one of its clauses is actually true right now:

    * a request that reaches a hosted AI provider is ZDR-routed (``local``
      trivially satisfies this — no such request is ever made), *and*
    * external structure lookups (PubChem) are blocked, *and*
    * the workspace is memory-only, so nothing is written to disk unless the
      caller explicitly does so (e.g. exporting the workspace JSON).

    A custom (non-``local``, non-``openrouter``) endpoint can never earn this
    claim: OpenMolClaw cannot verify an arbitrary endpoint's retention policy,
    so making the claim there would overclaim.
    """
    if not private_structure_mode:
        return None
    provider = (provider or "").strip().lower()
    if provider not in ("local", "openrouter"):
        return None
    if provider == "openrouter" and not openrouter_zdr:
        return None
    if not blocks_external_lookup:
        return None
    if save_mode != "memory_only":
        return None
    return (
        "Private Structure Mode: structures are processed only for the active "
        "request, routed through ZDR-compatible AI providers where AI is "
        "required, excluded from model training, excluded from external "
        "molecule lookups, and not saved to projects or chat history unless "
        "you explicitly choose to save them."
    )


def describe_privacy(
    provider_info: Dict[str, Any],
    *,
    save_mode: str,
    local_workspace_disk_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the machine-readable ``/api/privacy`` / CLI posture payload.

    ``provider_info`` is the dict returned by :func:`config.describe_provider`
    (it carries the resolved ``privacy`` block). Never includes secrets.
    """
    provider = str(provider_info.get("provider") or "").strip().lower()
    privacy = dict(provider_info.get("privacy") or {})
    openrouter_zdr = bool(privacy.get("openrouter_zdr", False))
    deny_data_collection = bool(privacy.get("deny_data_collection", True))
    allow_fallbacks = bool(privacy.get("allow_fallbacks", False))
    require_parameters = bool(privacy.get("require_parameters", True))
    # Resolved upstream by config.resolve_privacy_flags() (config value > env
    # var > default); read here as an already-resolved boolean.
    private_structure_mode = bool(privacy.get("private_structure_mode", False))

    # No silent weakening: enabling Private Structure Mode always strengthens
    # the OpenRouter routing controls for this request, it can never be used to
    # turn them off while still claiming the mode is active.
    if private_structure_mode and provider == "openrouter":
        openrouter_zdr = True
        deny_data_collection = True
        allow_fallbacks = False
        require_parameters = True

    # Private Structure Mode always blocks external structure lookups (e.g.
    # PubChem name resolution) regardless of provider — the lookup query itself
    # would leave the machine, independent of which AI provider is configured.
    blocks_external_lookup = private_structure_mode

    # The exact ``provider`` object that OpenRouter requests will carry (empty
    # for a local provider, which makes no OpenRouter request).
    provider_policy: Dict[str, Any] = {}
    if provider == "openrouter":
        if openrouter_zdr:
            provider_policy["zdr"] = True
        if deny_data_collection:
            provider_policy["data_collection"] = "deny"
        if openrouter_zdr or deny_data_collection or require_parameters:
            provider_policy["allow_fallbacks"] = allow_fallbacks
        if require_parameters:
            provider_policy["require_parameters"] = True

    warnings = privacy_warnings(provider, openrouter_zdr=openrouter_zdr, save_mode=save_mode)
    claim = private_structure_mode_claim(
        provider,
        private_structure_mode=private_structure_mode,
        openrouter_zdr=openrouter_zdr,
        blocks_external_lookup=blocks_external_lookup,
        save_mode=save_mode,
    )
    if private_structure_mode and claim is None:
        if provider not in ("local", "openrouter"):
            warnings.append(
                "Private Structure Mode is ON, but the strongest claim cannot be "
                f"made for a custom endpoint ({provider or 'unknown'}): its "
                "retention policy is not verifiable by OpenMolClaw. External "
                "lookups are still blocked."
            )
        elif save_mode != "memory_only":
            warnings.append(
                "Private Structure Mode is ON, but the workspace is still saving "
                "to disk. Enable memory-only workspace mode to earn the full "
                "Private Structure Mode claim."
            )

    return {
        "provider": provider,
        "openrouter_zdr": openrouter_zdr if provider == "openrouter" else False,
        "deny_data_collection": deny_data_collection if provider == "openrouter" else False,
        "allow_fallbacks": allow_fallbacks if provider == "openrouter" else False,
        "require_parameters": require_parameters if provider == "openrouter" else False,
        "workspace_save_mode": save_mode,
        "local_workspace_disk_path": (
            local_workspace_disk_path if save_mode == "local_json" else None
        ),
        "chemillusion_server_storage": False,
        "provider_policy": provider_policy,
        "private_structure_mode": private_structure_mode,
        "blocks_external_lookup": blocks_external_lookup,
        "private_structure_mode_claim": claim,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Structure redaction (logs/traces only — never chemistry logic)
# ---------------------------------------------------------------------------

_STRUCTURE_HINT_CHARS = set("=#[]()@/\\")


def redact_structure_text(text: Any) -> Any:
    """Collapse structure-like text to a marker for logs/traces.

    Conservative and fail-safe: a non-string is returned unchanged, and text
    that does not look like a structure is returned unchanged. This exists so a
    debug log or trace never carries a raw SMILES / Molfile / InChI.

    * A Molfile (contains ``M  END``) or an InChI (``InChI=`` prefix) →
      ``[STRUCTURE_REDACTED]``.
    * Otherwise, longer text containing SMILES-ish punctuation →
      ``[POSSIBLE_STRUCTURE_REDACTED]``.
    """
    if not isinstance(text, str) or not text:
        return text
    if "M  END" in text or text.startswith("InChI="):
        return "[STRUCTURE_REDACTED]"
    if len(text) > 12 and any(ch in _STRUCTURE_HINT_CHARS for ch in text):
        return "[POSSIBLE_STRUCTURE_REDACTED]"
    return text


class StructureRedactingLogFilter:
    """A :class:`logging.Filter` that redacts structure-like text in messages.

    Installed on OpenMolClaw's loggers so that even an accidental
    ``logger.info(smiles)`` cannot emit a raw structure. Applies to the rendered
    message and to string args; leaves non-string args untouched.
    """

    def filter(self, record: Any) -> bool:  # pragma: no cover - thin logging glue
        try:
            if isinstance(record.msg, str):
                record.msg = redact_structure_text(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        k: redact_structure_text(v) for k, v in record.args.items()
                    }
                else:
                    record.args = tuple(redact_structure_text(a) for a in record.args)
        except Exception:  # noqa: BLE001 - a log filter must never raise
            pass
        return True


__all__ = [
    "WORKSPACE_SAVE_MODES",
    "coerce_bool",
    "resolve_workspace_save_mode",
    "privacy_warnings",
    "private_structure_mode_claim",
    "describe_privacy",
    "redact_structure_text",
    "StructureRedactingLogFilter",
]
