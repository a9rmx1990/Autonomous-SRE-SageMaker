"""AgentCore Memory hooks for incident knowledge management.

Before invocation: retrieves relevant historical incidents.
After invocation: stores incident summary and post-mortem.

Falls back to in-memory storage when AgentCore is unavailable.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from ..config import get_settings
from ..models import MemoryEntry

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages incident memory using AgentCore Memory or local fallback.

    Stores incident summaries, root causes, remediation outcomes,
    and post-mortems so future investigations benefit from
    historical context.
    """

    def __init__(self) -> None:
        self._local_store: list[MemoryEntry] = []
        self._agentcore_client = None
        self._init_agentcore()

    def _init_agentcore(self) -> None:
        settings = get_settings()
        if not settings.agentcore_memory_id:
            logger.info("AgentCore Memory ID not configured; using local fallback.")
            return
        try:
            from bedrock_agentcore.memory import MemoryClient
            self._agentcore_client = MemoryClient(
                memory_id=settings.agentcore_memory_id,
                region_name=settings.aws_region,
            )
            logger.info("AgentCore Memory client initialized (memory_id=%s).", settings.agentcore_memory_id)
        except ImportError:
            logger.warning("bedrock-agentcore SDK not installed; using local fallback.")
        except Exception as exc:
            logger.warning("AgentCore Memory init failed: %s. Using local fallback.", exc)

    # ── Retrieval (before invocation) ────────────────────────────────────

    async def retrieve_context(self, service: str, incident_description: str) -> list[dict[str, Any]]:
        """Retrieve relevant historical incidents for context."""
        if self._agentcore_client:
            try:
                results = self._agentcore_client.retrieve(
                    query=f"incidents for {service}: {incident_description}",
                    retrieval_type="SEMANTIC",
                    max_results=5,
                )
                return [
                    {"content": r.get("content", {}), "score": r.get("score", 0)}
                    for r in results.get("results", [])
                ]
            except Exception as exc:
                logger.warning("AgentCore retrieval failed: %s", exc)

        # Local fallback: simple keyword matching
        matches = []
        for entry in self._local_store:
            content_str = json.dumps(entry.content).lower()
            if service.lower() in content_str:
                matches.append({"content": entry.content, "score": 0.8})
        return matches[:5]

    # ── Storage (after invocation) ───────────────────────────────────────

    async def store_incident(
        self,
        incident_id: str,
        service: str,
        summary: str,
        root_cause: str,
        remediation: str,
        verification_result: str,
        metrics: dict[str, Any] | None = None,
        lessons_learned: str = "",
    ) -> MemoryEntry:
        """Store incident context as a post-mortem memory entry."""
        content = {
            "incident_id": incident_id,
            "service": service,
            "summary": summary,
            "root_cause": root_cause,
            "remediation": remediation,
            "verification_result": verification_result,
            "metrics": metrics or {},
            "lessons_learned": lessons_learned,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        entry = MemoryEntry(
            incident_id=incident_id,
            category="incident_postmortem",
            content=content,
            tags=[service, "postmortem", "incident"],
        )

        if self._agentcore_client:
            try:
                self._agentcore_client.store(
                    content=json.dumps(content),
                    content_type="incident_postmortem",
                    metadata={"service": service, "incident_id": incident_id},
                )
                logger.info("Stored incident %s in AgentCore Memory.", incident_id)
            except Exception as exc:
                logger.warning("AgentCore store failed: %s. Stored locally.", exc)
                self._local_store.append(entry)
        else:
            self._local_store.append(entry)
            logger.info("Stored incident %s in local memory.", incident_id)

        return entry

    async def store_preference(self, key: str, value: Any) -> None:
        """Store an engineer preference."""
        entry = MemoryEntry(
            incident_id="preferences",
            category="user_preference",
            content={"key": key, "value": value},
            tags=["preference"],
        )
        if self._agentcore_client:
            try:
                self._agentcore_client.store(
                    content=json.dumps({"key": key, "value": value}),
                    content_type="USER_PREFERENCE",
                )
            except Exception as exc:
                logger.warning("Preference store failed: %s", exc)
                self._local_store.append(entry)
        else:
            self._local_store.append(entry)

    # ── Query ────────────────────────────────────────────────────────────

    def get_all_entries(self) -> list[MemoryEntry]:
        return list(self._local_store)

    def get_entries_for_service(self, service: str) -> list[MemoryEntry]:
        return [e for e in self._local_store if service.lower() in json.dumps(e.content).lower()]
