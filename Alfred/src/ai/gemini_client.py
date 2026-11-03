"""Google Gemini client integration for Alfred using the official google-genai SDK.

Handles conversational Q&A, task interpretation, error resilience, and response formatting
for spoken TTS delivery.
"""

from __future__ import annotations

import logging
import re
from typing import List, Dict, Optional

from google import genai
from google.genai import types
from src.config import AppConfig
from src.ai.persona import ALFRED_SYSTEM_PROMPT

logger = logging.getLogger("alfred.ai.gemini")


class GeminiClient:
    """Wrapper around the official Google Gemini SDK with butler persona integration."""

    def __init__(self, config: AppConfig):
        self.config = config
        self._client: Optional[genai.Client] = None
        self._init_client()

    def _init_client(self) -> None:
        """Initializes the official genai Client if API key is present."""
        if self.config.has_gemini():
            try:
                self._client = genai.Client(api_key=self.config.gemini_api_key)
                logger.info("Initialized Google Gemini client with model: %s", self.config.gemini_model)
            except Exception as e:
                logger.error("Failed to initialize Gemini client: %s", e)
                self._client = None
        else:
            logger.info("Gemini API key is not configured. Assistant will inform user gracefully.")

    def clean_for_speech(self, text: str) -> str:
        """Strips markdown asterisks, hashes, backticks, and emojis so speech flows naturally."""
        if not text:
            return ""
        # Remove markdown symbols
        cleaned = re.sub(r"[\*\_#`~>]", "", text)
        # Remove bracketed citations like [1] or [source]
        cleaned = re.sub(r"\[\d+\]", "", cleaned)
        # Collapse multiple spaces or newlines into clean sentences
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def generate_response(
        self,
        prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        custom_system_instruction: Optional[str] = None,
    ) -> str:
        """Generates a conversational response from Gemini.
        
        Args:
            prompt: User's spoken query or command
            conversation_history: List of prior turns [{'role': 'user'|'model', 'content': '...'}]
            custom_system_instruction: Optional override for briefings or tasks
        """
        if not self.config.has_gemini() or self._client is None:
            return (
                "I am at your service, Sir, but my Gemini API key has not yet been configured in the environment file. "
                "Kindly add your GEMINI_API_KEY to the dot-env file so we may converse freely."
            )

        instruction = custom_system_instruction or ALFRED_SYSTEM_PROMPT

        # Build contents structure
        contents: List[types.Content] = []

        if conversation_history:
            for turn in conversation_history:
                role = "user" if turn.get("role") in ("user", "human") else "model"
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=turn.get("content", ""))],
                    )
                )

        # Add current user prompt
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)],
            )
        )

        model_name = self.config.gemini_model or "gemini-2.5-flash"

        try:
            config = types.GenerateContentConfig(
                system_instruction=instruction,
                temperature=0.7,
                max_output_tokens=600,
            )

            logger.info("Sending request to Gemini model %s...", model_name)
            response = self._client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )

            if response and response.text:
                return self.clean_for_speech(response.text)

            return "I am listening, Sir, though my thoughts momentarily escaped me. How else may I assist?"

        except Exception as e:
            err_str = str(e)
            logger.warning("Gemini API request error (%s): %s", model_name, err_str)

            # Check if model not found and try fallback to gemini-2.0-flash or gemini-1.5-flash
            if "not found" in err_str.lower() and model_name != "gemini-2.0-flash":
                try:
                    logger.info("Attempting fallback to gemini-2.0-flash...")
                    fallback_response = self._client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=contents,
                        config=types.GenerateContentConfig(system_instruction=instruction),
                    )
                    if fallback_response and fallback_response.text:
                        return self.clean_for_speech(fallback_response.text)
                except Exception as fallback_err:
                    logger.error("Fallback to gemini-2.0-flash also failed: %s", fallback_err)

            return (
                "My apologies, Sir. I encountered a momentary connection disturbance with the Gemini service. "
                "Perhaps we might try again in a moment."
            )

