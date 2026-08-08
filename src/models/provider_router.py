import os
import json
import logging
import asyncio
import datetime
from typing import Dict, Any, List, Optional
import urllib.request
import urllib.error

from src.models.openrouter_client import OpenRouterClient, Message
from src.memory.sqlite_store import SQLiteMemoryStore
from src.utils.config import config

logger = logging.getLogger(__name__)

class ProviderRouter:
    """Unified router supporting OpenRouter, OpenAI, Google AI Studio, and Anthropic APIs."""
    
    def __init__(self, openrouter_client: Optional[OpenRouterClient] = None, memory_store: Optional[SQLiteMemoryStore] = None):
        self.openrouter_client = openrouter_client or OpenRouterClient()
        self.memory_store = memory_store or SQLiteMemoryStore()

    def get_api_key_for_provider(self, provider: str) -> Optional[str]:
        """Fetch active API key for provider from SQLite DB with .env fallback."""
        provider_lower = provider.lower()
        
        # 1. Try SQLite Database first
        try:
            db_key = self.memory_store.get_api_key_by_provider(provider_lower)
            if db_key and db_key.strip():
                return db_key.strip()
        except Exception as e:
            logger.warning(f"Error fetching API key from SQLite for {provider}: {e}")

        # 2. Fall back to environment variables
        if provider_lower == "openrouter":
            return getattr(config.settings, "openrouter_api_key", None) or os.getenv("OPENROUTER_API_KEY")
        elif provider_lower in ["openai"]:
            return os.getenv("OPENAI_API_KEY")
        elif provider_lower in ["google", "gemini"]:
            return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        elif provider_lower in ["anthropic", "claude"]:
            return os.getenv("ANTHROPIC_API_KEY")
        elif provider_lower in ["groq"]:
            return os.getenv("GROQ_API_KEY")
        elif provider_lower in ["mistral"]:
            return os.getenv("MISTRAL_API_KEY")
            
        return None

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Dict[str, Any]:
        """Route generation request to appropriate provider based on model ID prefix or configuration."""
        raw_model = model_id.strip()
        provider_name = "openrouter"
        clean_model = raw_model

        known_providers = ["google", "gemini", "openai", "anthropic", "claude", "groq", "mistral", "openrouter", "deepseek", "qwen"]
        if ":" in raw_model:
            parts = raw_model.split(":", 1)
            prov = parts[0].lower().strip()
            if "/" not in parts[0] and prov in known_providers:
                provider_name = prov
                clean_model = parts[1]
            else:
                clean_model = raw_model
        elif raw_model.startswith("google/"):
            provider_name = "google"
            clean_model = raw_model.replace("google/", "")
        elif raw_model.startswith("openai/"):
            provider_name = "openai"
            clean_model = raw_model.replace("openai/", "")
        elif raw_model.startswith("anthropic/"):
            provider_name = "anthropic"
            clean_model = raw_model.replace("anthropic/", "")
        elif raw_model.startswith("groq/"):
            provider_name = "groq"
            clean_model = raw_model.replace("groq/", "")
        elif raw_model.startswith("mistral/"):
            provider_name = "mistral"
            clean_model = raw_model.replace("mistral/", "")
        elif raw_model.startswith("openrouter/"):
            provider_name = "openrouter"
            clean_model = raw_model.replace("openrouter/", "")

        provider_name = provider_name.lower().strip()

        # 1. Google AI Studio Direct API
        if provider_name in ["google", "gemini"]:
            api_key = self.get_api_key_for_provider("google")
            if api_key:
                return await self._generate_google_direct(messages, clean_model, api_key, temperature, max_tokens)
            else:
                return {
                    "success": False,
                    "error": "No Google AI Studio API Key found. Please add your Google AI Studio API key in Settings -> Models & API Keys.",
                    "content": "⚠️ No Google AI Studio API Key found. Please add your Google AI Studio API key in Settings -> Models & API Keys (or set GEMINI_API_KEY in .env) to use Google AI Studio.",
                    "model_id": f"google/{clean_model}"
                }

        # 2. OpenAI Native Direct API
        if provider_name in ["openai"]:
            api_key = self.get_api_key_for_provider("openai")
            if api_key:
                return await self._generate_openai_direct(messages, clean_model, api_key, temperature, max_tokens)
            else:
                return {
                    "success": False,
                    "error": "No OpenAI API Key found. Please add your OpenAI API key in Settings -> Models & API Keys.",
                    "content": "⚠️ No OpenAI API Key found. Please add your OpenAI API key in Settings -> Models & API Keys (or set OPENAI_API_KEY in .env) to use OpenAI.",
                    "model_id": f"openai/{clean_model}"
                }

        # 3. Anthropic Direct API
        if provider_name in ["anthropic", "claude"]:
            api_key = self.get_api_key_for_provider("anthropic")
            if api_key:
                return await self._generate_anthropic_direct(messages, clean_model, api_key, temperature, max_tokens)
            else:
                return {
                    "success": False,
                    "error": "No Anthropic API Key found. Please add your Anthropic API key in Settings -> Models & API Keys.",
                    "content": "⚠️ No Anthropic API Key found. Please add your Anthropic API key in Settings -> Models & API Keys (or set ANTHROPIC_API_KEY in .env) to use Anthropic.",
                    "model_id": f"anthropic/{clean_model}"
                }

        # 4. Groq Direct API
        if provider_name in ["groq"]:
            api_key = self.get_api_key_for_provider("groq")
            if api_key:
                return await self._generate_groq_direct(messages, clean_model, api_key, temperature, max_tokens)
            else:
                return {
                    "success": False,
                    "error": "No Groq API Key found. Please add your Groq API key in Settings -> Models & API Keys.",
                    "content": "⚠️ No Groq API Key found. Please add your Groq API key in Settings -> Models & API Keys (or set GROQ_API_KEY in .env) to use Groq.",
                    "model_id": f"groq/{clean_model}"
                }

        # 5. Mistral Direct API
        if provider_name in ["mistral"]:
            api_key = self.get_api_key_for_provider("mistral")
            if api_key:
                return await self._generate_mistral_direct(messages, clean_model, api_key, temperature, max_tokens)
            # If no native Mistral API key set, fall through to OpenRouter with mistralai/ prefix!

        # 6. OpenRouter API
        formatted_model = clean_model
        model_lower = clean_model.lower()
        if "gemini" in model_lower and not model_lower.startswith("google/"):
            formatted_model = f"google/{clean_model}"
        elif "deepseek" in model_lower and not model_lower.startswith("deepseek/"):
            formatted_model = f"deepseek/{clean_model}"
        elif "qwen" in model_lower and not model_lower.startswith("qwen/"):
            formatted_model = f"qwen/{clean_model}"
        elif "claude" in model_lower and not model_lower.startswith("anthropic/"):
            formatted_model = f"anthropic/{clean_model}"
        elif ("mistral" in model_lower or "codestral" in model_lower) and not model_lower.startswith("mistralai/"):
            formatted_model = f"mistralai/{clean_model}"

        from src.models.openrouter_client import Message
        msg_objs = [Message(role=m.get("role", "user"), content=m.get("content", "")) for m in messages]
        resp = await self.openrouter_client.chat_completion(
            messages=msg_objs,
            model_type=formatted_model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        content = ""
        if resp.choices:
            content = resp.choices[0].get("message", {}).get("content", "")
        tokens = resp.usage.total_tokens if resp.usage else 0
        return {"content": content, "model_id": formatted_model, "tokens_used": tokens, "success": True}

    @staticmethod
    def get_model_pricing_sync(model_id: str) -> Dict[str, float]:
        """
        Synchronously look up approximate input/output pricing (per million tokens)
        for any model ID.  Uses the static fallback catalog so it works without
        network access or an async context.

        Returns {"input": float, "output": float}  ($/1M tokens).
        Returns a low safe-fallback if the model is not in the catalog.
        """
        import re as _re
        clean = model_id.strip()
        if ":" in clean:
            # strip provider prefix e.g. "google:gemini-2.5-flash"
            clean = clean.split(":", 1)[1]
        clean = clean.lower()

        # Ordered list of (substring, input$/1M, output$/1M)
        _CATALOG = [
            # OpenRouter / generic
            ("qwen3",                       0.10,  0.30),
            ("qwen",                        0.10,  0.30),
            ("deepseek-v4-flash",           0.14,  0.28),
            ("deepseek-v4-pro",             0.55,  2.19),
            ("deepseek-r1-distill",         0.75,  0.99),
            ("deepseek",                    0.14,  0.28),
            ("gpt-oss-120b",                0.00,  0.00),
            # Google
            ("gemini-3.6-flash",            0.10,  0.40),
            ("gemini-3.5-flash-lite",       0.075, 0.30),
            ("gemini-3.5-flash",            0.10,  0.40),
            ("gemini-3.1-flash-lite",       0.075, 0.30),
            ("gemini-3.1-pro",              1.25,  5.00),
            ("gemini-3-flash",              0.10,  0.40),
            ("gemini-2.5-flash-lite",       0.075, 0.30),
            ("gemini-2.5-flash",            0.10,  0.40),
            ("gemini-2.5-pro",              1.25,  5.00),
            ("gemini-2.0-flash-lite",       0.075, 0.30),
            ("gemini-2.0-flash",            0.10,  0.40),
            ("gemini-1.5-flash",            0.075, 0.30),
            ("gemini-1.5-pro",              1.25,  5.00),
            # OpenAI
            ("gpt-4o-mini",                 0.15,  0.60),
            ("gpt-4o",                      2.50, 10.00),
            ("o3-mini",                     1.10,  4.40),
            ("o1-mini",                     1.10,  4.40),
            ("gpt-3.5-turbo",               0.50,  1.50),
            # Anthropic
            ("claude-3-7-sonnet",           3.00, 15.00),
            ("claude-3-5-sonnet",           3.00, 15.00),
            ("claude-3-5-haiku",            0.80,  4.00),
            ("claude-3-haiku",              0.25,  1.25),
            ("claude",                      3.00, 15.00),
            # Groq
            ("llama-3.3-70b",               0.59,  0.79),
            ("llama-3.1-8b",                0.05,  0.08),
            ("mixtral-8x7b",                0.24,  0.24),
            # Mistral
            ("mistral-large",               2.00,  6.00),
            ("pixtral-large",               2.00,  6.00),
            ("codestral",                   0.30,  0.90),
            ("mistral-small",               0.10,  0.30),
            ("mistral",                     0.20,  0.60),
        ]

        for substr, inp, out in _CATALOG:
            if substr in clean:
                return {"input": inp, "output": out}

        # Generic fallback — low cost assumption
        return {"input": 0.10, "output": 0.30}

    async def fetch_provider_models(self, provider: str) -> List[Dict[str, Any]]:
        """Fetch models with pricing metadata and active/deprecated flags for provider."""
        provider_lower = provider.lower().strip()
        api_key = self.get_api_key_for_provider(provider_lower)


        # 1. OpenRouter Catalog
        if provider_lower == "openrouter":
            try:
                loop = asyncio.get_event_loop()
                req = urllib.request.Request("https://openrouter.ai/api/v1/models")
                res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10.0))
                data = json.loads(res.read().decode("utf-8"))
                models = []
                for item in data.get("data", []):
                    model_id = item.get("id", "")
                    name = item.get("name", model_id)
                    pricing = item.get("pricing", {})
                    
                    try:
                        p_in = float(pricing.get("prompt", "0")) * 1_000_000
                        p_out = float(pricing.get("completion", "0")) * 1_000_000
                        cost_str = f"${p_in:.2f}/1M in, ${p_out:.2f}/1M out" if (p_in > 0 or p_out > 0) else "Free / Included"
                    except Exception:
                        cost_str = "Standard Pricing"
                        
                    models.append({
                        "id": model_id,
                        "name": name,
                        "provider": "openrouter",
                        "cost_label": cost_str,
                        "is_active": True,
                        "context_length": item.get("context_length", 0)
                    })
                return models
            except Exception as e:
                logger.warning(f"Failed to fetch OpenRouter model catalog dynamically: {e}")
                return [
                    {"id": "qwen/qwen3.5-flash-02-23", "name": "Qwen 3.5 Flash", "provider": "openrouter", "cost_label": "$0.10/1M in, $0.30/1M out", "is_active": True},
                    {"id": "deepseek/deepseek-v4-flash", "name": "DeepSeek V4 Flash", "provider": "openrouter", "cost_label": "$0.14/1M in, $0.28/1M out", "is_active": True},
                    {"id": "deepseek/deepseek-v4-pro", "name": "DeepSeek V4 Pro", "provider": "openrouter", "cost_label": "$0.55/1M in, $2.19/1M out", "is_active": True},
                    {"id": "google/gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash Lite", "provider": "openrouter", "cost_label": "$0.075/1M in, $0.30/1M out", "is_active": True},
                    {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "provider": "openrouter", "cost_label": "$3.00/1M in, $15.00/1M out", "is_active": True},
                ]

        # 2. Google AI Studio Catalog
        elif provider_lower in ["google", "gemini"]:
            models_list = []
            if api_key:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key.strip()}"
                    loop = asyncio.get_event_loop()
                    req = urllib.request.Request(url)
                    res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10.0))
                    data = json.loads(res.read().decode("utf-8"))
                    for m in data.get("models", []):
                        raw_id = m.get("name", "").replace("models/", "")
                        methods = m.get("supportedGenerationMethods", [])
                        if "generateContent" in methods:
                            disp_name = m.get("displayName") or raw_id
                            models_list.append({
                                "id": raw_id,
                                "name": f"{disp_name} ({raw_id})",
                                "provider": "google",
                                "cost_label": "Free Tier / Paid Quota",
                                "is_active": True
                            })
                except Exception as e:
                    logger.debug(f"Google AI Studio live model fetch notice: {e}")

            if not models_list:
                # Complete Gemini catalog matching Google AI Studio dashboard
                models_list = [
                    {"id": "gemini-3.6-flash", "name": "Gemini 3.6 Flash", "provider": "google", "cost_label": "$0.10/1M in, $0.40/1M out", "is_active": True},
                    {"id": "gemini-3.5-flash", "name": "Gemini 3.5 Flash", "provider": "google", "cost_label": "$0.10/1M in, $0.40/1M out", "is_active": True},
                    {"id": "gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash Lite", "provider": "google", "cost_label": "$0.075/1M in, $0.30/1M out", "is_active": True},
                    {"id": "gemini-3.1-flash-lite", "name": "Gemini 3.1 Flash Lite", "provider": "google", "cost_label": "$0.075/1M in, $0.30/1M out", "is_active": True},
                    {"id": "gemini-3.1-pro", "name": "Gemini 3.1 Pro", "provider": "google", "cost_label": "$1.25/1M in, $5.00/1M out", "is_active": True},
                    {"id": "gemini-3-flash", "name": "Gemini 3 Flash", "provider": "google", "cost_label": "$0.10/1M in, $0.40/1M out", "is_active": True},
                    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "provider": "google", "cost_label": "$0.10/1M in, $0.40/1M out", "is_active": True},
                    {"id": "gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash Lite", "provider": "google", "cost_label": "$0.075/1M in, $0.30/1M out", "is_active": True},
                    {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "provider": "google", "cost_label": "$1.25/1M in, $5.00/1M out", "is_active": True},
                    {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "provider": "google", "cost_label": "$0.10/1M in, $0.40/1M out", "is_active": True},
                    {"id": "gemini-2.0-flash-lite", "name": "Gemini 2.0 Flash Lite", "provider": "google", "cost_label": "$0.075/1M in, $0.30/1M out", "is_active": True},
                    {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "provider": "google", "cost_label": "$0.075/1M in, $0.30/1M out", "is_active": True},
                    {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "provider": "google", "cost_label": "$1.25/1M in, $5.00/1M out", "is_active": True},
                    {"id": "gemini-2.5-flash-tts", "name": "Gemini 2.5 Flash TTS Voice", "provider": "google", "cost_label": "TTS Audio Model", "is_active": True},
                ]
            return models_list

        # 3. OpenAI Catalog
        elif provider_lower in ["openai"]:
            return [
                {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai", "cost_label": "$0.15/1M in, $0.60/1M out", "is_active": True},
                {"id": "gpt-4o", "name": "GPT-4o Flagship", "provider": "openai", "cost_label": "$2.50/1M in, $10.00/1M out", "is_active": True},
                {"id": "o3-mini", "name": "o3-mini Reasoning", "provider": "openai", "cost_label": "$1.10/1M in, $4.40/1M out", "is_active": True},
                {"id": "o1-mini", "name": "o1-mini Reasoning", "provider": "openai", "cost_label": "$1.10/1M in, $4.40/1M out", "is_active": True},
                {"id": "whisper-1", "name": "Whisper-1 Speech-to-Text", "provider": "openai", "cost_label": "$0.006 / min STT", "is_active": True},
                {"id": "tts-1", "name": "TTS-1 Text-to-Speech Voice", "provider": "openai", "cost_label": "$0.015 / 1k chars TTS", "is_active": True},
                {"id": "tts-1-hd", "name": "TTS-1-HD High Def Voice", "provider": "openai", "cost_label": "$0.030 / 1k chars TTS", "is_active": True},
                {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo [Legacy]", "provider": "openai", "cost_label": "[Deprecated] Legacy Model", "is_active": False},
                {"id": "text-davinci-003", "name": "Davinci-003 [Retired]", "provider": "openai", "cost_label": "[Deprecated] Retired", "is_active": False},
            ]

        # 4. Anthropic Catalog
        elif provider_lower in ["anthropic", "claude"]:
            return [
                {"id": "claude-3-7-sonnet-20250219", "name": "Claude 3.7 Sonnet (Hybrid Reasoning)", "provider": "anthropic", "cost_label": "$3.00/1M in, $15.00/1M out", "is_active": True},
                {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "provider": "anthropic", "cost_label": "$3.00/1M in, $15.00/1M out", "is_active": True},
                {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "provider": "anthropic", "cost_label": "$0.80/1M in, $4.00/1M out", "is_active": True},
                {"id": "claude-2.1", "name": "Claude 2.1 [Legacy]", "provider": "anthropic", "cost_label": "[Deprecated] Legacy", "is_active": False},
            ]

        # 5. Groq Catalog
        elif provider_lower in ["groq"]:
            models_list = []
            if api_key:
                try:
                    headers = {
                        "Authorization": f"Bearer {api_key.strip()}",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                    req = urllib.request.Request("https://api.groq.com/openai/v1/models", headers=headers)
                    loop = asyncio.get_event_loop()
                    res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10.0))
                    data = json.loads(res.read().decode("utf-8"))
                    for m in data.get("data", []):
                        m_id = m.get("id", "")
                        models_list.append({
                            "id": m_id,
                            "name": f"Groq {m_id}",
                            "provider": "groq",
                            "cost_label": "Ultra-Fast LPUs",
                            "is_active": True
                        })
                except Exception as e:
                    logger.debug(f"Groq live model fetch notice: {e}")

            if not models_list:
                models_list = [
                    {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B Versatile", "provider": "groq", "cost_label": "$0.59/1M in, $0.79/1M out", "is_active": True},
                    {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B Instant", "provider": "groq", "cost_label": "$0.05/1M in, $0.08/1M out", "is_active": True},
                    {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7b", "provider": "groq", "cost_label": "$0.24/1M in, $0.24/1M out", "is_active": True},
                    {"id": "deepseek-r1-distill-llama-70b", "name": "DeepSeek R1 Distill 70B", "provider": "groq", "cost_label": "$0.75/1M in, $0.99/1M out", "is_active": True},
                    {"id": "whisper-large-v3", "name": "Whisper Large V3 (Audio STT)", "provider": "groq", "cost_label": "STT Audio Model", "is_active": True},
                ]
            return models_list

        # 6. Mistral Catalog
        elif provider_lower in ["mistral"]:
            models_list = []
            if api_key:
                try:
                    headers = {
                        "Authorization": f"Bearer {api_key.strip()}",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                    req = urllib.request.Request("https://api.mistral.ai/v1/models", headers=headers)
                    loop = asyncio.get_event_loop()
                    res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10.0))
                    data = json.loads(res.read().decode("utf-8"))
                    for m in data.get("data", []):
                        m_id = m.get("id", "")
                        models_list.append({
                            "id": m_id,
                            "name": f"Mistral {m_id}",
                            "provider": "mistral",
                            "cost_label": "Native Mistral AI",
                            "is_active": True
                        })
                except Exception as e:
                    logger.debug(f"Mistral live model fetch notice: {e}")

            if not models_list:
                models_list = [
                    {"id": "mistral-large-latest", "name": "Mistral Large (Flagship)", "provider": "mistral", "cost_label": "$2.00/1M in, $6.00/1M out", "is_active": True},
                    {"id": "pixtral-large-latest", "name": "Pixtral Large (Multimodal)", "provider": "mistral", "cost_label": "$2.00/1M in, $6.00/1M out", "is_active": True},
                    {"id": "codestral-latest", "name": "Codestral (Coding Specialist)", "provider": "mistral", "cost_label": "$0.30/1M in, $0.90/1M out", "is_active": True},
                    {"id": "mistral-small-latest", "name": "Mistral Small", "provider": "mistral", "cost_label": "$0.10/1M in, $0.30/1M out", "is_active": True},
                ]
            return models_list

        return []

    async def test_provider_key(self, provider: str, key_value: Optional[str] = None, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Test and verify an API key for a specific provider."""
        provider_lower = (provider or "").strip().lower()
        key_str = (key_value or self.get_api_key_for_provider(provider_lower) or "").strip()

        if not key_str:
            return {"success": False, "error": f"No API Key provided or found for [{provider_lower}]. Please enter a key or set environment variable."}

        test_message = [{"role": "user", "content": "Ping test. Respond with OK."}]
        
        try:
            if provider_lower == "openrouter":
                target_model = model_id or "qwen/qwen3.5-flash-02-23"
                headers = {
                    "Authorization": f"Bearer {key_str}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                payload = json.dumps({
                    "model": target_model,
                    "messages": test_message,
                    "max_tokens": 10
                }).encode("utf-8")
                
                req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=payload, headers=headers, method="POST")
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10.0))
                res_data = json.loads(response.read().decode("utf-8"))
                return {"success": True, "message": "OpenRouter API Key verified successfully!", "details": res_data.get("choices", [{}])[0].get("message", {}).get("content", "")}

            elif provider_lower == "openai":
                headers = {
                    "Authorization": f"Bearer {key_str}",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                req = urllib.request.Request("https://api.openai.com/v1/models", headers=headers)
                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10.0))
                data = json.loads(res.read().decode("utf-8"))
                model_count = len(data.get("data", []))
                return {
                    "success": True,
                    "message": f"OpenAI API Key verified successfully! ({model_count} models accessible)",
                    "details": f"{model_count} models available in OpenAI catalog"
                }

            elif provider_lower == "google":
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key_str}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10.0))
                data = json.loads(res.read().decode("utf-8"))
                model_count = len(data.get("models", []))
                return {
                    "success": True,
                    "message": f"Google AI Studio API Key verified successfully! ({model_count} models accessible)",
                    "details": f"{model_count} models available in Google AI Studio catalog"
                }

            elif provider_lower == "anthropic":
                target_model = model_id or "claude-3-5-haiku-20241022"
                return await self._generate_anthropic_direct(test_message, target_model, key_str, 0.2, 10)

            elif provider_lower == "groq":
                headers = {
                    "Authorization": f"Bearer {key_str}",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                req = urllib.request.Request("https://api.groq.com/openai/v1/models", headers=headers)
                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10.0))
                data = json.loads(res.read().decode("utf-8"))
                model_count = len(data.get("data", []))
                return {
                    "success": True,
                    "message": f"Groq API Key verified successfully! ({model_count} models accessible on LPU speed)",
                    "details": f"{model_count} models available in Groq catalog"
                }

            elif provider_lower == "mistral":
                headers = {
                    "Authorization": f"Bearer {key_str}",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                req = urllib.request.Request("https://api.mistral.ai/v1/models", headers=headers)
                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10.0))
                data = json.loads(res.read().decode("utf-8"))
                model_count = len(data.get("data", []))
                return {
                    "success": True,
                    "message": f"Mistral API Key verified successfully! ({model_count} models accessible)",
                    "details": f"{model_count} models available in Mistral catalog"
                }

            else:
                return {"success": False, "error": f"Unsupported provider: {provider}"}
        except urllib.error.HTTPError as http_err:
            err_body = http_err.read().decode("utf-8") if http_err.fp else str(http_err)
            return {"success": False, "error": f"HTTP {http_err.code}: {err_body}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_api_key_for_provider(self, provider: str) -> Optional[str]:
        """Fetch active API key for provider from SQLite DB with .env fallback."""
        provider_lower = provider.lower().strip()
        if provider_lower in ["mistralai", "codestral"]:
            provider_lower = "mistral"
        elif provider_lower in ["gemini"]:
            provider_lower = "google"
        elif provider_lower in ["claude"]:
            provider_lower = "anthropic"
        
        # 1. Try SQLite Database first
        try:
            db_key = self.memory_store.get_api_key_by_provider(provider_lower)
            if db_key and db_key.strip():
                return db_key.strip()
        except Exception as e:
            logger.warning(f"Error fetching API key from SQLite for {provider}: {e}")

        # 2. Fall back to environment variables
        if provider_lower == "openrouter":
            return getattr(config.settings, "openrouter_api_key", None) or os.getenv("OPENROUTER_API_KEY")
        elif provider_lower in ["openai"]:
            return os.getenv("OPENAI_API_KEY")
        elif provider_lower in ["google", "gemini"]:
            return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        elif provider_lower in ["anthropic", "claude"]:
            return os.getenv("ANTHROPIC_API_KEY")
        elif provider_lower in ["groq"]:
            return os.getenv("GROQ_API_KEY")
        elif provider_lower in ["mistral", "mistralai", "codestral"]:
            return os.getenv("MISTRAL_API_KEY")
            
        return None

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Route generation request to appropriate provider with tool calling support."""
        raw_model = model_id.strip()
        provider_name = "openrouter"
        clean_model = raw_model

        known_providers = ["google", "gemini", "openai", "anthropic", "claude", "groq", "mistral", "mistralai", "codestral", "openrouter", "deepseek", "qwen"]
        if ":" in raw_model:
            parts = raw_model.split(":", 1)
            prov = parts[0].lower().strip()
            if "/" not in parts[0] and prov in known_providers:
                provider_name = prov
                clean_model = parts[1]
            else:
                clean_model = raw_model
        elif raw_model.startswith("google/") or raw_model.startswith("gemini/"):
            provider_name = "google"
            clean_model = raw_model.split("/", 1)[1]
        elif raw_model.startswith("openai/"):
            provider_name = "openai"
            clean_model = raw_model.replace("openai/", "")
        elif raw_model.startswith("anthropic/") or raw_model.startswith("claude/"):
            provider_name = "anthropic"
            clean_model = raw_model.split("/", 1)[1]
        elif raw_model.startswith("groq/"):
            provider_name = "groq"
            clean_model = raw_model.replace("groq/", "")
        elif raw_model.startswith("mistral/") or raw_model.startswith("mistralai/") or raw_model.startswith("codestral/"):
            provider_name = "mistral"
            clean_model = raw_model.split("/", 1)[1]
        elif raw_model.startswith("openrouter/"):
            provider_name = "openrouter"
            clean_model = raw_model.replace("openrouter/", "")

        provider_name = provider_name.lower().strip()

        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{current_time}] 🤖 Requesting completion from direct provider [{provider_name.upper()}]: {clean_model}...")

        # Helper to fall back to OpenRouter pass-through for the requested model if direct provider fails or lacks key
        async def _fallback_to_openrouter(target_model_name: str) -> Optional[Dict[str, Any]]:
            openrouter_key = self.get_api_key_for_provider("openrouter")
            if not openrouter_key:
                return None
            
            fmt_model = target_model_name
            t_lower = target_model_name.lower()
            if "gemini" in t_lower and not t_lower.startswith("google/"):
                fmt_model = f"google/{target_model_name}"
            elif "claude" in t_lower and not t_lower.startswith("anthropic/"):
                fmt_model = f"anthropic/{target_model_name}"
            elif ("mistral" in t_lower or "codestral" in t_lower or "pixtral" in t_lower) and not t_lower.startswith("mistralai/"):
                fmt_model = f"mistralai/{target_model_name}"
            elif "deepseek" in t_lower and not t_lower.startswith("deepseek/"):
                fmt_model = f"deepseek/{target_model_name}"
            elif "qwen" in t_lower and not t_lower.startswith("qwen/"):
                fmt_model = f"qwen/{target_model_name}"

            openrouter_aliases = {
                "google/gemini-2.0-flash": "google/gemini-2.5-flash",
                "google/gemini-2.0-flash-lite": "google/gemini-2.5-flash-lite",
                "google/gemini-3.5-flash": "google/gemini-2.5-flash",
                "google/gemini-3.6-flash": "google/gemini-2.5-flash",
                "google/gemini-3.1-pro": "google/gemini-2.5-pro",
                "google/gemini-3-flash": "google/gemini-2.5-flash",
            }
            fmt_model = openrouter_aliases.get(fmt_model, fmt_model)

            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🔄 Direct provider unavailable/failed. Falling back to OpenRouter pass-through for model [{fmt_model}]...")
            try:
                from src.models.openrouter_client import Message
                msg_objs = []
                for m in messages:
                    if isinstance(m, dict):
                        msg_objs.append(Message(role=m.get("role", "user"), content=m.get("content", ""), tool_calls=m.get("tool_calls"), tool_call_id=m.get("tool_call_id")))
                    elif isinstance(m, Message):
                        msg_objs.append(m)

                resp = await self.openrouter_client.chat_completion(
                    messages=msg_objs,
                    model_type=fmt_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools
                )
                c_text = ""
                t_calls = None
                if resp.choices:
                    c_msg = resp.choices[0].get("message", {})
                    c_text = c_msg.get("content", "")
                    t_calls = c_msg.get("tool_calls", None)
                toks = resp.usage.total_tokens if resp.usage else 0
                return {"content": c_text, "tool_calls": t_calls, "model_id": f"openrouter:{fmt_model}", "tokens_used": toks, "success": True}
            except Exception as fe:
                logger.warning(f"OpenRouter pass-through fallback failed for {fmt_model}: {fe}")
                return None

        # 1. Google AI Studio Direct API
        if provider_name in ["google", "gemini"]:
            api_key = self.get_api_key_for_provider("google")
            if api_key:
                res = await self._generate_google_direct(messages, clean_model, api_key, temperature, max_tokens, tools)
                if res.get("success", False):
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ✅ Response received from [GOOGLE] {clean_model} (Tokens: {res.get('tokens_used', 0)})")
                    return res
                else:
                    logger.warning(f"Google direct API call returned error: {res.get('error')}. Attempting OpenRouter pass-through...")
            
            fb_res = await _fallback_to_openrouter(clean_model)
            if fb_res:
                return fb_res
            return {
                "success": False,
                "error": "No Google AI Studio API Key found. Please add your Google AI Studio API key in Settings -> Models & API Keys.",
                "content": "⚠️ No Google AI Studio API Key found. Please add your Google AI Studio API key in Settings -> Models & API Keys (or set GEMINI_API_KEY in .env) to use Google AI Studio.",
                "model_id": f"google/{clean_model}"
            }

        # 2. OpenAI Native Direct API
        if provider_name in ["openai"]:
            api_key = self.get_api_key_for_provider("openai")
            if api_key:
                res = await self._generate_openai_direct(messages, clean_model, api_key, temperature, max_tokens, tools)
                if res.get("success", False):
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ✅ Response received from [OPENAI] {clean_model} (Tokens: {res.get('tokens_used', 0)})")
                    return res
                else:
                    logger.warning(f"OpenAI direct API call returned error: {res.get('error')}. Attempting OpenRouter pass-through...")
            
            fb_res = await _fallback_to_openrouter(clean_model)
            if fb_res:
                return fb_res
            return {
                "success": False,
                "error": "No OpenAI API Key found. Please add your OpenAI API key in Settings -> Models & API Keys.",
                "content": "⚠️ No OpenAI API Key found. Please add your OpenAI API key in Settings -> Models & API Keys (or set OPENAI_API_KEY in .env) to use OpenAI.",
                "model_id": f"openai/{clean_model}"
            }

        # 3. Anthropic Direct API
        if provider_name in ["anthropic", "claude"]:
            api_key = self.get_api_key_for_provider("anthropic")
            if api_key:
                res = await self._generate_anthropic_direct(messages, clean_model, api_key, temperature, max_tokens, tools)
                if res.get("success", False):
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ✅ Response received from [ANTHROPIC] {clean_model} (Tokens: {res.get('tokens_used', 0)})")
                    return res
                else:
                    logger.warning(f"Anthropic direct API call returned error: {res.get('error')}. Attempting OpenRouter pass-through...")
            
            fb_res = await _fallback_to_openrouter(clean_model)
            if fb_res:
                return fb_res
            return {
                "success": False,
                "error": "No Anthropic API Key found. Please add your Anthropic API key in Settings -> Models & API Keys.",
                "content": "⚠️ No Anthropic API Key found. Please add your Anthropic API key in Settings -> Models & API Keys (or set ANTHROPIC_API_KEY in .env) to use Anthropic.",
                "model_id": f"anthropic/{clean_model}"
            }

        # 4. Groq Direct API
        if provider_name in ["groq"]:
            api_key = self.get_api_key_for_provider("groq")
            if api_key:
                res = await self._generate_groq_direct(messages, clean_model, api_key, temperature, max_tokens, tools)
                if res.get("success", False):
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ✅ Response received from [GROQ] {clean_model} (Tokens: {res.get('tokens_used', 0)})")
                    return res
                else:
                    logger.warning(f"Groq direct API call returned error: {res.get('error')}. Attempting OpenRouter pass-through...")
            
            fb_res = await _fallback_to_openrouter(clean_model)
            if fb_res:
                return fb_res
            return {
                "success": False,
                "error": "No Groq API Key found. Please add your Groq API key in Settings -> Models & API Keys.",
                "content": "⚠️ No Groq API Key found. Please add your Groq API key in Settings -> Models & API Keys (or set GROQ_API_KEY in .env) to use Groq.",
                "model_id": f"groq/{clean_model}"
            }

        # 5. Mistral Direct API
        if provider_name in ["mistral", "mistralai", "codestral"]:
            api_key = self.get_api_key_for_provider("mistral")
            if api_key:
                res = await self._generate_mistral_direct(messages, clean_model, api_key, temperature, max_tokens, tools)
                if res.get("success", False):
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ✅ Response received from [MISTRAL] {clean_model} (Tokens: {res.get('tokens_used', 0)})")
                    return res
                else:
                    logger.warning(f"Mistral direct API call returned error: {res.get('error')}. Attempting OpenRouter pass-through...")
            
            fb_res = await _fallback_to_openrouter(clean_model)
            if fb_res:
                return fb_res
            return {
                "success": False,
                "error": "No Mistral API Key found. Please add your Mistral API key in Settings -> Models & API Keys.",
                "content": "⚠️ No Mistral API Key found. Please add your Mistral API key in Settings -> Models & API Keys (or set MISTRAL_API_KEY in .env) to use Mistral AI.",
                "model_id": f"mistral/{clean_model}"
            }

        # 6. OpenRouter API
        formatted_model = clean_model
        model_lower = clean_model.lower()
        if "gemini" in model_lower and not model_lower.startswith("google/"):
            formatted_model = f"google/{clean_model}"
        elif "deepseek" in model_lower and not model_lower.startswith("deepseek/"):
            formatted_model = f"deepseek/{clean_model}"
        elif "qwen" in model_lower and not model_lower.startswith("qwen/"):
            formatted_model = f"qwen/{clean_model}"
        elif "claude" in model_lower and not model_lower.startswith("anthropic/"):
            formatted_model = f"anthropic/{clean_model}"
        elif ("mistral" in model_lower or "codestral" in model_lower or "pixtral" in model_lower) and not model_lower.startswith("mistralai/"):
            formatted_model = f"mistralai/{clean_model}"

        from src.models.openrouter_client import Message
        msg_objs = []
        for m in messages:
            if isinstance(m, dict):
                msg_objs.append(Message(role=m.get("role", "user"), content=m.get("content", ""), tool_calls=m.get("tool_calls"), tool_call_id=m.get("tool_call_id")))
            elif isinstance(m, Message):
                msg_objs.append(m)

        resp = await self.openrouter_client.chat_completion(
            messages=msg_objs,
            model_type=formatted_model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools
        )
        content = ""
        tool_calls = None
        if resp.choices:
            choice_msg = resp.choices[0].get("message", {})
            content = choice_msg.get("content", "")
            tool_calls = choice_msg.get("tool_calls", None)
        tokens = resp.usage.total_tokens if resp.usage else 0
        return {"content": content, "tool_calls": tool_calls, "model_id": formatted_model, "tokens_used": tokens, "success": True}

    # ── Private Provider Direct HTTP Implementations ─────────────────────────────

    async def _generate_openai_direct(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        api_key: str,
        temperature: float,
        max_tokens: int,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Direct HTTP call to OpenAI API. Preserves image_url vision content blocks."""
        from src.models.openrouter_client import extract_text_content
        formatted_messages = []
        for m in messages:
            raw_content = m.get("content")
            # Preserve list content (vision blocks: image_url, text) — only stringify scalars
            if isinstance(raw_content, list):
                safe_content = [
                    block if isinstance(block, dict) and block.get("type") in ("text", "image_url") else {"type": "text", "text": extract_text_content(block)}
                    for block in raw_content
                ]
            else:
                safe_content = extract_text_content(raw_content)
            msg_item = {
                "role": m.get("role", "user"),
                "content": safe_content
            }
            if m.get("tool_calls"):
                msg_item["tool_calls"] = m.get("tool_calls")
            if m.get("tool_call_id"):
                msg_item["tool_call_id"] = m.get("tool_call_id")
            if m.get("name"):
                msg_item["name"] = m.get("name")
            formatted_messages.append(msg_item)

        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json"
        }
        body: Dict[str, Any] = {
            "model": model_name,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if tools:
            body["tools"] = tools

        try:
            payload = json.dumps(body).encode("utf-8")
            req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=payload, headers=headers, method="POST")
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=30.0))
            data = json.loads(res.read().decode("utf-8"))
            
            msg = data.get("choices", [{}])[0].get("message", {})
            content = extract_text_content(msg.get("content", ""))
            tool_calls = msg.get("tool_calls", None)
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return {"content": content, "tool_calls": tool_calls, "model_id": f"openai/{model_name}", "tokens_used": tokens, "success": True}
        except urllib.error.HTTPError as http_err:
            err_body = http_err.read().decode("utf-8") if http_err.fp else str(http_err)
            logger.error(f"OpenAI Direct API HTTP {http_err.code}: {err_body}")
            return {"success": False, "error": f"OpenAI HTTP {http_err.code}: {err_body}", "model_id": f"openai/{model_name}"}
        except Exception as e:
            logger.error(f"OpenAI Direct API error: {e}")
            return {"success": False, "error": str(e), "model_id": f"openai/{model_name}"}

    async def _generate_google_direct(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        api_key: str,
        temperature: float,
        max_tokens: int,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Direct HTTP call to Google AI Studio Gemini REST API.
        Supports vision/image_url content blocks AND native function calling.
        Translates OpenAI tool schema/history ↔ Gemini functionDeclarations/functionCall/functionResponse.
        """
        import base64 as _b64
        from src.models.openrouter_client import extract_text_content
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key.strip()}"

        system_instruction_parts = []
        contents = []

        def _build_gemini_parts(content: Any) -> List[Dict[str, Any]]:
            """Convert OpenAI-style content (str or list of blocks) to Gemini parts."""
            if content is None:
                return [{"text": ""}]
            if isinstance(content, str):
                return [{"text": content}]
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, str):
                        parts.append({"text": block})
                    elif isinstance(block, dict):
                        btype = block.get("type", "")
                        if btype == "text":
                            parts.append({"text": block.get("text", "")})
                        elif btype == "image_url":
                            img_url = block.get("image_url", {}).get("url", "")
                            if img_url.startswith("data:"):
                                try:
                                    header, b64data = img_url.split(",", 1)
                                    mime_type = header.split(":")[1].split(";")[0]
                                    parts.append({"inlineData": {"mimeType": mime_type, "data": b64data}})
                                except Exception:
                                    parts.append({"text": "[inline image]"})
                            elif img_url.startswith("http"):
                                parts.append({"fileData": {"mimeType": "image/jpeg", "fileUri": img_url}})
                        elif btype == "thinking":
                            txt = block.get("thinking", "")
                            if txt:
                                parts.append({"text": txt})
                return parts if parts else [{"text": ""}]
            return [{"text": str(content)}]

        def _normalize_gemini_schema(schema: Any) -> None:
            """Recursively uppercase all JSON Schema 'type' values for Gemini compliance."""
            if not isinstance(schema, dict):
                return
            if "type" in schema and isinstance(schema["type"], str):
                schema["type"] = schema["type"].upper()
            for key in ("properties", "items"):
                child = schema.get(key)
                if isinstance(child, dict):
                    if key == "properties":
                        for v in child.values():
                            _normalize_gemini_schema(v)
                    else:
                        _normalize_gemini_schema(child)

        # ── 1. Translate OpenAI tools → Gemini functionDeclarations ──────────
        gemini_tools = []
        if tools:
            function_declarations = []
            for t in tools:
                if t.get("type") == "function":
                    fn = t.get("function", {})
                    params = json.loads(json.dumps(fn.get("parameters", {})))  # deep copy
                    _normalize_gemini_schema(params)
                    # Remove unsupported 'required' field at root (Gemini uses per-property 'required')
                    params.pop("required", None)
                    function_declarations.append({
                        "name": fn.get("name"),
                        "description": fn.get("description", ""),
                        "parameters": params
                    })
            if function_declarations:
                gemini_tools.append({"functionDeclarations": function_declarations})

        # ── 2. Translate OpenAI-style message history → Gemini contents ──────
        for m in messages:
            role = m.get("role", "user")
            raw_content = m.get("content")

            if role == "system":
                txt = extract_text_content(raw_content)
                if txt.strip():
                    system_instruction_parts.append({"text": txt})

            elif role == "tool":
                # Tool execution result → Gemini 'function' role with functionResponse
                name = m.get("name", "tool")
                try:
                    resp_data = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
                    if not isinstance(resp_data, dict):
                        resp_data = {"output": str(resp_data)}
                except Exception:
                    resp_data = {"output": str(raw_content)}
                contents.append({
                    "role": "function",
                    "parts": [{"functionResponse": {"name": name, "response": resp_data}}]
                })

            else:
                # user / assistant / model turn
                g_role = "user" if role == "user" else "model"
                parts = _build_gemini_parts(raw_content)

                # If assistant emitted tool_calls in this turn, append functionCall parts
                if role in ("assistant", "model") and m.get("tool_calls"):
                    for tc in m["tool_calls"]:
                        fn_name = tc.get("function", {}).get("name", "")
                        try:
                            args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                        except Exception:
                            args = {}
                        parts.append({"functionCall": {"name": fn_name, "args": args}})

                # Merge consecutive same-role turns (Gemini rejects duplicate adjacent roles)
                if contents and contents[-1]["role"] == g_role:
                    contents[-1]["parts"].extend(parts)
                else:
                    contents.append({"role": g_role, "parts": parts})

        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

        # ── 3. Build request payload ──────────────────────────────────────────
        headers = {"Content-Type": "application/json"}
        payload_dict: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}
        }
        if system_instruction_parts:
            sys_combined = "\n\n".join(p["text"] for p in system_instruction_parts)
            payload_dict["systemInstruction"] = {"parts": [{"text": sys_combined}]}
        if gemini_tools:
            payload_dict["tools"] = gemini_tools

        try:
            payload = json.dumps(payload_dict).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=60.0))
            data = json.loads(res.read().decode("utf-8"))

            candidates = data.get("candidates", [{}])
            resp_parts = candidates[0].get("content", {}).get("parts", [])

            # ── 4. Parse text content ─────────────────────────────────────────
            content_text = " ".join(
                p.get("text", "") for p in resp_parts if p.get("text")
            ).strip()

            # ── 5. Parse functionCall → OpenAI-style tool_calls ───────────────
            tool_calls_out = None
            fc_parts = [p for p in resp_parts if "functionCall" in p]
            if fc_parts:
                tool_calls_out = []
                for i, p in enumerate(fc_parts):
                    fc = p["functionCall"]
                    tool_calls_out.append({
                        "id": f"call_gemini_{i}",
                        "type": "function",
                        "function": {
                            "name": fc.get("name", ""),
                            "arguments": json.dumps(fc.get("args", {}))
                        }
                    })

            tokens = data.get("usageMetadata", {}).get("totalTokenCount", 0)
            return {
                "content": content_text,
                "tool_calls": tool_calls_out,
                "model_id": f"google/{model_name}",
                "tokens_used": tokens,
                "success": True
            }
        except urllib.error.HTTPError as http_err:
            err_body = http_err.read().decode("utf-8") if http_err.fp else str(http_err)
            logger.error(f"Google Direct API HTTP {http_err.code}: {err_body}")
            return {"success": False, "error": f"Google AI Studio HTTP {http_err.code}: {err_body}", "model_id": f"google/{model_name}"}
        except Exception as e:
            logger.error(f"Google Direct API error: {e}")
            return {"success": False, "error": str(e), "model_id": f"google/{model_name}"}

    async def _generate_anthropic_direct(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        api_key: str,
        temperature: float,
        max_tokens: int,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Direct HTTP call to Anthropic Messages API.
        Supports native tool calling (tool_use / tool_result content blocks).
        Translates OpenAI tool schema/history ↔ Anthropic format.
        """
        from src.models.openrouter_client import extract_text_content

        system_msg = ""
        user_msgs: List[Dict[str, Any]] = []

        # ── 1. Translate OpenAI tools → Anthropic tools schema ────────────────
        anthropic_tools = None
        if tools:
            anthropic_tools = []
            for t in tools:
                if t.get("type") == "function":
                    fn = t.get("function", {})
                    anthropic_tools.append({
                        "name": fn.get("name"),
                        "description": fn.get("description", ""),
                        "input_schema": fn.get("parameters", {"type": "object", "properties": {}})
                    })

        # ── 2. Translate OpenAI-style message history → Anthropic messages ────
        for m in messages:
            role = m.get("role", "user")
            raw_content = m.get("content")

            if role == "system":
                system_msg += extract_text_content(raw_content) + "\n"

            elif role == "tool":
                # Tool result → Anthropic tool_result content block inside a 'user' message
                # Merge with previous user message if it's already a tool_result carrier
                result_block: Dict[str, Any] = {
                    "type": "tool_result",
                    "tool_use_id": m.get("tool_call_id", ""),
                    "content": extract_text_content(raw_content)
                }
                if user_msgs and user_msgs[-1]["role"] == "user" and isinstance(user_msgs[-1]["content"], list):
                    user_msgs[-1]["content"].append(result_block)
                else:
                    user_msgs.append({"role": "user", "content": [result_block]})

            elif role in ("assistant", "model"):
                content_blocks: List[Dict[str, Any]] = []
                txt = extract_text_content(raw_content)
                if txt:
                    content_blocks.append({"type": "text", "text": txt})
                # If assistant called tools in this turn, add tool_use blocks
                for tc in (m.get("tool_calls") or []):
                    fn = tc.get("function", {})
                    try:
                        inp = json.loads(fn.get("arguments", "{}"))
                    except Exception:
                        inp = {}
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": fn.get("name", ""),
                        "input": inp
                    })
                if content_blocks:
                    user_msgs.append({"role": "assistant", "content": content_blocks})

            else:  # user
                txt = extract_text_content(raw_content)
                if user_msgs and user_msgs[-1]["role"] == "user" and isinstance(user_msgs[-1]["content"], str):
                    # Merge consecutive user text messages
                    user_msgs[-1]["content"] += "\n" + txt
                else:
                    user_msgs.append({"role": "user", "content": txt})

        if not user_msgs:
            user_msgs = [{"role": "user", "content": "Hello"}]

        # ── 3. Build request payload ──────────────────────────────────────────
        headers = {
            "x-api-key": api_key.strip(),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        body: Dict[str, Any] = {
            "model": model_name,
            "messages": user_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        if system_msg.strip():
            body["system"] = system_msg.strip()
        if anthropic_tools:
            body["tools"] = anthropic_tools

        try:
            payload = json.dumps(body).encode("utf-8")
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload, headers=headers, method="POST")
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=60.0))
            data = json.loads(res.read().decode("utf-8"))

            resp_blocks = data.get("content", [])

            # ── 4. Parse text content ─────────────────────────────────────────
            content_text = "".join(
                b.get("text", "") for b in resp_blocks if b.get("type") == "text"
            ).strip()

            # ── 5. Parse tool_use → OpenAI-style tool_calls ───────────────────
            tool_calls_out = None
            tu_blocks = [b for b in resp_blocks if b.get("type") == "tool_use"]
            if tu_blocks:
                tool_calls_out = []
                for tu in tu_blocks:
                    tool_calls_out.append({
                        "id": tu.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": tu.get("name", ""),
                            "arguments": json.dumps(tu.get("input", {}))
                        }
                    })

            tokens = data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0)
            return {
                "content": content_text,
                "tool_calls": tool_calls_out,
                "model_id": f"anthropic/{model_name}",
                "tokens_used": tokens,
                "success": True
            }
        except urllib.error.HTTPError as http_err:
            err_body = http_err.read().decode("utf-8") if http_err.fp else str(http_err)
            logger.error(f"Anthropic Direct API HTTP {http_err.code}: {err_body}")
            return {"success": False, "error": f"Anthropic HTTP {http_err.code}: {err_body}", "model_id": f"anthropic/{model_name}"}
        except Exception as e:
            logger.error(f"Anthropic Direct API error: {e}")
            return {"success": False, "error": str(e), "model_id": f"anthropic/{model_name}"}

    async def _generate_groq_direct(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        api_key: str,
        temperature: float,
        max_tokens: int,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Direct HTTP call to Groq API (OpenAI compatible)."""
        from src.models.openrouter_client import extract_text_content
        clean_model = model_name.replace("groq/", "").strip()
        formatted_messages = []
        for m in messages:
            msg_item = {
                "role": m.get("role", "user"),
                "content": extract_text_content(m.get("content"))
            }
            if m.get("tool_calls"):
                msg_item["tool_calls"] = m.get("tool_calls")
            if m.get("tool_call_id"):
                msg_item["tool_call_id"] = m.get("tool_call_id")
            if m.get("name"):
                msg_item["name"] = m.get("name")
            formatted_messages.append(msg_item)

        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        body: Dict[str, Any] = {
            "model": clean_model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if tools:
            body["tools"] = tools

        try:
            payload = json.dumps(body).encode("utf-8")
            req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=payload, headers=headers, method="POST")
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=30.0))
            data = json.loads(res.read().decode("utf-8"))
            
            msg = data.get("choices", [{}])[0].get("message", {})
            content = extract_text_content(msg.get("content", ""))
            tool_calls = msg.get("tool_calls", None)
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return {"content": content, "tool_calls": tool_calls, "model_id": f"groq/{clean_model}", "tokens_used": tokens, "success": True}
        except urllib.error.HTTPError as http_err:
            err_body = http_err.read().decode("utf-8") if http_err.fp else str(http_err)
            logger.error(f"Groq Direct API HTTP {http_err.code}: {err_body}")
            return {"success": False, "error": f"Groq HTTP {http_err.code}: {err_body}", "model_id": f"groq/{clean_model}"}
        except Exception as e:
            logger.error(f"Groq Direct API error: {e}")
            return {"success": False, "error": str(e), "model_id": f"groq/{clean_model}"}

    @staticmethod
    def _sanitize_mistral_tool_call_id(id_str: str) -> str:
        """Mistral API requires tool call IDs to be exactly 9 alphanumeric characters [a-zA-Z0-9]."""
        if not id_str:
            return "call00000"
        import re, hashlib
        clean = re.sub(r'[^a-zA-Z0-9]', '', id_str)
        if len(clean) == 9:
            return clean
        return hashlib.md5(id_str.encode('utf-8')).hexdigest()[:9]

    async def _generate_mistral_direct(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        api_key: str,
        temperature: float,
        max_tokens: int,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Direct HTTP call to Mistral AI API."""
        from src.models.openrouter_client import extract_text_content
        clean_model = model_name.replace("mistralai/", "").replace("mistral/", "").strip()
        formatted_messages = []
        for m in messages:
            msg_item = {
                "role": m.get("role", "user"),
                "content": extract_text_content(m.get("content"))
            }
            if m.get("tool_calls"):
                sanitized_tc = []
                for tc in m.get("tool_calls", []):
                    tc_copy = dict(tc)
                    if tc_copy.get("id"):
                        tc_copy["id"] = self._sanitize_mistral_tool_call_id(tc_copy["id"])
                    sanitized_tc.append(tc_copy)
                msg_item["tool_calls"] = sanitized_tc
            if m.get("tool_call_id"):
                msg_item["tool_call_id"] = self._sanitize_mistral_tool_call_id(m.get("tool_call_id"))
            if m.get("name"):
                msg_item["name"] = m.get("name")
            formatted_messages.append(msg_item)

        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        body: Dict[str, Any] = {
            "model": clean_model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if tools:
            body["tools"] = tools

        try:
            payload = json.dumps(body).encode("utf-8")
            req = urllib.request.Request("https://api.mistral.ai/v1/chat/completions", data=payload, headers=headers, method="POST")
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=30.0))
            data = json.loads(res.read().decode("utf-8"))
            
            msg = data.get("choices", [{}])[0].get("message", {})
            content = extract_text_content(msg.get("content", ""))
            tool_calls = msg.get("tool_calls", None)
            if tool_calls:
                for tc in tool_calls:
                    if isinstance(tc, dict) and tc.get("id"):
                        tc["id"] = self._sanitize_mistral_tool_call_id(tc["id"])
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return {"content": content, "tool_calls": tool_calls, "model_id": f"mistral/{clean_model}", "tokens_used": tokens, "success": True}
        except urllib.error.HTTPError as http_err:
            err_body = http_err.read().decode("utf-8") if http_err.fp else str(http_err)
            logger.error(f"Mistral Direct API HTTP {http_err.code}: {err_body}")
            return {"success": False, "error": f"Mistral HTTP {http_err.code}: {err_body}", "model_id": f"mistral/{clean_model}"}
        except Exception as e:
            logger.error(f"Mistral Direct API error: {e}")
            return {"success": False, "error": str(e), "model_id": f"mistral/{clean_model}"}
