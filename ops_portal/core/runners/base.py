from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class BaseRunner:
    """
    Base interface for all runners (Grafana, Harness, SPLOC, Copilot, etc.)
    """
    integration: str
    user_key: str

    def run(self, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError("Runner must implement run()")
