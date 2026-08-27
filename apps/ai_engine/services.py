"""
AI Engine services — OpenRouter API integration.
"""

import json
import logging
import time

import httpx

from django.conf import settings

logger = logging.getLogger(__name__)


class AIService:
    """Central AI service for OpenRouter API calls."""

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.OPENROUTER_MODEL
        self.temperature = settings.OPENROUTER_TEMPERATURE
        self.max_tokens = settings.OPENROUTER_MAX_TOKENS
        self.timeout = settings.OPENROUTER_TIMEOUT
        self.api_url = settings.OPENROUTER_API_URL

    def _call_api(self, messages: list, response_format: str = "json") -> dict:
        """Make an API call to OpenRouter."""
        if not self.api_key:
            return {"success": False, "error": "OPENROUTER_API_KEY non configurée", "data": {}}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://dataextract-ai.app",
            "X-Title": "DataExtract AI",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        try:
            start = time.time()
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.api_url, json=payload, headers=headers)
                duration_ms = int((time.time() - start) * 1000)

                if response.status_code != 200:
                    return {"success": False, "error": f"API error {response.status_code}: {response.text[:200]}", "data": {}, "duration_ms": duration_ms}

                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})

                return {
                    "success": True,
                    "content": content,
                    "tokens_input": usage.get("prompt_tokens", 0),
                    "tokens_output": usage.get("completion_tokens", 0),
                    "duration_ms": duration_ms,
                }

        except httpx.TimeoutException:
            return {"success": False, "error": "Timeout API OpenRouter", "data": {}}
        except Exception as e:
            return {"success": False, "error": f"Erreur: {str(e)}", "data": {}}

    def analyze_page(self, html_content: str, url: str) -> dict:
        """Analyze a web page and suggest field selectors."""
        # Truncate HTML to avoid token limits
        truncated = html_content[:8000]

        messages = [
            {"role": "system", "content": """You are a web scraping expert. Analyze HTML and suggest CSS selectors for data extraction.
Respond with JSON: {"fields": [{"name": "field_name", "selector": "css_selector", "type": "text|price|date|url|image|number", "confidence": 0.0-1.0}]}
Be precise with CSS selectors. Focus on repeatable product/item elements."""},
            {"role": "user", "content": f"Analyze this HTML from {url} and suggest extraction fields:\n\n{truncated}"},
        ]

        result = self._call_api(messages)
        if not result["success"]:
            return result

        try:
            data = json.loads(result["content"])
            return {"success": True, "data": data, "tokens": result.get("tokens_input", 0) + result.get("tokens_output", 0), "duration_ms": result.get("duration_ms", 0)}
        except json.JSONDecodeError:
            return {"success": False, "error": "Réponse IA non-JSON", "data": {}}

    def clean_data(self, records: list, field_types: dict) -> dict:
        """Clean and normalize extracted data using AI."""
        messages = [
            {"role": "system", "content": "You are a data cleaning expert. Clean the provided JSON records: trim whitespace, normalize dates, fix prices, validate URLs/emails. Return cleaned JSON array."},
            {"role": "user", "content": f"Field types: {json.dumps(field_types)}\nRecords to clean:\n{json.dumps(records[:20])}"},
        ]

        result = self._call_api(messages)
        if not result["success"]:
            return result

        try:
            cleaned = json.loads(result["content"])
            return {"success": True, "data": cleaned}
        except json.JSONDecodeError:
            return {"success": False, "error": "Réponse IA non-JSON"}

    def detect_anomalies(self, records: list, field_types: dict) -> dict:
        """Detect anomalies in extracted data."""
        messages = [
            {"role": "system", "content": "You are a data quality expert. Analyze these records and detect anomalies: missing values, inconsistent prices, invalid formats, outliers. Return JSON: {\"anomalies\": [{\"record_index\": 0, \"field\": \"name\", \"type\": \"missing|inconsistent|invalid|outlier\", \"severity\": \"low|medium|high\", \"description\": \"...\"}]}"},
            {"role": "user", "content": f"Field types: {json.dumps(field_types)}\nRecords:\n{json.dumps(records[:50])}"},
        ]

        result = self._call_api(messages)
        if not result["success"]:
            return result

        try:
            data = json.loads(result["content"])
            return {"success": True, "data": data}
        except json.JSONDecodeError:
            return {"success": False, "error": "Réponse IA non-JSON"}

    def chat(self, user_message: str, context: str = "") -> dict:
        """AI chat assistant for data analysis."""
        messages = [
            {"role": "system", "content": "You are DataExtract AI, an expert assistant for web data extraction and structuration. Help users configure extractions, analyze data quality, and troubleshoot issues. Be concise and practical."},
        ]
        if context:
            messages.append({"role": "system", "content": f"Context:\n{context[:2000]}"})
        messages.append({"role": "user", "content": user_message})

        result = self._call_api(messages, response_format="text")
        return result


# Singleton
ai_service = AIService()
