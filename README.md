# IIIF Paleography

A tool for transcribing handwritten text in IIIF manifests using Google Gemini AI. This project automatically adds 
HTR (Handwritten Text Recognition) annotations to IIIF Presentation API v3 manifests, including both transcriptions 
and the AI's reasoning process.

It is highly influenced by the work of [Ben](https://github.com/benwbrum) and [Sara](https://github.com/saracarl) and
[FromthePage](https://github.com/benwbrum/fromthepage).

**Note**: This is a work in progress.

Example output looks like this:

[View Example in Clover](https://samvera-labs.github.io/clover-iiif/docs/viewer/demo?iiif-content=https%3A%2F%2Ftamulib-dc-labs.github.io%2Fcustom-iiif-manifests%2Fmanifests%2Fmcinnis-39-v3-htr.json)

## Todo

* [x] Generate Transcription and Reasoning with Gemini.
* [x] Add Transcription and Reasoning to a Single v3 Manifest.
* [x] Upgrade (parts of a) v2 manifest to v3 so I can use iiif_prezi3.
* [x] Init CLI utility.
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

### Running from Command Line

Generate transcription and annotations for a single manifest online and update its identifier:

```bash
iiif-transcribe manifest -p "https://api-pre.library.tamu.edu/iiif-service/fedora/presentation/bb/
97/f2/3e/bb97f23e-803a-4bd6-8406-06802623554c/mcinnis_objects/241" -o "fixtures/mcinnis-241.json" -n "https://tamulib-dc-labs.github.io/custom-iiif-manifests/manifests/mcinnis-241.json" 
```

Or update a manifest on disk:

```bash
iiif-transcribe manifest -p fixtures/manifest.json -o "fixtures/mcinnis-241.json" -n "https://tamulib-dc-labs.github.io/custom-iiif-manifests/manifests/mcinnis-241.json" 
```

Or run the transcriber directly:

```bash
python -m iiif_paleography.gemini.gemini
```

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
from iiif_paleography.transcribe import ManifestHTRBuilder
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

## Configuration

Set your Gemini API key as an environment variable:

```bash
export GEMINI_KEY="your-api-key-here"
```

## Notes

- This is an experimental project for quickly transcribing handwritten text
- The quality of transcriptions depends on the Gemini model and prompt configuration
- Processing large manifests may take time as each canvas is transcribed individually
