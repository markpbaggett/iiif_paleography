import base64
import mimetypes
import os

import requests

DEFAULT_ENDPOINT = "https://chat-api.tamu.ai"


# Module-level constants used by translate_text().
_DEFAULT_TRANSLATE_PROMPT_PATH = "prompts/gemini-translate.md"


class TamuChatTranscriber:
    """
    Transcribes images through TAMUS AI Chat's OpenAI-compatible API
    (https://docs.tamus.ai/docs/prod/api-tool/) instead of calling Google's
    Gemini API directly -- usage draws from the free daily TAMUS AI Chat
    token allowance instead of a billed Gemini API key.

    Same transcribe()/get_response_dict() interface as GeminiTranscriber so
    it's a drop-in replacement.

    Gemini's thinking trace is billed (reasoning tokens show up in the usage
    block) even when not requested, but chat-api.tamu.ai only puts it in the
    response when the request includes `reasoning_effort` ("low"/"medium"/
    "high") -- confirmed via TAMU's own testing. Without it, `reasoning_content`
    comes back empty even though the model reasoned. This client always sends
    `reasoning_effort` (see `reasoning_effort` param) and reads the trace back
    from `reasoning_content` (falling back to `reasoning` for other proxies).

    Caveat: model ids on TAMUS AI Chat are namespaced (e.g.
    "protected.gemini-3.5-flash"); a bare model name is prefixed with
    "protected." here. Confirm the exact id for your model via
    GET {endpoint}/api/models if a run 404s/400s on the model.
    """

    # Overridable by subclasses that target a different TAMUS API surface.
    DEFAULT_ENDPOINT = DEFAULT_ENDPOINT
    CHAT_COMPLETIONS_PATH = "/api/chat/completions"
    MODEL_PREFIX = "protected."
    ENV_API_KEY = ("TAMUS_AI_CHAT_API_KEY", "TAMU_CHAT")
    ENV_ENDPOINT = "TAMUS_AI_CHAT_API_ENDPOINT"

    def __init__(self, api_key=None, endpoint=None, model="gemini-3.5-flash",
                 prompt_path='prompts/gemini-htr.md', width=None, height=None,
                 reasoning_effort="medium", max_tokens=None,
                 translate_prompt_path=_DEFAULT_TRANSLATE_PROMPT_PATH):
        self.width = width
        self.height = height
        self.api_key = api_key or next(
            (os.getenv(name) for name in self.ENV_API_KEY if os.getenv(name)), None
        )
        self.endpoint = (
            endpoint or os.getenv(self.ENV_ENDPOINT) or self.DEFAULT_ENDPOINT
        ).rstrip('/')
        self.model = model if not self.MODEL_PREFIX or model.startswith(self.MODEL_PREFIX) \
            else f"{self.MODEL_PREFIX}{model}"
        self.prompt_path = prompt_path
        self.reasoning_effort = reasoning_effort
        self.max_tokens = max_tokens
        self.prompt = self._load_prompt()
        self._translate_prompt_path = translate_prompt_path
        self._translate_prompt = None

    def _load_prompt(self):
        """Load the prompt from file."""
        with open(self.prompt_path, 'r') as f:
            return f.read()

    def _prepare_prompt(self):
        """Prepare prompt, replacing dimension placeholders if needed."""
        prompt = self.prompt
        if 'gemini-htr-and-coords.md' in self.prompt_path:
            prompt = prompt.replace('INSERT_WIDTH', str(self.width))
            prompt = prompt.replace('INSERT_HEIGHT', str(self.height))
        return prompt

    def _load_image(self, image_path):
        if image_path.startswith(('http://', 'https://')):
            r = requests.get(image_path)
            r.raise_for_status()
            content_type = r.headers.get('Content-Type', 'image/jpeg').split(';')[0]
            return r.content, content_type
        with open(image_path, 'rb') as f:
            data = f.read()
        content_type = mimetypes.guess_type(image_path)[0] or 'image/jpeg'
        return data, content_type

    def transcribe(self, image_path, temperature=0.7, include_thoughts=True):
        """
        Transcribe an image via TAMUS AI Chat.

        Args:
            image_path: Path to the image file or URL to a remote image.
            temperature: Temperature for generation.
            include_thoughts: Whether to ask for a reasoning trace back (sends
                `reasoning_effort`). Without this, chat-api.tamu.ai returns an
                empty `reasoning_content` even though the model still reasons.

        Returns:
            The parsed JSON response body (dict).
        """
        image_bytes, content_type = self._load_image(image_path)
        b64_image = base64.b64encode(image_bytes).decode('utf-8')
        prepared_prompt = self._prepare_prompt()

        payload = {
            "model": self.model,
            "stream": False,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": prepared_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please transcribe the following image according to the established guidelines:",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{content_type};base64,{b64_image}"},
                        },
                    ],
                },
            ],
        }
        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens
        if include_thoughts:
            thinking = self._thinking_payload()
            # An explicit thinking config and `reasoning_effort` are mutually
            # exclusive on some backends (the Gateway 400s on both) -- prefer the
            # explicit one when a subclass provides it.
            if thinking:
                payload.update(thinking)
            else:
                payload["reasoning_effort"] = self.reasoning_effort

        response = requests.post(
            f"{self.endpoint}{self.CHAT_COMPLETIONS_PATH}",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if not response.ok:
            raise requests.HTTPError(
                f"{response.status_code} from {response.url}: {response.text}",
                response=response,
            )
        return response.json()

    def _thinking_payload(self):
        """
        Extra request fields needed to get a *readable* reasoning trace back.
        chat-api.tamu.ai surfaces it in `reasoning_content` from `reasoning_effort`
        alone, so nothing extra is needed here. Subclasses override.
        """
        return {}

    def print_response(self, response):
        """Print the response in a formatted way."""
        result = self.get_response_dict(response)
        if result['thought_process']:
            print(f"--- THOUGHT PROCESS ---\n{result['thought_process']}\n")
        print(f"--- FINAL TRANSCRIPTION ---\n{result['transcription']}")

    def get_response_dict(self, response):
        """
        Extract thought process and final transcription from response.

        Args:
            response: The parsed JSON response body from transcribe().

        Returns:
            dict: A dictionary with 'thought_process' and 'transcription' keys.

        Raises:
            ValueError: If the response has no choices.
        """
        result = {
            'thought_process': '',
            'transcription': ''
        }

        choices = response.get('choices')
        if not choices:
            raise ValueError(f"No choices in response. Response: {response}")

        message = choices[0].get('message', {}) or {}
        content = message.get('content') or ''
        reasoning = message.get('reasoning_content') or message.get('reasoning') or ''

        # Some proxies (e.g. the TAMUS AI Gateway with Gemini `include_thoughts`)
        # don't populate `reasoning_content` -- they inline the thought summary at
        # the front of `content` wrapped in <think>...</think>. Split it back out.
        if not reasoning and '<think>' in content:
            after_open = content.split('<think>', 1)[1]
            if '</think>' in after_open:
                reasoning, content = after_open.split('</think>', 1)
            else:  # trace got truncated before the closing tag
                reasoning, content = after_open, ''
            reasoning, content = reasoning.strip(), content.strip()

        result['transcription'] = content
        result['thought_process'] = reasoning

        return result

    def _load_translate_prompt(self):
        """Load the system prompt for translation if not already cached."""
        if self._translate_prompt is None:
            with open(self._translate_prompt_path, 'r') as f:
                self._translate_prompt = f.read()
        return self._translate_prompt

    def translate_text(self, text: str) -> str:
        """
        Translate *text* to English via the TAMUS AI Chat API.

        Args:
            text: The text to translate (may contain HTML markup).

        Returns:
            The translated text as a plain string, or an empty string if
            translation could not be performed.
        """
        if not text:
            return ""
        try:
            response = requests.post(
                f"{self.endpoint}{self.CHAT_COMPLETIONS_PATH}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "stream": False,
                    "temperature": 0.3,
                    "messages": [
                        {"role": "system", "content": self._load_translate_prompt()},
                        {"role": "user", "content": text},
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
            if data.get('choices') and data['choices'][0].get('message', {}).get('content'):
                return data['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"Warning: translation failed: {e}")
        return ""


if __name__ == "__main__":
    transcriber = TamuChatTranscriber()
    image_path = "https://api-pre.library.tamu.edu/iiif/2/5349c9b2-c7d0-3b9c-a6d5-7a3adeb698e2/full/564,/0/default.jpg"
    response = transcriber.transcribe(image_path)
    print(transcriber.get_response_dict(response))
