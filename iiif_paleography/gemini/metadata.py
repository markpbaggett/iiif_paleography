import os
from google import genai
from google.genai import types
from toon_format import decode
import PIL.Image
import requests
from io import BytesIO


class GeminiMetadata:
    def __init__(self, api_key=None, model="gemini-3.1-pro-preview", prompt_path='prompts/gemini-metadata.md'):
        self.api_key = api_key or os.getenv("GEMINI_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model = model
        self.prompt_path = prompt_path
        self.prompt = self._load_prompt()

    def _load_prompt(self):
        """Load the prompt from file."""
        with open(self.prompt_path, 'r') as f:
            return f.read()

    def generate_metadata(self, transcription_text=None, image_url=None):
        """
        Takes raw text or an image URL and returns a structured Python dictionary.
        """
        if not transcription_text and not image_url:
            raise ValueError("Must provide either transcription_text or image_url")

        if image_url:
            r = requests.get(image_url)
            r.raise_for_status()
            img = PIL.Image.open(BytesIO(r.content))
            contents = ["Please analyze the following image:", img]
        else:
            contents = [f"Transcription to analyze:\n\n{transcription_text}"]

        response = self.client.models.generate_content(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=self.prompt,
                temperature=0.1,
            ),
            contents=contents
        )

        toon_string = response.text.strip()
        try:
            return decode(toon_string)
        except Exception as e:
            print(f"Parsing Error: {e}")
            return {"error": "Failed to parse TOON", "raw": toon_string}


# Example Usage
if __name__ == "__main__":
    raw_text = """
EXECUTIVE DEPARTMENT
Office of Comptroller,
W. J. SWAIN, COMPTROLLER.
JOHN D. McCALL, CHIEF CLERK.
Austin, Sept 18 1885

Prof L. L. McInnis
College. Station.
Texas

Dear Sir:
Your letter came yesterday
and I enclose Drft on N.Y. for
Amt your 1st Qr - $55.00 -

Glad to hear Hal is moving
off well. I have written
him to go to you for his in
struction and advice -

Many thanks for kind interest
you have manifested. He writes
that you have been especially
kind to him -

Truly -
W. J. Swain
    """
    meta_engine = GeminiMetadata()
    metadata = meta_engine.generate_metadata(transcription_text=raw_text)
    print(metadata)
    # meta_engine = GeminiMetadata(prompt_path='prompts/gemini-map.md')
    # metadata = meta_engine.generate_metadata(image_url="https://api-pre.library.tamu.edu/iiif/2/aHR0cHM6Ly9hcGktcHJlLmxpYnJhcnkudGFtdS5lZHUvZmNyZXBvL3Jlc3QvYmF0Y2gtc2VydmljZS1tYXBzLXRlc3RzX29iamVjdHMvMTE2L3BhZ2VzL3BhZ2VfMC9maWxlcy9zZXJ2aWNlX21hcHNfMDExNV8wMDAxLmpwMg==/full/870,/0/default.jpg")
    # print(metadata)