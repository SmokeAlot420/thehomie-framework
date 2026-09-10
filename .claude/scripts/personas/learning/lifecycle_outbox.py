"""Durable session-end delivery independent of the learning SQLite stores.

An end hook saves a bounded, redacted replay envelope before consulting the
learning DB. Session deletion can therefore proceed through a DB outage. The
normal learner discovery replays pending envelopes and deletes one only after
its cognitive cycle is durable. Core source keys make crash/retry idempotent.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import stat
import tempfile
from pathlib import Path

from .models import LearningError, canonical_json

_LOG = logging.getLogger(__name__)
_LIMIT = 16000
_FIELDS = frozenset(
    {
        "version",
        "persona_id",
        "session_id",
        "surface",
        "reason",
        "transcript",
        "transcript_hash",
        "transcript_truncated",
    }
)
_FILE = re.compile(r"^[0-9a-f]{64}\.json$")


def _hash(value) -> str:
    # Same full-transcript identity as the original lifecycle capture hook.
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _directory(service) -> Path:
    root = Path(os.path.abspath(service.target.state_dir))
    directory = root / "learning-lifecycle-outbox"
    for path in (directory, *directory.parents):
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise LearningError("lifecycle outbox cannot traverse links")
    return directory


def _validate(service, payload: dict, *, identifier: str | None = None) -> str:
    if not isinstance(payload, dict) or set(payload) != _FIELDS or payload["version"] != 1:
        raise LearningError("invalid lifecycle replay envelope")
    if payload["persona_id"] != service.target.persona_id:
        raise LearningError("lifecycle replay belongs to another persona")
    for key, limit in (
        ("session_id", 1024),
        ("surface", 100),
        ("reason", 256),
        ("transcript", _LIMIT),
    ):
        value = payload[key]
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise LearningError(f"invalid lifecycle replay {key}")
    if (
        not isinstance(payload["transcript_truncated"], bool)
        or not isinstance(payload["transcript_hash"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", payload["transcript_hash"])
    ):
        raise LearningError("invalid lifecycle replay provenance")
    expected = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
    if identifier is not None and identifier != expected:
        raise LearningError("lifecycle replay content changed")
    return expected


def _read(service, path: Path) -> dict:
    if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
        raise LearningError("lifecycle outbox entry cannot be a link")
    if not _FILE.fullmatch(path.name) or path.stat().st_size > 100000:
        raise LearningError("invalid lifecycle outbox entry")
    payload = json.loads(path.read_text(encoding="utf-8"))
    _validate(service, payload, identifier=path.stem)
    return payload


def _make_payload(
    service, *, persona_id: str, session_id: str, surface: str, transcript: str, reason: str
) -> dict:
    from security.redact import redact_sensitive_text

    if persona_id != service.target.persona_id:
        raise LearningError("session debrief service belongs to another persona")
    original = str(transcript).strip()
    payload = {
        "version": 1,
        "persona_id": persona_id,
        "session_id": redact_sensitive_text(str(session_id)),
        "surface": redact_sensitive_text(str(surface)),
        "reason": redact_sensitive_text(str(reason)),
        "transcript": redact_sensitive_text(original)[:_LIMIT],
        "transcript_hash": _hash(original),
        "transcript_truncated": len(original) > _LIMIT,
    }
    _validate(service, payload)
    return payload


def persist_session_debrief(service, **values) -> Path:
    """Write/fsync an immutable replay record before any learning DB access."""
    payload = _make_payload(service, **values)
    identifier = _validate(service, payload)
    directory = _directory(service)
    directory.mkdir(parents=True, exist_ok=True)
    _directory(service)
    path = directory / f"{identifier}.json"
    if path.exists():
        _read(service, path)
        return path
    descriptor, filename = tempfile.mkstemp(prefix=".outbox-", dir=directory)
    temporary = Path(filename)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(canonical_json(payload))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            # Both publish-without-overwrite paths leave concurrent hooks with
            # one complete file, never a partially written JSON envelope.
            if os.name == "nt":
                os.rename(temporary, path)
            else:
                os.link(temporary, path)
        except FileExistsError:
            _read(service, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def _ingest_payload(service, payload: dict) -> dict:
    _validate(service, payload)
    if not service.enabled():
        return {"status": "disabled"}
    revision = payload["transcript_hash"]
    origin = f"{payload['session_id']}:{revision}"
    experience = service.capture_experience(
        origin,
        payload["surface"],
        payload["transcript"],
        metadata={
            "capture_scope": "host",
            "reason": payload["reason"],
            "transcript_hash": revision,
            "transcript_truncated": payload["transcript_truncated"],
        },
    )
    observation = service.record_observation(
        experience["id"],
        {
            "quality": "direct",
            "status": "partial",
            "domain_outcome_observed": False,
            "evidence": {
                "kind": "session_transcript",
                "text": payload["transcript"],
                "transcript_hash": revision,
                "reason": payload["reason"],
            },
        },
        source_key=revision,
    )
    cycle = service.enqueue_cognitive_cycle(
        "reflect",
        origin,
        [experience["id"], observation["id"]],
        experience_id=experience["id"],
        metadata={"surface": payload["surface"], "reason": payload["reason"], "host_event": True},
    )
    return {
        "status": "queued",
        "cognitive_cycle_id": cycle["id"],
        "experience_id": experience["id"],
    }


def deliver_pending(service, path: Path) -> dict:
    """Ingest exactly the saved envelope, retaining it on pause or DB failure."""
    directory = _directory(service)
    if path.parent != directory:
        raise LearningError("lifecycle replay escaped persona outbox")
    payload = _read(service, path)
    try:
        receipt = _ingest_payload(service, payload)
    except Exception as exc:
        _LOG.warning("session debrief retained in lifecycle outbox: %s", type(exc).__name__)
        return {
            "status": "deferred",
            "outbox_id": path.stem,
            "reason": "learning_unavailable",
            "error_type": type(exc).__name__,
        }
    if receipt["status"] != "queued":
        return receipt | {"outbox_id": path.stem}
    # The cycle is committed. A failed acknowledgement removal is safe to retry.
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        _LOG.warning("lifecycle outbox acknowledgement retained: %s", type(exc).__name__)
    return receipt


def enqueue_session_debrief(service, **values) -> dict:
    try:
        path = persist_session_debrief(service, **values)
    except OSError:
        # If the separate outbox filesystem is unavailable, a committed DB cycle
        # is still a durable delivery. Only losing both destinations blocks clear.
        try:
            receipt = _ingest_payload(service, _make_payload(service, **values))
            if receipt["status"] == "queued":
                return receipt
        except Exception:
            pass
        raise LearningError("session debrief could not be retained; session must remain") from None
    return deliver_pending(service, path)


def replay_pending(service) -> dict:
    """Replay bounded pending end hooks; malformed entries stay visibly rejected."""
    directory = _directory(service)
    result = {"delivered": 0, "pending": 0, "rejected": 0}
    if not directory.exists():
        return result
    for path in sorted(directory.glob("*.json")):
        try:
            receipt = deliver_pending(service, path)
            result["delivered" if receipt["status"] == "queued" else "pending"] += 1
        except (LearningError, OSError, ValueError) as exc:
            result["rejected"] += 1
            _LOG.warning("lifecycle replay rejected: %s", type(exc).__name__)
    return result
