import base64
import mimetypes
import os

import requests

DEFAULT_ENDPOINT = "https://chat-api.tamu.ai"


class TamuChatTranscriber:
    """
    Transcribes images through TAMUS AI Chat's OpenAI-compatible API
    (https://docs.tamus.ai/docs/prod/api-tool/) instead of calling Google's
    Gemini API directly -- usage draws from the free daily TAMUS AI Chat
    token allowance instead of a billed Gemini API key.

    Same transcribe()/get_response_dict() interface as GeminiTranscriber so
    it's a drop-in replacement.

    Caveats (unverified -- built from docs text, not a live test against a
    real API key):
      * Model ids on TAMUS AI Chat are namespaced (the docs' only example is
        "protected.gemini-2.5-flash-lite"); a bare model name is prefixed
        with "protected." here. Confirm the exact id for your model via
        GET {endpoint}/api/models before relying on it.
      * TAMUS AI Chat's own FAQ says only Claude models show a visible
        "thinking" trace in the UI. It's unconfirmed whether Gemini routed
        through this gateway returns separate reasoning content over the
        API the way Google's native API does with `thinking_config`. This
        client looks for `reasoning_content`/`reasoning` on the response
        message and leaves `thought_process` empty if neither is present,
        rather than guessing.
    """

    def __init__(self, api_key=None, endpoint=None, model="gemini-3.5-flash",
                 prompt_path='prompts/gemini-htr.md', width=None, height=None):
        self.width = width
        self.height = height
        self.api_key = api_key or os.getenv("TAMUS_AI_CHAT_API_KEY") or os.getenv("TAMU_CHAT")
        self.endpoint = (endpoint or os.getenv("TAMUS_AI_CHAT_API_ENDPOINT") or DEFAULT_ENDPOINT).rstrip('/')
        self.model = model if model.startswith("protected.") else f"protected.{model}"
        self.prompt_path = prompt_path
        self.prompt = self._load_prompt()

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
            include_thoughts: Unused -- kept for interface parity with
                GeminiTranscriber; TAMUS AI Chat's reasoning-trace support
                (if any) isn't a request-time toggle in the documented API.

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

        response = requests.post(
            f"{self.endpoint}/api/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        return response.json()

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
        result['transcription'] = message.get('content') or ''
        result['thought_process'] = message.get('reasoning_content') or message.get('reasoning') or ''

        return result


if __name__ == "__main__":
    transcriber = TamuChatTranscriber()
    image_path = "https://api-pre.library.tamu.edu/iiif/2/5349c9b2-c7d0-3b9c-a6d5-7a3adeb698e2/full/564,/0/default.jpg"
    response = transcriber.transcribe(image_path)
    print(transcriber.get_response_dict(response))
