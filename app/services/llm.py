import json
from typing import Any

from google import genai
from google.genai import types

from app.config import Settings


class LLMConfigurationError(RuntimeError):
    """Raised when Gemini or Vertex AI is not configured correctly."""


class GeminiService:
    def __init__(self, settings: Settings):
        self.settings = settings
        if settings.google_use_vertex_ai and not settings.google_cloud_project:
            raise LLMConfigurationError(
                "Vertex AI is enabled, but GOOGLE_CLOUD_PROJECT is not set."
            )
        if not settings.google_use_vertex_ai and not settings.google_api_key:
            raise LLMConfigurationError(
                "Gemini Developer API mode requires GOOGLE_API_KEY, or set GOOGLE_USE_VERTEX_AI=true."
            )

        client_kwargs: dict[str, Any] = {}
        if settings.google_use_vertex_ai:
            client_kwargs["vertexai"] = True
            client_kwargs["project"] = settings.google_cloud_project
            client_kwargs["location"] = settings.google_cloud_location
        else:
            client_kwargs["api_key"] = settings.google_api_key
        self.client = genai.Client(**client_kwargs)

    def generate_json(self, prompt: str) -> dict[str, Any]:
        try:
            response = self.client.models.generate_content(
                model=self.settings.google_genai_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            text = response.text if hasattr(response, "text") else "{}"
            return json.loads(text)
        except Exception as exc:
            raise LLMConfigurationError(self._format_runtime_error(exc)) from exc

    def generate_text(self, prompt: str) -> str:
        try:
            response = self.client.models.generate_content(
                model=self.settings.google_genai_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,
                ),
            )
            return response.text if hasattr(response, "text") else ""
        except Exception as exc:
            raise LLMConfigurationError(self._format_runtime_error(exc)) from exc

    def _format_runtime_error(self, exc: Exception) -> str:
        if self.settings.google_use_vertex_ai:
            return (
                "Vertex AI request failed. Make sure GOOGLE_CLOUD_PROJECT is set, "
                "you ran 'gcloud auth application-default login' locally, and the active "
                "user or Cloud Run service account has roles/aiplatform.user. "
                f"Original error: {exc}"
            )
        return (
            "Gemini request failed. Check GOOGLE_API_KEY or switch to Vertex AI mode. "
            f"Original error: {exc}"
        )
