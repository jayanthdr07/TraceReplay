# Recording engine for capturing LLM interactions into persistent fixtures.

from __future__ import annotations

import uuid
from pathlib import Path

from tracereplay.config import TraceReplayConfig, get_config
from tracereplay.exceptions import RecordingError
from tracereplay.matcher.normalizer import RequestNormalizer
from tracereplay.models import Interaction, RequestPayload, ResponsePayload, SessionRecord
from tracereplay.sanitizer import Sanitizer
from tracereplay.storage.json_storage import JsonStorageEngine


class Recorder:
    # Records LLM interactions during a session and flushes them to persistent storage.

    def __init__(
        self,
        session_name: str,
        storage: JsonStorageEngine,
        sanitizer: Sanitizer,
        normalizer: RequestNormalizer | None = None,
        config: TraceReplayConfig | None = None,
    ) -> None:
        self.session_name = session_name
        self.storage = storage
        self.sanitizer = sanitizer
        self.config = config or get_config()
        self.normalizer = normalizer or RequestNormalizer(config=self.config)
        self.session_id = f"sess_{uuid.uuid4().hex[:12]}"
        self.interactions: list[Interaction] = []
        self._interaction_count = 0

    @property
    def session_record(self) -> SessionRecord:
        # Construct the immutable SessionRecord sanpshot.
        return SessionRecord(
            session_id=self.session_id,
            name=self.session_name,
            interactions=list(self.interactions),
        )

    def record_interaction(
        self,
        request: RequestPayload,
        response: ResponsePayload,
        duration_ms: float = 0.0,
    ) -> Interaction:
        # Sanitize, normalize, and record an LLM interaction.
        clean_request = self.sanitizer.sanitize_request(request)
        clean_response = self.sanitizer.sanitize_response(response)

        interaction = Interaction(
            session_id=self.session_id,
            index=self._interaction_count,
            request=clean_request,
            response=clean_response,
            duration_ms=duration_ms,
        )

        self.interactions.append(interaction)
        self._interaction_count += 1
        return interaction

    def flush(self) -> Path:
        # Write recorded session to storage.
        if not self.interactions:
            raise RecordingError(f"No interactions recorded for session: '{self.session_name}")
        return self.storage.save(self.session_record)
