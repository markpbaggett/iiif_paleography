from iiif_paleography.tamu_chat.client import TamuChatTranscriber

DEFAULT_ENDPOINT = "https://gateway.api.tamu.ai"


class TamuGatewayTranscriber(TamuChatTranscriber):
    """
    Transcribes images through the TAMUS AI Gateway
    (https://docs.tamus.ai/api-services/gateway/) instead of TAMUS AI Chat.

    The Gateway exposes each upstream provider's real API. This client uses the
    OpenAI-compatible chat completions surface (`/v1/chat/completions`), so the
    request/response handling is identical to TamuChatTranscriber -- only the
    endpoint, path, model id namespacing, and auth token differ.

    Differences from TamuChatTranscriber:

    * Endpoint is the institution's Gateway URL (see
      https://docs.tamus.ai/api-services/gateway/api-endpoints). Default here is
      https://gateway.api.tamu.ai -- override with TAMUS_AI_FRAMEWORK_API_ENDPOINT
      for other System members.
    * The "API key" is your billing-group name or NetID, NOT a secret -- real
      auth is handled by Cloudflare One / WARP, which must be connected and
      re-authenticated every 24h. Set it via TAMUS_AI_FRAMEWORK_API_KEY.
    * Model ids are the bare `id` values listed by GET {endpoint}/v1/models,
      e.g. "claude-haiku-4-5" or "gemini-3.5-flash" (NOT the `bedrock_id`).
      There is no "protected." prefix, so pass an explicit --model; the Gemini
      default from transcribe.py may not resolve here.
    """

    DEFAULT_ENDPOINT = DEFAULT_ENDPOINT
    CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
    MODEL_PREFIX = ""
    ENV_API_KEY = ("TAMUS_AI_FRAMEWORK_API_KEY",)
    ENV_ENDPOINT = "TAMUS_AI_FRAMEWORK_API_ENDPOINT"

    # reasoning_effort -> Gemini `thinking_budget` (tokens). The Gateway needs an
    # explicit budget + include_thoughts to return a readable trace; `reasoning_effort`
    # alone just spends reasoning tokens silently.
    _GEMINI_THINKING_BUDGET = {"low": 4096, "medium": 12288, "high": 24576}

    def _thinking_payload(self):
        """
        For Gemini models, ask the Gateway to return the thought *summary*.

        Without `include_thoughts` the Gateway drops the trace entirely (Gemini 3.x
        only emits an opaque encrypted `thought_signature`); with it, the summary is
        inlined into `content` as <think>...</think>, which get_response_dict splits
        back out. Claude/GPT models return `reasoning_content` natively, so this only
        touches Gemini.
        """
        if "gemini" not in self.model.lower():
            return {}
        budget = self._GEMINI_THINKING_BUDGET.get(self.reasoning_effort, 12288)
        return {
            "extra_body": {
                "google": {
                    "thinking_config": {
                        "include_thoughts": True,
                        "thinking_budget": budget,
                    }
                }
            }
        }


if __name__ == "__main__":
    transcriber = TamuGatewayTranscriber(model="claude-haiku-4-5")
    image_path = "https://api-pre.library.tamu.edu/iiif/2/5349c9b2-c7d0-3b9c-a6d5-7a3adeb698e2/full/564,/0/default.jpg"
    response = transcriber.transcribe(image_path)
    print(transcriber.get_response_dict(response))
