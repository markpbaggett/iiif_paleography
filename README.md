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

Generate an Archipelago AMI-ready CSV from a CSV of manifests. The input CSV needs
a `manifest` column (a URL or local path to a IIIF manifest); every other column
is copied through as-is. The output CSV drops `manifest` and adds
`generative_ai_details` (when it ran, the model used, and the app version) and
`annotations` (the reasoning and transcription for each canvas), both JSON-encoded
using the `"`-escaped serialization Archipelago's PHP CSV parser requires:

```bash
iiif-transcribe csv -p htrami_input.csv -o htr_ami_output.csv
```

The command is resume-safe: if `--output` already exists, rows already present
(matched by `node_uuid`, falling back to `label`) are skipped and the file is
rewritten after every new row, so an interrupted run can just be restarted.

Every command (`manifest`, `list`, `csv`) accepts `--model`/`-m` to pick the Gemini
model, defaulting to `gemini-3.1-pro-preview`. Pass a faster/cheaper alternative
like `gemini-3.5-flash`:

```bash
iiif-transcribe csv -p htrami_input.csv -o htr_ami_output.csv --model gemini-3.5-flash
```

Every command also accepts `--provider`/`-P` (`google`, the default, or `tamu`) to route the same
model through [TAMUS AI Chat](https://docs.tamus.ai/docs/prod/api-tool/) instead of Google's API
directly, which draws from TAMUS AI Chat's free daily token allowance instead of billing a Gemini
API key:

```bash
export TAMUS_AI_CHAT_API_KEY="your-tamus-ai-chat-api-key"
iiif-transcribe csv -p htrami_input.csv -o htr_ami_output.csv --model gemini-3.5-flash --provider tamu
```

See [Configuration](#configuration) below for how to get a `TAMUS_AI_CHAT_API_KEY`, and the one
remaining caveat on `--provider tamu` (namespaced model ids).

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

For `--provider tamu`, set your [TAMUS AI Chat](https://docs.tamus.ai/docs/prod/api-tool/) API key
instead (get one by following [Create and Test API Key](https://docs.tamus.ai/docs/prod/api-tool/create-and-test-api-key),
which needs your TAMU institutional login):

```bash
export TAMUS_AI_CHAT_API_KEY="your-tamus-ai-chat-api-key"
# Optional: override the per-institution endpoint (defaults to Texas A&M's, chat-api.tamu.ai)
export TAMUS_AI_CHAT_API_ENDPOINT="https://chat-api.tamu.ai"
```

`TAMU_CHAT` also works as the API key variable, if that's what you already have it set to.

**Reasoning trace via `--provider tamu`**: chat-api.tamu.ai only returns Gemini's thinking trace
(in `reasoning_content`) when the request includes `reasoning_effort` — Gemini still reasons
without it (reasoning tokens are billed either way), the trace just isn't surfaced. This client
always sends `reasoning_effort="medium"`, so `annotations.reasoning` is populated the same as with
`--provider google`. If a canvas still comes back with an empty trace (e.g. the endpoint or model
doesn't support it), `reasoning` falls back to a plain "no reasoning trace was returned" note
instead of an empty/misleading value — the transcription itself is unaffected either way.

**Other caveat on `--provider tamu`**: model ids on TAMUS AI Chat are namespaced (e.g.
`protected.gemini-3.5-flash`); a bare `--model` value gets `protected.` prefixed automatically.
Confirm the exact id for a given model with `GET {endpoint}/api/models` if a run fails with a
model-not-found error.

## Notes

- This is an experimental project for quickly transcribing handwritten text
- The quality of transcriptions depends on the Gemini model and prompt configuration
- Processing large manifests may take time as each canvas is transcribed individually
