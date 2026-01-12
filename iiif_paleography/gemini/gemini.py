from google import genai
from google.genai import types
import PIL.Image
import os
import requests
from io import BytesIO


class GeminiTranscriber:
    def __init__(self, api_key=None, model="gemini-3-pro-preview", prompt_path='prompts/gemini-htr.md'):
        """
        Initialize the Gemini transcriber.

        Args:
            api_key: API key for Gemini. If None, reads from GEMINI_KEY environment variable.
            model: The Gemini model to use.
            prompt_path: Path to the prompt file.
        """
        self.api_key = api_key or os.getenv("GEMINI_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model = model
        self.prompt_path = prompt_path
        self.prompt = self._load_prompt()

    def _load_prompt(self):
        """Load the prompt from file."""
        with open(self.prompt_path, 'r') as f:
            return f.read()

    def transcribe(self, image_path, temperature=0.7, include_thoughts=True):
        """
        Transcribe an image using Gemini.

        Args:
            image_path: Path to the image file or URL to a remote image.
            temperature: Temperature for generation.
            include_thoughts: Whether to include thought process in response.

        Returns:
            The API response object.
        """
        if image_path.startswith(('http://', 'https://')):
            response = requests.get(image_path)
            response.raise_for_status()
            img = PIL.Image.open(BytesIO(response.content))
        else:
            img = PIL.Image.open(image_path)

        response = self.client.models.generate_content(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=self.prompt,
                temperature=temperature,
                thinking_config=types.ThinkingConfig(
                    include_thoughts=include_thoughts
                ),
            ),
            contents=[
                "Please transcribe the following image according to the established guidelines:",
                img
            ]
        )

        return response

    def print_response(self, response):
        """Print the response in a formatted way."""
        for part in response.candidates[0].content.parts:
            if part.thought:
                print(f"--- THOUGHT PROCESS ---\n{part.text}\n")
            else:
                print(f"--- FINAL TRANSCRIPTION ---\n{part.text}")

    def get_response_dict(self, response):
        """
        Extract thought process and final transcription from response.

        Args:
            response: The API response object.

        Returns:
            dict: A dictionary with 'thought_process' and 'transcription' keys.

        Raises:
            ValueError: If the response is invalid or empty.
        """
        result = {
            'thought_process': '',
            'transcription': ''
        }

        if not response.candidates or len(response.candidates) == 0:
            raise ValueError(f"No candidates in response. Response: {response}")

        if not hasattr(response.candidates[0], 'content') or response.candidates[0].content is None:
            raise ValueError(f"No content in response candidate. Response: {response}")

        if not hasattr(response.candidates[0].content, 'parts') or response.candidates[0].content.parts is None:
            raise ValueError(f"No parts in response content. Response: {response}")

        for part in response.candidates[0].content.parts:
            if part.thought:
                result['thought_process'] = part.text
            else:
                result['transcription'] = part.text

        return result


if __name__ == "__main__":
    transcriber = GeminiTranscriber()
    # image_path = '/Users/mark.baggett/Desktop/gemini_sample2_1.jpg'
    image_path = "https://api-pre.library.tamu.edu/iiif/2/558c93e3-7fd3-388c-8114-08d20a9e47b0/full/full/0/default.jpg"
    response = transcriber.transcribe(image_path)
    print(transcriber.get_response_dict(response))
