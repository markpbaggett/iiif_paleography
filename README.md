# IIIF Paleography

A tool for transcribing handwritten text in IIIF manifests using Google Gemini AI. This project automatically adds 
HTR (Handwritten Text Recognition) annotations to IIIF Presentation API v3 manifests, including both transcriptions 
and the AI's reasoning process.

It is highly influenced by the work of [Ben](https://github.com/benwbrum) and [Sara](https://github.com/saracarl) and
[FromthePage](https://github.com/benwbrum/fromthepage).

**Note**: This is a work in progress.

Example output looks like this:

[View Example in Theseus](https://tamulib-dc-labs.github.io/custom-iiif-manifests/manifests/mcinnis-39-v3-htr.json)

## Todo

* [x] Generate Transcription and Reasoning with Gemini.
* [x] Add Transcription and Reasoning to a Single v3 Manifest.
* [x] Upgrade (parts of a) v2 manifest to v3 so I can use iiif_prezi3.
* [ ] Create Full CLI utility.
* [ ] Run over a IIIF collection of manifests.
* [ ] Run over a directory of manifests.

## Installation

This project uses Poetry for dependency management.

```bash
poetry install
```

## Requirements

- Python 3.12+
- Google Gemini API key (set as `GEMINI_KEY` environment variable)
- Dependencies:
  - `google-genai`
  - `iiif-prezi3`
  - `Pillow`
  - `requests`

## Usage

### GeminiTranscriber

```python
from iiif_paleography.gemini import GeminiTranscriber

# Initialize transcriber
transcriber = GeminiTranscriber()

# Transcribe from local file
response = transcriber.transcribe('/path/to/image.jpg')

# Or transcribe from URL
response = transcriber.transcribe('https://example.com/image.jpg')

# Get results as dictionary
result = transcriber.get_response_dict(response)
print(result['transcription'])
print(result['thought_process'])
```

### ManifestHTRBuilder

```python
from iiif_paleography.iiif_paleography import ManifestHTRBuilder
import json

# Load a IIIF v3 manifest
with open('fixtures/manifest.json', 'r') as f:
    manifest_data = json.load(f)

# Build HTR-enriched manifest
builder = ManifestHTRBuilder(manifest_data, new_id="https://example.org/new-manifest")
manifest = builder.build_htr()

# Save to file
with open('output.json', 'w') as f:
    f.write(manifest.json(indent=4))
```

### Running from Command Line

```bash
# Run the main script
python -m iiif_paleography.iiif_paleography

# Run the transcriber directly
python -m iiif_paleography.gemini.gemini
```

## Configuration

Set your Gemini API key as an environment variable:

```bash
export GEMINI_KEY="your-api-key-here"
```

## Notes

- This is an experimental project for quickly transcribing handwritten text
- The quality of transcriptions depends on the Gemini model and prompt configuration
- Processing large manifests may take time as each canvas is transcribed individually
