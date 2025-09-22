import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


CONFIG_FILENAME = "config.json"


@dataclass
class LLMConfig:
    """Data container for a single LLM configuration."""

    name: str
    endpoint: str = ""
    api_key: str = ""
    model: str = ""
    system_prompt: str = ""
    user_prompt: str = ""
    response_keys: List[str] = field(default_factory=list)
    destination_fields: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "endpoint": self.endpoint,
            "api_key": self.api_key,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "response_keys": self.response_keys,
            "destination_fields": self.destination_fields,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMConfig":
        return cls(
            name=data.get("name", "Unnamed"),
            endpoint=data.get("endpoint", ""),
            api_key=data.get("api_key", ""),
            model=data.get("model", ""),
            system_prompt=data.get("system_prompt", ""),
            user_prompt=data.get("user_prompt", ""),
            response_keys=list(data.get("response_keys", [])),
            destination_fields=list(data.get("destination_fields", [])),
        )


class ConfigStore:
    """Manages reading and writing LLM config definitions to disk."""

    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or Path(__file__).resolve().parent / CONFIG_FILENAME
        self._data: Dict[str, Any] = {"configs": []}
        self.load()

    @property
    def config_path(self) -> Path:
        return self._config_path

    def load(self) -> None:
        if self._config_path.exists():
            try:
                self._data = json.loads(self._config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                # If file is corrupted, start fresh but keep a backup.
                backup_path = self._config_path.with_suffix(".bak")
                try:
                    self._config_path.replace(backup_path)
                except OSError:
                    pass
                self._data = {"configs": []}
        if "configs" not in self._data or not isinstance(self._data["configs"], list):
            self._data = {"configs": []}
        if not self._data["configs"]:
            self._data["configs"].append(LLMConfig(name="Default").to_dict())
            self.save()

    def save(self) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with self._config_path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2, ensure_ascii=False)

    def list_configs(self) -> List[LLMConfig]:
        return [LLMConfig.from_dict(item) for item in self._data.get("configs", [])]

    def find(self, name: str) -> Optional[LLMConfig]:
        for config in self.list_configs():
            if config.name == name:
                return config
        return None

    def upsert(self, config: LLMConfig) -> None:
        configs = self._data.setdefault("configs", [])
        for idx, existing in enumerate(configs):
            if existing.get("name") == config.name:
                configs[idx] = config.to_dict()
                break
        else:
            configs.append(config.to_dict())
        self.save()

    def delete(self, name: str) -> None:
        configs = self._data.setdefault("configs", [])
        new_configs = [cfg for cfg in configs if cfg.get("name") != name]
        if len(new_configs) != len(configs):
            self._data["configs"] = new_configs
            if not new_configs:
                self._data["configs"] = [LLMConfig(name="Default").to_dict()]
            self.save()

    def ensure_unique_name(self, base_name: str = "Config") -> str:
        existing = {cfg.name for cfg in self.list_configs()}
        if base_name not in existing:
            return base_name
        counter = 1
        while True:
            candidate = f"{base_name} {counter}"
            if candidate not in existing:
                return candidate
            counter += 1
