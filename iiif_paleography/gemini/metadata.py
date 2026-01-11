import os
from google import genai
from google.genai import types
from toon_format import decode


class GeminiMetadata:
    def __init__(self, api_key=None, model="gemini-3-pro-preview"):
        self.api_key = api_key or os.getenv("GEMINI_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model = model
        self.prompt = self._load_prompt()

    def _load_prompt(self):
        """Load the prompt from file."""
        with open("prompts/gemini-metadata.md", 'r') as f:
            return f.read()

    def generate_metadata(self, transcription_text):
        """
        Takes raw text and returns a structured Python dictionary.
        """

        response = self.client.models.generate_content(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=self.prompt,
                temperature=0.1,
            ),
            contents=[f"Transcription to analyze:\n\n{transcription_text}"]
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
    metadata = meta_engine.generate_metadata(raw_text)
    print(metadata)