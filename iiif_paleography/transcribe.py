from iiif_prezi3 import Manifest
from iiif_paleography import __version__
from iiif_paleography.gemini import GeminiTranscriber
from iiif_paleography.tamu_chat import TamuChatTranscriber
from iiif_paleography.tamu_gateway import TamuGatewayTranscriber
from iiif_paleography.iiif import IIIFv2tov3Converter
from iiif_paleography.translate import detect_language, translate_with_transcriber
import json
import csv
import os
import click
import requests
from tqdm import tqdm
from pathlib import Path
from toon_format import decode
from datetime import datetime, timezone


DEFAULT_MODEL = "gemini-3.1-pro-preview"
PROVIDERS = {
    "google": GeminiTranscriber,
    "tamu": TamuChatTranscriber,
    "tamu-gateway": TamuGatewayTranscriber,
}

NO_REASONING_NOTE = "_No reasoning trace was returned for this canvas._"


def _create_transcriber(canvas, with_coords=False, model=None, provider="google",
                        reasoning_effort=None, max_tokens=None):
    model = model or DEFAULT_MODEL
    transcriber_cls = PROVIDERS[provider]
    kwargs = {"model": model}
    if provider != "google":
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
    if with_coords:
        kwargs["prompt_path"] = 'prompts/gemini-htr-and-coords.md'
        kwargs["width"] = str(canvas.items[0].items[0].body.width)
        kwargs["height"] = str(canvas.items[0].items[0].body.height)
    return transcriber_cls(**kwargs)


def _get_image_url(canvas, with_coords=False):
    url = canvas.items[0].items[0].body.id
    if with_coords:
        url = url.replace('full/full', 'full/pct:25')
    return url


def safe_json(obj):
    """
    Serialize to JSON without \\" sequences that confuse PHP's fgetcsv.
    Uses \\u0022 (Unicode escape for ") instead -- json_decode restores it.
    """
    return json.dumps(obj).replace('\\"', '\\u0022')


class ManifestHTRBuilder:
    def __init__(self, manifest: Manifest, new_id=None, new_base="https://example.org",
                 nuke_tamu=False, with_coords=False, model=None, provider="google",
                 reasoning_effort=None, max_tokens=None, with_translations=False):
        self.manifest_data = manifest
        self.new_id = new_id if new_id else self.manifest_data.get("id", self.manifest_data.get("@id"))
        self.new_base = new_base
        self.nuke = nuke_tamu
        self.with_coords = with_coords
        self.model = model or DEFAULT_MODEL
        self.provider = provider
        self.reasoning_effort = reasoning_effort
        self.max_tokens = max_tokens
        self.with_translations = with_translations

    def _convert_if_v2(self):
        if '@id' in self.manifest_data:
            converter = IIIFv2tov3Converter(
                v2_manifest=self.manifest_data,
                manifest_id=self.new_id,
            )
            self.manifest_data = converter.convert()

    def _create_transcriber(self, canvas):
        return _create_transcriber(canvas, with_coords=self.with_coords, model=self.model, provider=self.provider,
                                   reasoning_effort=self.reasoning_effort, max_tokens=self.max_tokens)

    def _get_image_url(self, canvas):
        return _get_image_url(canvas, with_coords=self.with_coords)

    def _add_transcription_annotations(self, canvas, response, transcriber):
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if self.with_coords:
            word_coords = decode(response['transcription'])
            for coord in word_coords:
                canvas.make_annotation(
                    motivation="tagging",
                    purpose="transcribing",
                    creator=self.model,
                    created=timestamp,
                    generator="iiif-paleography@v0.1.0",
                    generated=timestamp,
                    body={
                        "type": "TextualBody",
                        "language": "en",
                        "format": "text/plain",
                        "purpose": "transcribing",
                        "value": coord['raw']
                    },
                    target=f"{canvas.id}#xywh={coord['x']},{coord['y']},{coord['w']},{coord['h']}",
                )
        else:
            canvas.make_annotation(
                motivation="transcribing",
                purpose="transcribing",
                creator=self.model,
                created=timestamp,
                generator="iiif-paleography@v0.1.0",
                generated=timestamp,
                body={
                    "type": "TextualBody",
                    "language": "en",
                    "format": "text/html",
                    "purpose": "transcribing",
                    "value": f"<span>{response['transcription']}</span>"
                },
                target=canvas.id
            )
            if self.with_translations:
                self._add_translation_annotation(canvas, response, transcriber)

    def _add_translation_annotation(self, canvas, response, transcriber):
        """Add a translation annotation when the transcription is non-English."""
        transcription = response['transcription']
        lang = detect_language(transcription)
        if lang == "en":
            return
        translated = translate_with_transcriber(transcriber, transcription)
        if not translated:
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        canvas.make_annotation(
            motivation="translating",
            purpose="translating",
            creator=self.model,
            created=timestamp,
            generator="iiif-paleography@v0.1.0",
            generated=timestamp,
            body={
                "type": "TextualBody",
                "language": "en",
                "format": "text/html",
                "purpose": "translating",
                "value": f"{TRANSLATING_PREFIX}{translated}</span>"
            },
            target=canvas.id
        )

    def build_htr(self):
        self._convert_if_v2()
        manifest = Manifest(**self.manifest_data)
        if self.new_id:
            manifest.id = self.new_id
        if self.nuke:
            manifest.thumbnail[0].id = manifest.thumbnail[0].id.replace('!100,100', 'pct:25')

        for i, canvas in enumerate(tqdm(manifest.items)):
            try:
                transcriber = self._create_transcriber(canvas)
                image = self._get_image_url(canvas)
                if self.nuke:
                    canvas.label['none'][0] = f"Page {i}"

                api_response = transcriber.transcribe(image)
                response = transcriber.get_response_dict(api_response)
                self._add_transcription_annotations(canvas, response, transcriber)
                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                canvas.make_annotation(
                    motivation="commenting",
                    purpose="transcribing",
                    creator=self.model,
                    created=timestamp,
                    generator="iiif-paleography@v0.1.0",
                    generated=timestamp,
                    body={
                        "type": "TextualBody",
                        "language": "none",
                        "format": "text/markdown",
                        "value": response['thought_process'] or NO_REASONING_NOTE
                    },
                    target=canvas.id,
                )
            except Exception as e:
                print(f"\nError processing canvas {i} ({canvas.id}): {e}")
                print(f"Skipping this canvas and continuing...")
        return manifest


REASONING_PREFIX = "**<span><b>Reasoning</b></span>:**\n\n\n"
TRANSCRIBING_PREFIX = "<span><b>Transcription:</b><br/><br/>\n"
TRANSLATING_PREFIX = "<span><b>Translation:</b><br/><br/>\n"


class ManifestAnnotationsBuilder:
    """
    Transcribes every canvas of a manifest and returns the results as plain
    data: a single {"transcribing": [...], "reasoning": [...]} entry for the
    whole work, with one item per canvas (in canvas order) in each array.
    Used to populate an Archipelago AMI `annotations` column.
    """
    def __init__(self, manifest: Manifest, new_id=None, model=None, provider="google",
                 reasoning_effort=None, max_tokens=None, with_translations=False):
        self.manifest_data = manifest
        self.new_id = new_id if new_id else self.manifest_data.get("id", self.manifest_data.get("@id"))
        self.model = model or DEFAULT_MODEL
        self.provider = provider
        self.reasoning_effort = reasoning_effort
        self.max_tokens = max_tokens
        self.with_translations = with_translations

    def _convert_if_v2(self):
        if '@id' in self.manifest_data:
            converter = IIIFv2tov3Converter(
                v2_manifest=self.manifest_data,
                manifest_id=self.new_id,
            )
            self.manifest_data = converter.convert()

    def build_annotations(self):
        self._convert_if_v2()
        manifest = Manifest(**self.manifest_data)
        transcribing_items = []
        reasoning_items = []
        translating_items = []
        for i, canvas in enumerate(tqdm(manifest.items, leave=False)):
            try:
                transcriber = _create_transcriber(canvas, model=self.model, provider=self.provider,
                                                  reasoning_effort=self.reasoning_effort, max_tokens=self.max_tokens)
                image = _get_image_url(canvas)
                api_response = transcriber.transcribe(image)
                response = transcriber.get_response_dict(api_response)
                thought_process = response['thought_process'] or NO_REASONING_NOTE
                reasoning_items.append(
                    {"value": REASONING_PREFIX + thought_process, "mime_type": "text/markdown"}
                )
                transcribing_items.append(
                    {"value": TRANSCRIBING_PREFIX + response['transcription'] + "</span>", "mime_type": "text/html"}
                )
                if self.with_translations:
                    transcription = response['transcription']
                    lang = detect_language(transcription)
                    if lang != "en":
                        translated = translate_with_transcriber(transcriber, transcription)
                        if translated:
                            translating_items.append(
                                {"value": TRANSLATING_PREFIX + translated + "</span>", "mime_type": "text/html"}
                            )
                        else:
                            translating_items.append(
                                {"value": TRANSLATING_PREFIX + "_Translation failed._</span>", "mime_type": "text/html"}
                            )
                    else:
                        translating_items.append(
                            {"value": TRANSLATING_PREFIX + "_Already in English; no translation needed._</span>", "mime_type": "text/html"}
                        )
            except Exception as e:
                print(f"\nError processing canvas {i} ({canvas.id}): {e}")
                print(f"Inserting an error placeholder for this canvas and continuing...")
                error_note = f"_Error transcribing this canvas: {e}_"
                reasoning_items.append(
                    {"value": REASONING_PREFIX + error_note, "mime_type": "text/markdown"}
                )
                transcribing_items.append(
                    {"value": TRANSCRIBING_PREFIX + error_note + "</span>", "mime_type": "text/html"}
                )
                if self.with_translations:
                    translating_items.append(
                        {"value": TRANSLATING_PREFIX + error_note + "</span>", "mime_type": "text/html"}
                    )
        return [{"transcribing": transcribing_items, "reasoning": reasoning_items, "translating": translating_items}]


def load_manifest(path: str):
    """Load a manifest from a URL or local file path."""
    if path.startswith("https"):
        r = requests.get(path)
        if r.status_code != 200:
            raise click.ClickException(f"{r.status_code}: {r.text} on {path}")
        return r.json()
    with open(path, 'r') as f:
        return json.load(f)


def write_manifest(manifest, output: str):
    """Write a manifest to a JSON file."""
    with open(output, 'w') as f:
        json_obj = json.loads(manifest.json())
        f.write(json.dumps(json_obj, indent=4))
    print(f"HTR manifest written to {output}")


@click.group()
def cli() -> None:
    pass


@cli.command("manifest", help="Transcribe a single IIIF Manifest")
@click.option("--path", "-p", help="The path to the Manifest")
@click.option("--output", "-o", help="The output file path", default="fixtures/transcribed.json")
@click.option("--new_id", "-n", help="A new identifier for your manifest")
@click.option("--is_tamu", "-t", is_flag=True, help="Whether the manifest is from TAMU and needs to get gross stuff purged")
@click.option("--with_coords", "-c", is_flag=True, help="Include coordinate annotations")
@click.option("--model", "-m", default=None, help=f"Gemini model to use (default: {DEFAULT_MODEL}), e.g. gemini-3.5-flash")
@click.option("--provider", "-P", type=click.Choice(list(PROVIDERS.keys())), default="google",
              help="Where to run the model: 'google' calls the Gemini API directly; "
                   "'tamu' routes through TAMUS AI Chat (needs TAMUS_AI_CHAT_API_KEY); "
                   "'tamu-gateway' routes through the TAMUS AI Gateway (needs "
                   "TAMUS_AI_FRAMEWORK_API_KEY, Cloudflare WARP connected, and an explicit "
                   "--model id from GET {endpoint}/v1/models, e.g. claude-haiku-4-5)")
@click.option("--reasoning_effort", "-r", type=click.Choice(["low", "medium", "high"]), default=None,
              help="Reasoning effort for the 'tamu'/'tamu-gateway' providers (default: medium)")
@click.option("--max_tokens", "-x", type=int, default=None,
              help="Max response tokens for the 'tamu'/'tamu-gateway' providers (raises the CoT+answer cap)")
@click.option("--with_translations", "-T", is_flag=True,
              help="Detect non-English transcripts and add translation annotations")
def transcribe_manifest(path: str, output: str, new_id: str, is_tamu: bool, with_coords: bool, model: str, provider: str,
                        reasoning_effort: str, max_tokens: int, with_translations: bool) -> None:
    json_data = load_manifest(path)
    builder = ManifestHTRBuilder(json_data, new_id=new_id, nuke_tamu=is_tamu, with_coords=with_coords, model=model, provider=provider,
                                 reasoning_effort=reasoning_effort, max_tokens=max_tokens, with_translations=with_translations)
    manifest = builder.build_htr()
    write_manifest(manifest, output)


def _read_csv_rows(path: str):
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames), list(reader)


def _write_ami_csv(path: str, fieldnames: list, rows: list):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


@cli.command("csv", help="Transcribe the manifests listed in a CSV and write an Archipelago AMI CSV")
@click.option("--path", "-p", help="Path to the input CSV; must have a 'manifest' column")
@click.option("--output", "-o", help="The output AMI CSV path", default="htr_ami_output.csv")
@click.option("--model", "-m", default=None, help=f"Gemini model to use (default: {DEFAULT_MODEL}), e.g. gemini-3.5-flash")
@click.option("--provider", "-P", type=click.Choice(list(PROVIDERS.keys())), default="google",
              help="Where to run the model: 'google' calls the Gemini API directly; "
                   "'tamu' routes through TAMUS AI Chat (needs TAMUS_AI_CHAT_API_KEY); "
                   "'tamu-gateway' routes through the TAMUS AI Gateway (needs "
                   "TAMUS_AI_FRAMEWORK_API_KEY, Cloudflare WARP connected, and an explicit "
                   "--model id from GET {endpoint}/v1/models, e.g. claude-haiku-4-5)")
@click.option("--reasoning_effort", "-r", type=click.Choice(["low", "medium", "high"]), default=None,
              help="Reasoning effort for the 'tamu'/'tamu-gateway' providers (default: medium)")
@click.option("--max_tokens", "-x", type=int, default=None,
              help="Max response tokens for the 'tamu'/'tamu-gateway' providers (raises the CoT+answer cap)")
@click.option("--with_translations", "-T", is_flag=True,
              help="Detect non-English transcripts and add a 'translating' property to the annotations JSON in the CSV")
def transcribe_csv(path: str, output: str, model: str, provider: str,
                   reasoning_effort: str, max_tokens: int, with_translations: bool) -> None:
    fieldnames, input_rows = _read_csv_rows(path)
    if "manifest" not in fieldnames:
        raise click.ClickException("Input CSV must have a 'manifest' column")

    output_fieldnames = [c for c in fieldnames if c != "manifest"] + ["generative_ai_details", "annotations"]

    output_rows = []
    done = set()
    if os.path.exists(output):
        _, existing_rows = _read_csv_rows(output)
        for row in existing_rows:
            output_rows.append(row)
            done.add(row.get("node_uuid") or row.get("label"))

    for row in tqdm(input_rows):
        key = row.get("node_uuid") or row.get("label")
        if key in done:
            continue
        try:
            manifest_data = load_manifest(row["manifest"])
            builder = ManifestAnnotationsBuilder(manifest_data, model=model, provider=provider,
                                                reasoning_effort=reasoning_effort, max_tokens=max_tokens,
                                                with_translations=with_translations)
            entries = builder.build_annotations()
        except Exception as e:
            print(f"\nError processing manifest {row.get('manifest')}: {e}")
            print(f"Skipping this row and continuing...")
            continue

        new_row = {k: v for k, v in row.items() if k != "manifest"}
        new_row["generative_ai_details"] = safe_json({
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "model": builder.model,
            "provider": builder.provider,
            "generator": f"iiif-paleography/@v{__version__}",
        })
        new_row["annotations"] = safe_json(entries)
        output_rows.append(new_row)
        done.add(key)
        _write_ami_csv(output, output_fieldnames, output_rows)

    print(f"AMI CSV written to {output}")


@cli.command("list", help="Transcribe a list of IIIF Manifests")
@click.option("--path", "-p", help="The path to the list as a text file with ids on each line")
@click.option("--output", "-o", help="The output directory path to write each json", default="output")
@click.option("--is_tamu", "-t", is_flag=True, help="Whether the manifest is from TAMU and needs to get gross stuff purged")
@click.option("--with_coords", "-c", is_flag=True, help="Include coordinate annotations")
@click.option("--model", "-m", default=None, help=f"Gemini model to use (default: {DEFAULT_MODEL}), e.g. gemini-3.5-flash")
@click.option("--provider", "-P", type=click.Choice(list(PROVIDERS.keys())), default="google",
              help="Where to run the model: 'google' calls the Gemini API directly; "
                   "'tamu' routes through TAMUS AI Chat (needs TAMUS_AI_CHAT_API_KEY); "
                   "'tamu-gateway' routes through the TAMUS AI Gateway (needs "
                   "TAMUS_AI_FRAMEWORK_API_KEY, Cloudflare WARP connected, and an explicit "
                   "--model id from GET {endpoint}/v1/models, e.g. claude-haiku-4-5)")
@click.option("--reasoning_effort", "-r", type=click.Choice(["low", "medium", "high"]), default=None,
              help="Reasoning effort for the 'tamu'/'tamu-gateway' providers (default: medium)")
@click.option("--max_tokens", "-x", type=int, default=None,
              help="Max response tokens for the 'tamu'/'tamu-gateway' providers (raises the CoT+answer cap)")
@click.option("--with_translations", "-T", is_flag=True,
              help="Detect non-English transcripts and add translation annotations")
def transcribe_list(path: str, output: str, is_tamu: bool, with_coords: bool, model: str, provider: str,
                    reasoning_effort: str, max_tokens: int, with_translations: bool) -> None:
    all_ids = []
    with open(path, 'r') as f:
        for line in f:
            if line.strip() != "" and line.strip() not in all_ids:
                all_ids.append(line.strip())
    for id in tqdm(all_ids):
        output_path = Path(f"{output}/mcinnis-{id}.json")
        if not output_path.exists():
            r = requests.get(
                f"https://api-pre.library.tamu.edu/iiif-service/fedora/presentation/bb/97/f2/3e/bb97f23e-803a-4bd6-8406-06802623554c/mcinnis_objects/{id}"
            )
            if r.status_code != 200:
                raise click.ClickException(f"{r.status_code}: {r.text} on {id}")
            json_data = r.json()
            builder = ManifestHTRBuilder(
                json_data,
                new_id=f"https://tamulib-dc-labs.github.io/custom-iiif-manifests/manifests/mcinnis/mcinnis-{id}.json",
                nuke_tamu=is_tamu,
                with_coords=with_coords,
                model=model,
                provider=provider,
                reasoning_effort=reasoning_effort,
                max_tokens=max_tokens,
                with_translations=with_translations,
            )
            manifest = builder.build_htr()
            write_manifest(manifest, str(output_path))
