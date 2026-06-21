from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AssistantConfig:
    rtbdi_base_url: str = "https://www.myrtpos.com/newbdi/"
    rtbdi_username: str | None = None
    rtbdi_password: str | None = None
    rtbdi_storage_state: Path | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    @classmethod
    def from_env(cls) -> "AssistantConfig":
        storage_state = os.getenv("RTBDI_STORAGE_STATE")
        return cls(
            rtbdi_base_url=os.getenv("RTBDI_BASE_URL", cls.rtbdi_base_url),
            rtbdi_username=os.getenv("RTBDI_USERNAME"),
            rtbdi_password=os.getenv("RTBDI_PASSWORD"),
            rtbdi_storage_state=Path(storage_state) if storage_state else None,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", cls.openai_model),
        )

    def require_rtbdi_credentials(self) -> tuple[str, str]:
        if not self.rtbdi_username or not self.rtbdi_password:
            raise RuntimeError("RTBDI_USERNAME and RTBDI_PASSWORD must be set")
        return self.rtbdi_username, self.rtbdi_password

    def require_openai_key(self) -> str:
        if not self.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY must be set")
        return self.openai_api_key
