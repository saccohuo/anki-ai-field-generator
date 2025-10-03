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
    image_prompt_mappings: List[str] = field(default_factory=list)
    image_api_key: str = ""
    image_endpoint: str = ""
    image_model: str = ""
    audio_prompt_mappings: List[str] = field(default_factory=list)
    audio_api_key: str = ""
    audio_endpoint: str = ""
    audio_model: str = ""
    audio_voice: str = ""
    audio_format: str = ""
    text_mapping_entries: List[Dict[str, Any]] = field(default_factory=list)
    enable_text_generation: bool = True
    enable_image_generation: bool = True
    enable_audio_generation: bool = True
    retry_limit: int = 3
    retry_delay: float = 5.0

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
            "image_prompt_mappings": self.image_prompt_mappings,
            "image_api_key": self.image_api_key,
            "image_endpoint": self.image_endpoint,
            "image_model": self.image_model,
            "audio_prompt_mappings": self.audio_prompt_mappings,
            "audio_api_key": self.audio_api_key,
            "audio_endpoint": self.audio_endpoint,
            "audio_model": self.audio_model,
            "audio_voice": self.audio_voice,
            "audio_format": self.audio_format,
            "text_mapping_entries": self.text_mapping_entries,
            "enable_text_generation": self.enable_text_generation,
            "enable_image_generation": self.enable_image_generation,
            "enable_audio_generation": self.enable_audio_generation,
            "retry_limit": self.retry_limit,
            "retry_delay": self.retry_delay,
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
            image_prompt_mappings=list(data.get("image_prompt_mappings", [])),
            image_api_key=data.get("image_api_key", ""),
            image_endpoint=data.get("image_endpoint", ""),
            image_model=data.get("image_model", ""),
            audio_prompt_mappings=list(data.get("audio_prompt_mappings", [])),
            audio_api_key=data.get("audio_api_key", ""),
            audio_endpoint=data.get("audio_endpoint", ""),
            audio_model=data.get("audio_model", ""),
            audio_voice=data.get("audio_voice", ""),
            audio_format=data.get("audio_format", ""),
            text_mapping_entries=list(data.get("text_mapping_entries", [])),
            enable_text_generation=data.get("enable_text_generation", True),
            enable_image_generation=data.get("enable_image_generation", True),
            enable_audio_generation=data.get("enable_audio_generation", True),
            retry_limit=int(data.get("retry_limit", 3)),
            retry_delay=float(data.get("retry_delay", 5.0)),
        )


class ConfigStore:
    """Manages reading and writing LLM config definitions to disk."""

    def __init__(self, config_path: Optional[Path] = None):
        base_path = Path(__file__).resolve().parent
        if config_path is not None:
            self._config_path = config_path
            self._using_example = False
        else:
            self._config_path = base_path / CONFIG_FILENAME
            self._using_example = not self._config_path.exists()
            if self._using_example:
                example_path = base_path / "config.example.json"
                if example_path.exists():
                    self._config_path = example_path
        self._base_path = base_path
        self._default_path = base_path / CONFIG_FILENAME
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
        self._using_example = self._config_path.name != CONFIG_FILENAME

    def save(self) -> None:
        target_path = self._config_path
        if self._config_path.name != CONFIG_FILENAME:
            target_path = self._base_path / CONFIG_FILENAME
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2, ensure_ascii=False)
        self._config_path = target_path
        self._using_example = False

    @property
    def using_example(self) -> bool:
        return self._using_example

    @property
    def default_config_path(self) -> Path:
        return self._default_path

    def save_as(self, target_path: Path) -> None:
        self._config_path = target_path
        self._using_example = False
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
