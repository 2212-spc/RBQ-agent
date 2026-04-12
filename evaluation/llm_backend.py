from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
from urllib import error as urllib_error
from urllib import request as urllib_request


ROOT = Path(__file__).resolve().parents[1]


@dataclass(slots=True)
class LLMConfig:
    api_key: str
    api_base: str
    model: str
    timeout_seconds: int = 45
    retry_attempts: int = 2
    max_calls: int = 6
    cache_dir: Path = ROOT / "outputs" / "llm_cache"


def _load_llm_config_from_file(path: Path) -> LLMConfig | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    api_key = str(payload.get("api_key", "")).strip()
    api_base = str(payload.get("api_base", "")).strip()
    model = str(payload.get("model", "")).strip()
    if not api_key or not api_base:
        return None
    timeout_seconds = int(payload.get("timeout_seconds", os.environ.get("HDRBENCH_LLM_TIMEOUT_SECONDS", "45")))
    retry_attempts = int(payload.get("retry_attempts", os.environ.get("HDRBENCH_LLM_RETRIES", "2")))
    max_calls = int(payload.get("max_calls", os.environ.get("HDRBENCH_MAX_LLM_CALLS", "4")))
    cache_dir = Path(str(payload.get("cache_dir", os.environ.get("HDRBENCH_LLM_CACHE_DIR", str(ROOT / "outputs" / "llm_cache")))))
    return LLMConfig(
        api_key=api_key,
        api_base=api_base.rstrip("/"),
        model=model,
        timeout_seconds=timeout_seconds,
        retry_attempts=retry_attempts,
        max_calls=max_calls,
        cache_dir=cache_dir,
    )


def _load_llm_config_from_env() -> LLMConfig | None:
    api_key = os.environ.get("HDRBENCH_API_KEY", "").strip()
    api_base = os.environ.get("HDRBENCH_API_BASE", "").strip()
    model = os.environ.get("HDRBENCH_MODEL", "").strip()
    timeout_seconds = int(os.environ.get("HDRBENCH_LLM_TIMEOUT_SECONDS", "45"))
    retry_attempts = int(os.environ.get("HDRBENCH_LLM_RETRIES", "2"))
    max_calls = int(os.environ.get("HDRBENCH_MAX_LLM_CALLS", "4"))
    cache_dir = Path(os.environ.get("HDRBENCH_LLM_CACHE_DIR", str(ROOT / "outputs" / "llm_cache")))
    if not api_key or not api_base:
        explicit_path = os.environ.get("HDRBENCH_LLM_CONFIG", "").strip()
        candidate_paths = []
        if explicit_path:
            candidate_paths.append(Path(explicit_path))
        candidate_paths.append(ROOT / "outputs" / "local_llm_config.json")
        candidate_paths.append(ROOT / ".hdrbench_llm_config.json")
        for candidate in candidate_paths:
            config = _load_llm_config_from_file(candidate)
            if config is not None:
                return config
        return None
    return LLMConfig(
        api_key=api_key,
        api_base=api_base.rstrip("/"),
        model=model,
        timeout_seconds=timeout_seconds,
        retry_attempts=retry_attempts,
        max_calls=max_calls,
        cache_dir=cache_dir,
    )


def _http_json(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any] | None = None,
    timeout_seconds: int = 60,
) -> Dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib_request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _resolve_llm_model(config: LLMConfig) -> str:
    if config.model:
        return config.model
    headers = {"Authorization": f"Bearer {config.api_key}"}
    try:
        payload = _http_json(
            f"{config.api_base}/v1/models",
            headers=headers,
            payload=None,
            timeout_seconds=config.timeout_seconds,
        )
        models = payload.get("data", [])
        if models:
            return str(models[0]["id"])
    except Exception:
        pass
    return "gpt-4.1-mini"


def extract_json_object(text: str) -> Dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


class LLMBackendSession:
    def __init__(self, config: LLMConfig, namespace: str) -> None:
        self.config = config
        self.namespace = namespace
        self.calls_used = 0
        self.token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    @property
    def max_calls(self) -> int:
        return self.config.max_calls

    @property
    def remaining_calls(self) -> int:
        return max(self.config.max_calls - self.calls_used, 0)

    def _consume_budget(self) -> None:
        if self.calls_used >= self.config.max_calls:
            raise RuntimeError(f"llm_call_budget_exhausted: {self.config.max_calls}")
        self.calls_used += 1

    def _merge_usage(self, response: Dict[str, Any]) -> None:
        usage = response.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
        completion_tokens = int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)
        total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)
        self.token_usage["prompt_tokens"] += prompt_tokens
        self.token_usage["completion_tokens"] += completion_tokens
        self.token_usage["total_tokens"] += total_tokens

    def _cache_path(self, payload: Dict[str, Any], response_kind: str) -> Path:
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_key = hashlib.sha256(
            json.dumps(
                {
                    "namespace": self.namespace,
                    "response_kind": response_kind,
                    "payload": payload,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return self.config.cache_dir / f"{cache_key}.json"

    def chat_text(self, system_prompt: str, user_prompt: str, *, cache_namespace: str = "") -> str:
        self._consume_budget()
        model = _resolve_llm_model(self.config)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
        }
        cache_path = self._cache_path(
            {"cache_namespace": cache_namespace, "payload": payload},
            response_kind="text",
        )
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                return str(cached["content"])
            except Exception:
                pass

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(self.config.retry_attempts):
            try:
                response = _http_json(
                    f"{self.config.api_base}/v1/chat/completions",
                    headers=headers,
                    payload=payload,
                    timeout_seconds=self.config.timeout_seconds,
                )
                self._merge_usage(response)
                content = str(response["choices"][0]["message"]["content"])
                cache_path.write_text(json.dumps({"content": content}, ensure_ascii=False, indent=2), encoding="utf-8")
                return content
            except Exception as exc:
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"llm_request_failed: {last_error}")

    def chat_json(self, system_prompt: str, user_prompt: str, *, cache_namespace: str = "") -> Dict[str, Any]:
        self._consume_budget()
        model = _resolve_llm_model(self.config)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }
        cache_path = self._cache_path(
            {"cache_namespace": cache_namespace, "payload": payload},
            response_kind="json",
        )
        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        response: Dict[str, Any] | None = None
        for attempt in range(self.config.retry_attempts):
            try:
                response = _http_json(
                    f"{self.config.api_base}/v1/chat/completions",
                    headers=headers,
                    payload=payload,
                    timeout_seconds=self.config.timeout_seconds,
                )
                self._merge_usage(response)
                break
            except Exception as exc:
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        if response is None:
            try:
                payload.pop("response_format", None)
                for attempt in range(self.config.retry_attempts):
                    try:
                        response = _http_json(
                            f"{self.config.api_base}/v1/chat/completions",
                            headers=headers,
                            payload=payload,
                            timeout_seconds=self.config.timeout_seconds,
                        )
                        self._merge_usage(response)
                        break
                    except Exception as exc:
                        last_error = exc
                        time.sleep(1.5 * (attempt + 1))
            except urllib_error.URLError:
                response = None
        if response is None:
            raise RuntimeError(f"llm_request_failed: {last_error}")
        parsed = extract_json_object(str(response["choices"][0]["message"]["content"]))
        if parsed is None:
            raise RuntimeError("LLM did not return valid JSON")
        cache_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        return parsed


def create_llm_session(namespace: str) -> LLMBackendSession | None:
    config = _load_llm_config_from_env()
    if config is None:
        return None
    return LLMBackendSession(config=config, namespace=namespace)
