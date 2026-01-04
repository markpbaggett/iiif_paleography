from google import genai
from google.genai import types
import PIL.Image
import os

client = genai.Client(api_key=os.getenv("GEMINI_KEY"))

with open('prompts/gemini-htr.md', 'r') as f:
    prompt = f.read()

img = PIL.Image.open('/Users/mark.baggett/Desktop/gemini_sample2_1.jpg')

response = client.models.generate_content(
    model="gemini-3-pro-preview",
    config=types.GenerateContentConfig(
        system_instruction=prompt,
        temperature=0.7,
        thinking_config=types.ThinkingConfig(
            include_thoughts=True
        ),
    ),
    contents=[
        "Please transcribe the following image according to the established guidelines:",
        img
    ]
)

for part in response.candidates[0].content.parts:
    if part.thought:
        print(f"--- THOUGHT PROCESS ---\n{part.text}\n")
    else:
        print(f"--- FINAL TRANSCRIPTION ---\n{part.text}")
