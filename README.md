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

Every command also accepts `--provider`/`-P` to route the same request somewhere other than
Google's API:

| `--provider` | Where it runs | Auth | Models |
| --- | --- | --- | --- |
| `google` (default) | Google Gemini API directly | `GEMINI_KEY` (billed) | Gemini only |
| `tamu` | [TAMUS AI Chat](https://docs.tamus.ai/docs/prod/api-tool/) | `TAMUS_AI_CHAT_API_KEY` — free daily token allowance | Gemini (namespaced `protected.*`) |
| `tamu-gateway` | [TAMUS AI Gateway](https://docs.tamus.ai/api-services/gateway/) | `TAMUS_AI_FRAMEWORK_API_KEY` + Cloudflare WARP | Anything the Gateway lists — Anthropic Claude, Gemini, OpenAI GPT, etc. |

```bash
export TAMUS_AI_CHAT_API_KEY="your-tamus-ai-chat-api-key"
iiif-transcribe csv -p htrami_input.csv -o htr_ami_output.csv --model gemini-3.5-flash --provider tamu
```

#### `--provider tamu-gateway`

The [TAMUS AI Gateway](https://docs.tamus.ai/api-services/gateway/) is a separate service from
TAMUS AI Chat. It exposes every upstream provider's real API through one endpoint, has a much
larger token allowance, and — because it's not Gemini-only — lets you transcribe with **Anthropic
Claude, OpenAI GPT, or Gemini** models. Real authentication is handled by Cloudflare One / WARP
(which must be installed, connected to the `tamucs` team, and re-authenticated every 24h); the
"API key" is just your NetID or billing-group name and is not secret.

```bash
export TAMUS_AI_FRAMEWORK_API_KEY="your-netid-or-billing-group"
# Optional: override the per-institution endpoint (defaults to Texas A&M's, gateway.api.tamu.ai)
export TAMUS_AI_FRAMEWORK_API_ENDPOINT="https://gateway.api.tamu.ai"

# Gemini 3.5 Flash through the Gateway
iiif-transcribe csv -p htrami_input.csv -o htr_ami_output.csv -P tamu-gateway -m gemini-3.5-flash

# ...or Claude Haiku 4.5 instead
iiif-transcribe manifest -p fixtures/manifest.json -o out.json -P tamu-gateway -m claude-haiku-4-5
```

Pass the **bare `id`** from `GET {endpoint}/v1/models` as `--model` (e.g. `gemini-3.5-flash`,
`claude-haiku-4-5`, `claude-sonnet-4-6`, `gpt-5.1`) — *not* the `bedrock_id`, and with no
`protected.` prefix. There is no sensible default for this provider, so always pass `--model`.

Because the Gateway gives you far more headroom, `tamu` and `tamu-gateway` also accept two knobs
for spending it on deeper reasoning / longer output (ignored by `--provider google`):

| Option | Meaning |
| --- | --- |
| `-r` / `--reasoning_effort` | `low` \| `medium` (default) \| `high` — how much chain-of-thought the model does |
| `-x` / `--max_tokens` | Raise the response cap (reasoning + answer). Gateway limits: ~65K for Gemini, ~128K for Claude |

```bash
iiif-transcribe csv -p htrami_input.csv -o out.csv -P tamu-gateway -m gemini-3.5-flash -r high -x 32000
```

See [Configuration](#configuration) below for details and caveats on each provider.

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

For `--provider tamu-gateway`, follow the [TAMUS AI Gateway setup](https://docs.tamus.ai/api-services/gateway/):
install the [Cloudflare One client](https://developers.cloudflare.com/cloudflare-one/team-and-resources/devices/cloudflare-one-client/download/),
connect it to team `tamucs`, then set your NetID or billing-group name as the key. This value is
**not sensitive** — Cloudflare handles authentication, and the connection must be re-authenticated
every 24h.

```bash
export TAMUS_AI_FRAMEWORK_API_KEY="your-netid-or-billing-group"
# Optional: override the per-institution endpoint (defaults to Texas A&M's, gateway.api.tamu.ai)
export TAMUS_AI_FRAMEWORK_API_ENDPOINT="https://gateway.api.tamu.ai"
```

List the available model ids (and check your usage at <https://report.api.tamu.ai/>):

```bash
curl -s "$TAMUS_AI_FRAMEWORK_API_ENDPOINT/v1/models" \
  -H "Authorization: Bearer $TAMUS_AI_FRAMEWORK_API_KEY" | jq '.data[].id'
```

**Caveats on `--provider tamu-gateway`**: the Gateway has no `protected.` namespacing — pass the
bare `id` and always pass `--model` (the Gemini default won't resolve). Reasoning-trace support
depends on the chosen model: Gemini behaves like `--provider tamu` (trace in `reasoning_content`,
`reasoning_effort` always sent); for Claude/GPT models the trace may not be surfaced, in which case
`annotations.reasoning` falls back to the "no reasoning trace was returned" note and the
transcription is unaffected.

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
