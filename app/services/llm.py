"""
LLM abstraction.

Chain (guide §5): Ollama (local, primary) → cloud model (only if CLOUD_FALLBACK=true)
→ deterministic MockLLM (only if MOCK_FALLBACK=true). MOCK_LLM=true uses the mock directly.

The rest of the app only ever calls get_llm().complete(system, user). The LLM is asked to
explain verified facts or re-phrase; it is never the source of truth for numbers,
thresholds, identity or precedence. Every call reports tokens so the audit record can
record llm_calls and tokens per question.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.config import settings

log = logging.getLogger(__name__)

NOT_FOUND_TOKEN = "NOT_FOUND"

_STOPWORDS = {
    "what", "is", "the", "for", "of", "a", "an", "to", "in", "on", "and", "or", "my", "i", "am",
    "are", "do", "does", "can", "will", "be", "if", "it", "this", "that", "with", "by", "me",
    "required", "requirement", "minimum", "please", "tell", "about", "how", "much", "many",
    "there", "which", "when", "should", "would", "have", "has",
}


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class BaseLLM:
    name = "base"
    model = "none"

    def complete(self, system: str, user: str, max_tokens: int = 500, temperature: float = 0.0) -> LLMResponse:
        raise NotImplementedError

    def health(self) -> dict:
        return {"provider": self.name, "model": self.model, "status": "unknown"}


# --------------------------------------------------------------------------
# Mock provider — deterministic, parses the structured prompt from prompts.py
# --------------------------------------------------------------------------
class MockLLM(BaseLLM):
    name = "mock"
    model = "mock"

    def complete(self, system: str, user: str, max_tokens: int = 500, temperature: float = 0.0) -> LLMResponse:
        question = _between(user, "QUESTION:", "\n")
        facts = _block(user, "VERIFIED FACTS:")
        evidence = _block(user, "EVIDENCE:")
        parts: list[str] = []
        if facts.strip():
            # Calculated answers: the facts are complete and already cite their rules; do not pad with evidence.
            text = " ".join(line.lstrip("- ").strip() for line in facts.strip().splitlines() if line.strip())
            return LLMResponse(text, "mock", "mock", _estimate_tokens(system + user), _estimate_tokens(text))
        if evidence.strip():
            if not facts.strip() and not _terms_covered(question, evidence):
                text = NOT_FOUND_TOKEN
                return LLMResponse(text, "mock", "mock", _estimate_tokens(system + user), _estimate_tokens(text))
            ranked = sorted(_evidence_items(evidence), key=lambda it: _overlap(question, it[1]), reverse=True)
            for label, snippet in ranked[:2]:
                sentence = _best_sentences(question, snippet, 2)
                if sentence:
                    parts.append(f"{sentence} {label}")
        text = " ".join(parts) if parts else NOT_FOUND_TOKEN
        return LLMResponse(text, "mock", "mock", _estimate_tokens(system + user), _estimate_tokens(text))

    def health(self) -> dict:
        return {"provider": "mock", "model": "mock", "status": "ok"}


def _between(text: str, start: str, end: str) -> str:
    i = text.find(start)
    if i < 0:
        return ""
    i += len(start)
    j = text.find(end, i)
    return text[i:j if j > 0 else None].strip()


def _block(text: str, header: str) -> str:
    i = text.find(header)
    if i < 0:
        return ""
    body = text[i + len(header):]
    m = re.search(r"\n[A-Z][A-Z /]+:\n", body)
    return body[: m.start()] if m else body


def _evidence_items(evidence: str):
    for m in re.finditer(r"(\[S\d+\])\s*\([^)]*\)\s*(.*?)(?=\n\[S\d+\]|\Z)", evidence, flags=re.S):
        yield m.group(1), m.group(2).strip()


def _terms(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z][a-zA-Z\-]{3,}", text.lower()) if t not in _STOPWORDS]


def _overlap(question: str, text: str) -> int:
    tl = text.lower()
    return sum(1 for t in set(_terms(question)) if t.rstrip("s") in tl)


def _best_sentences(question: str, text: str, n: int) -> str:
    first, _, rest = text.partition("\n")
    if rest and not first.rstrip().endswith((".", "!", "?")):
        text = rest
    sentences = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    ranked = sorted(sentences, key=lambda s: _overlap(question, s), reverse=True)
    chosen = [s for s in ranked[:n] if len(s) > 20]
    return " ".join(s for s in sentences if s in chosen).strip()


def _terms_covered(question: str, evidence: str, threshold: float = 0.6) -> bool:
    terms = _terms(question)
    if not terms:
        return True
    ev = evidence.lower()
    hits = sum(1 for t in terms if t.rstrip("s") in ev)
    if hits / len(terms) < threshold:
        return False
    named = [w.strip("?.,!") for w in question.split()[1:] if w[:1].isupper() and len(w) > 3]
    return all(w.lower() in ev for w in named)


# --------------------------------------------------------------------------
# Ollama (native /api/chat) — primary
# --------------------------------------------------------------------------
class OllamaLLM(BaseLLM):
    name = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete(self, system: str, user: str, max_tokens: int = 500, temperature: float = 0.0) -> LLMResponse:
        import httpx

        payload = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        with httpx.Client(timeout=settings.LLM_TIMEOUT_S) as client:
            r = client.post(f"{self.base_url}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
        return LLMResponse(
            text=data["message"]["content"],
            model=self.model,
            provider="ollama",
            input_tokens=int(data.get("prompt_eval_count") or _estimate_tokens(system + user)),
            output_tokens=int(data.get("eval_count") or _estimate_tokens(data["message"]["content"])),
        )

    def health(self) -> dict:
        try:
            import httpx

            with httpx.Client(timeout=4) as client:
                r = client.get(f"{self.base_url}/api/tags")
            models = [m.get("name") for m in r.json().get("models", [])]
            ok = any(self.model == m or self.model.split(":")[0] == str(m).split(":")[0] for m in models)
            return {"provider": "ollama", "model": self.model, "status": "ok" if ok else "model_not_pulled",
                    "available_models": models[:10]}
        except Exception as exc:  # noqa: BLE001
            return {"provider": "ollama", "model": self.model, "status": "unreachable", "detail": str(exc)[:120]}


# --------------------------------------------------------------------------
# Cloud fallbacks
# --------------------------------------------------------------------------
class OpenAICompatibleLLM(BaseLLM):
    name = "cloud-openai"

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url, self.api_key, self.model = base_url.rstrip("/"), api_key, model

    def complete(self, system: str, user: str, max_tokens: int = 500, temperature: float = 0.0) -> LLMResponse:
        import httpx

        payload = {"model": self.model, "temperature": temperature, "max_tokens": max_tokens,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=settings.LLM_TIMEOUT_S) as client:
            r = client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        usage = data.get("usage", {})
        return LLMResponse(data["choices"][0]["message"]["content"], self.model, self.name,
                           int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0)))

    def health(self) -> dict:
        return {"provider": self.name, "model": self.model, "status": "configured" if self.api_key else "missing_key"}


class AnthropicLLM(BaseLLM):
    name = "cloud-anthropic"

    def __init__(self, api_key: str, model: str):
        self.api_key, self.model = api_key, model

    def complete(self, system: str, user: str, max_tokens: int = 500, temperature: float = 0.0) -> LLMResponse:
        import httpx

        payload = {"model": self.model, "max_tokens": max_tokens, "temperature": temperature,
                   "system": system, "messages": [{"role": "user", "content": user}]}
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        with httpx.Client(timeout=settings.LLM_TIMEOUT_S) as client:
            r = client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        usage = data.get("usage", {})
        text = "".join(b.get("text", "") for b in data.get("content", []))
        return LLMResponse(text, self.model, self.name, int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0)))

    def health(self) -> dict:
        return {"provider": self.name, "model": self.model, "status": "configured" if self.api_key else "missing_key"}


# --------------------------------------------------------------------------
# Chain: try each provider in order; record which one answered.
# --------------------------------------------------------------------------
class ChainLLM(BaseLLM):
    def __init__(self, providers: list[BaseLLM]):
        self.providers = providers
        self.name = providers[0].name
        self.model = providers[0].model

    def complete(self, system: str, user: str, max_tokens: int = 500, temperature: float = 0.0) -> LLMResponse:
        last_exc: Exception | None = None
        for p in self.providers:
            try:
                resp = p.complete(system, user, max_tokens=max_tokens, temperature=temperature)
                if p is not self.providers[0]:
                    resp.provider = f"{p.name} (fallback from {self.providers[0].name})"
                return resp
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                log.warning("LLM provider %s failed: %s", p.name, exc)
        raise RuntimeError(f"All LLM providers failed: {last_exc}")

    def health(self) -> dict:
        h = self.providers[0].health()
        h["fallbacks"] = [p.name for p in self.providers[1:]]
        return h


_llm_singleton: BaseLLM | None = None


def get_llm() -> BaseLLM:
    global _llm_singleton
    if _llm_singleton is not None:
        return _llm_singleton
    if settings.MOCK_LLM or settings.LLM_PROVIDER == "mock":
        _llm_singleton = MockLLM()
        return _llm_singleton
    chain: list[BaseLLM] = [OllamaLLM(settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL)]
    if settings.CLOUD_FALLBACK and settings.CLOUD_API_KEY:
        if settings.CLOUD_PROVIDER == "anthropic":
            chain.append(AnthropicLLM(settings.CLOUD_API_KEY, settings.CLOUD_MODEL))
        else:
            chain.append(OpenAICompatibleLLM(settings.CLOUD_BASE_URL, settings.CLOUD_API_KEY, settings.CLOUD_MODEL))
    if settings.MOCK_FALLBACK:
        chain.append(MockLLM())
    _llm_singleton = ChainLLM(chain)
    return _llm_singleton


def reset_llm() -> None:
    """Used by tests/evaluation when the configuration changes."""
    global _llm_singleton
    _llm_singleton = None
