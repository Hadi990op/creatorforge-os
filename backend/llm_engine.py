"""
CreatorForge OS — Multi-Provider LLM Engine
=============================================
Supports multiple AI providers with automatic failover:
  1. User-configured providers (Groq, OpenRouter, Google Gemini, etc.)
  2. LLM7.io free tier (no key needed — gemma3:27b, codestral-latest)
  3. Rule-based fallback (always works, never fails)

When a provider hits rate limits (429) or errors, it automatically
falls through to the next provider in the chain.

All providers use OpenAI-compatible chat completions API.
"""
import os
import json
import time
import asyncio
from typing import Optional
from dataclasses import dataclass, field

import httpx

# ═══════════════════════════════════════════════════════════════
#  Provider Configuration
# ═══════════════════════════════════════════════════════════════

@dataclass
class LLMProvider:
    name: str
    base_url: str
    api_key: str
    models: list   # ordered list of model IDs to try
    needs_key: bool = True
    enabled: bool = True
    # Runtime state
    _rate_limited_until: float = field(default=0, repr=False)
    _total_calls: int = field(default=0, repr=False)
    _total_errors: int = field(default=0, repr=False)
    _last_error: str = field(default="", repr=False)


def _load_providers() -> list:
    """Load all configured providers, ordered by priority."""
    providers = []

    # ── 1. User-configured providers from keys file ──
    keys_file = os.path.join(os.path.dirname(__file__), ".llm_keys")
    user_keys = {}
    if os.path.exists(keys_file):
        with open(keys_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    user_keys[k.strip().upper()] = v.strip()

    # Groq — free, no credit card, fast LPU inference
    groq_key = user_keys.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    if groq_key:
        providers.append(LLMProvider(
            name="groq",
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key,
            models=[
                "llama-3.3-70b-versatile",
                "llama-4-maverick-17b-128e-instruct",
                "moonshotai/kimi-k2-instruct",
            ],
        ))

    # Google Gemini — free, no credit card
    gemini_key = user_keys.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    if gemini_key:
        providers.append(LLMProvider(
            name="gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key=gemini_key,
            models=["gemini-2.5-flash", "gemini-2.0-flash"],
        ))

    # OpenRouter — has free models, needs $10 one-time topup for some
    openrouter_key = user_keys.get("OPENROUTER_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))
    if openrouter_key:
        providers.append(LLMProvider(
            name="openrouter",
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_key,
            models=[
                "tencent/hy3:free",
                "nvidia/nemotron-3-ultra-550b-a55b:free",
                "meta-llama/llama-3.3-70b-instruct:free",
                "deepseek/deepseek-r1:free",
            ],
        ))

    # Cerebras — free, no credit card, super fast
    cerebras_key = user_keys.get("CEREBRAS_API_KEY", os.environ.get("CEREBRAS_API_KEY", ""))
    if cerebras_key:
        providers.append(LLMProvider(
            name="cerebras",
            base_url="https://api.cerebras.ai/v1",
            api_key=cerebras_key,
            models=["llama3.1-70b", "gpt-oss-120b"],
        ))

    # Mistral — free, no credit card
    mistral_key = user_keys.get("MISTRAL_API_KEY", os.environ.get("MISTRAL_API_KEY", ""))
    if mistral_key:
        providers.append(LLMProvider(
            name="mistral",
            base_url="https://api.mistral.ai/v1",
            api_key=mistral_key,
            models=["mistral-medium-3-5-128b", "open-mixtral-8x7b"],
        ))

    # ── 2. LLM7.io free tier (no key needed) — always available ──
    providers.append(LLMProvider(
        name="llm7-free",
        base_url="https://api.llm7.io/v1",
        api_key="free",
        models=["gemma3:27b", "codestral-latest"],
        needs_key=False,
    ))

    return providers


# ═══════════════════════════════════════════════════════════════
#  Provider Registry
# ═══════════════════════════════════════════════════════════════

_PROVIDERS: list = []
_INITIALIZED = False


def get_providers() -> list:
    global _PROVIDERS, _INITIALIZED
    if not _INITIALIZED:
        _PROVIDERS = _load_providers()
        _INITIALIZED = True
    return _PROVIDERS


def reload_providers():
    """Reload providers from config file — call after user adds new keys."""
    global _PROVIDERS, _INITIALIZED
    _PROVIDERS = _load_providers()
    _INITIALIZED = True
    return _PROVIDERS


def has_any_llm() -> bool:
    """Check if any provider is available (including free tier)."""
    return len(get_providers()) > 0


def get_provider_status() -> list:
    """Get status of all providers for UI display."""
    status = []
    for p in get_providers():
        status.append({
            "name": p.name,
            "models": p.models,
            "needs_key": p.needs_key,
            "enabled": p.enabled,
            "is_rate_limited": time.time() < p._rate_limited_until,
            "rate_limit_expires_in": max(0, int(p._rate_limited_until - time.time())),
            "total_calls": p._total_calls,
            "total_errors": p._total_errors,
            "last_error": p._last_error,
        })
    return status


def add_provider_key(provider_name: str, api_key: str) -> dict:
    """Add or update a provider API key. Saves to .llm_keys file."""
    keys_file = os.path.join(os.path.dirname(__file__), ".llm_keys")
    user_keys = {}
    if os.path.exists(keys_file):
        with open(keys_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    user_keys[k.strip().upper()] = v.strip()

    key_map = {
        "groq": "GROQ_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "cerebras": "CEREBRAS_API_KEY",
        "mistral": "MISTRAL_API_KEY",
    }
    env_key = key_map.get(provider_name.lower())
    if not env_key:
        return {"error": f"Unknown provider: {provider_name}"}

    user_keys[env_key] = api_key.strip()

    with open(keys_file, "w") as f:
        f.write("# CreatorForge OS — LLM Provider API Keys\n")
        f.write(f"# Updated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for k, v in user_keys.items():
            f.write(f"{k}={v}\n")
    os.chmod(keys_file, 0o600)

    reload_providers()
    return {"status": "added", "provider": provider_name, "key_set": env_key}


def remove_provider_key(provider_name: str) -> dict:
    """Remove a provider's API key."""
    keys_file = os.path.join(os.path.dirname(__file__), ".llm_keys")
    key_map = {
        "groq": "GROQ_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "cerebras": "CEREBRAS_API_KEY",
        "mistral": "MISTRAL_API_KEY",
    }
    env_key = key_map.get(provider_name.lower())
    if not env_key:
        return {"error": f"Unknown provider: {provider_name}"}

    user_keys = {}
    if os.path.exists(keys_file):
        with open(keys_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    user_keys[k.strip().upper()] = v.strip()

    if env_key in user_keys:
        del user_keys[env_key]
        with open(keys_file, "w") as f:
            f.write("# CreatorForge OS — LLM Provider API Keys\n\n")
            for k, v in user_keys.items():
                f.write(f"{k}={v}\n")
        os.chmod(keys_file, 0o600)
        reload_providers()
        return {"status": "removed", "provider": provider_name}
    return {"status": "not_found", "provider": provider_name}


# ═══════════════════════════════════════════════════════════════
#  Core LLM Call with Automatic Failover
# ═══════════════════════════════════════════════════════════════

async def llm_chat(
    prompt: str,
    system: str = "",
    max_tokens: int = 800,
    temperature: float = 0.7,
    json_mode: bool = False,
) -> tuple:
    """
    Call LLM with automatic provider failover.
    Returns (text_response, provider_name_used).
    Falls through all providers; if all fail, returns ("", "fallback").
    """
    providers = get_providers()

    for provider in providers:
        if not provider.enabled:
            continue
        if time.time() < provider._rate_limited_until:
            continue  # skip rate-limited provider

        for model in provider.models:
            try:
                result = await _call_provider(
                    provider, model, prompt, system,
                    max_tokens, temperature, json_mode
                )
                if result:
                    provider._total_calls += 1
                    return result, provider.name
            except RateLimitError as e:
                provider._total_errors += 1
                provider._last_error = str(e)
                # Rate limited — cool down for 60 seconds
                provider._rate_limited_until = time.time() + 60
                print(f"[LLM] {provider.name}/{model} rate limited, trying next provider...")
                break  # try next provider, not next model
            except ProviderError as e:
                provider._total_errors += 1
                provider._last_error = str(e)
                print(f"[LLM] {provider.name}/{model} error: {e}, trying next model...")
                continue  # try next model in same provider
            except Exception as e:
                provider._total_errors += 1
                provider._last_error = str(e)
                print(f"[LLM] {provider.name}/{model} unexpected error: {e}")
                continue

    return "", "fallback"


async def llm_chat_json(
    prompt: str,
    system: str = "",
    max_tokens: int = 800,
) -> Optional[dict]:
    """
    Call LLM and parse JSON from the response.
    Returns dict or None if parsing fails.
    """
    text, provider = await llm_chat(
        prompt, system=system, max_tokens=max_tokens,
        temperature=0.3, json_mode=True
    )
    if not text:
        return None
    return _extract_json(text)


async def llm_chat_json_list(
    prompt: str,
    system: str = "",
    max_tokens: int = 800,
) -> Optional[list]:
    """Call LLM and parse a JSON array from the response."""
    text, provider = await llm_chat(
        prompt, system=system, max_tokens=max_tokens,
        temperature=0.3, json_mode=True
    )
    if not text:
        return None
    return _extract_json_list(text)


def _extract_json(text: str) -> Optional[dict]:
    """Extract a JSON object from LLM response text."""
    import re
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from markdown code blocks
    code_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except json.JSONDecodeError:
            pass
    # Try finding any JSON object in the text
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return None


def _extract_json_list(text: str) -> Optional[list]:
    """Extract a JSON array from LLM response text."""
    import re
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            # Maybe it's wrapped
            for v in result.values():
                if isinstance(v, list):
                    return v
    except json.JSONDecodeError:
        pass
    code_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', text, re.DOTALL)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except json.JSONDecodeError:
            pass
    json_match = re.search(r'\[.*\]', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return None


# ═══════════════════════════════════════════════════════════════
#  Provider API Call
# ═══════════════════════════════════════════════════════════════

class RateLimitError(Exception):
    pass


class ProviderError(Exception):
    pass


async def _call_provider(
    provider: LLMProvider,
    model: str,
    prompt: str,
    system: str,
    max_tokens: int,
    temperature: float,
    json_mode: bool,
) -> str:
    """Call a single provider's API. Raises on error."""
    headers = {"Content-Type": "application/json"}
    if provider.needs_key and provider.api_key and provider.api_key != "free":
        headers["Authorization"] = f"Bearer {provider.api_key}"
    elif provider.name == "gemini":
        # Gemini uses API key as query param
        pass

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    # Some providers support JSON response format
    if json_mode and provider.name in ("groq", "openrouter", "gemini", "cerebras"):
        payload["response_format"] = {"type": "json_object"}

    url = f"{provider.base_url}/chat/completions"

    # Gemini uses a different URL pattern when using OpenAI compat
    if provider.name == "gemini":
        url = f"{provider.base_url}/chat/completions"
        headers["x-goog-api-key"] = provider.api_key

    timeout = httpx.Timeout(30.0, connect=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=payload)

    if resp.status_code == 429:
        raise RateLimitError(f"Rate limited on {provider.name}/{model}")
    if resp.status_code == 401:
        raise ProviderError(f"Auth failed on {provider.name}")
    if resp.status_code == 404:
        raise ProviderError(f"Model {model} not found on {provider.name}")
    if resp.status_code >= 500:
        raise ProviderError(f"Server error {resp.status_code} on {provider.name}")
    if resp.status_code != 200:
        raise ProviderError(f"HTTP {resp.status_code} on {provider.name}: {resp.text[:200]}")

    data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        raise ProviderError(f"No choices in response from {provider.name}")

    content = choices[0].get("message", {}).get("content", "")
    if not content:
        raise ProviderError(f"Empty content from {provider.name}/{model}")

    return content


# ═══════════════════════════════════════════════════════════════
#  Backward Compatibility
# ═══════════════════════════════════════════════════════════════

# For backward compat with old code
HAS_LLM = True  # always true — at minimum LLM7 free tier works


async def llm_analyze(prompt: str, system: str = "", max_tokens: int = 800) -> str:
    """Backward-compatible wrapper. Returns text or empty string."""
    text, provider = await llm_chat(prompt, system=system, max_tokens=max_tokens)
    return text


def get_active_provider() -> str:
    """Returns the name of the first available provider."""
    for p in get_providers():
        if p.enabled and time.time() >= p._rate_limited_until:
            return p.name
    return "none"
