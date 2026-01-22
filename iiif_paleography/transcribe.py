from iiif_prezi3 import Manifest
from iiif_paleography.gemini import GeminiTranscriber
from iiif_paleography.iiif import IIIFv2tov3Converter
import json
import click
import requests
from tqdm import tqdm
from pathlib import Path
from toon_format import decode
from datetime import datetime, timezone


class ManifestHTRBuilder:
    def __init__(self, manifest: Manifest, new_id=None, new_base="https://example.org",
                 nuke_tamu=False, with_coords=False):
        self.manifest_data = manifest
        self.new_id = new_id if new_id else self.manifest_data.get("id", self.manifest_data.get("@id"))
        self.new_base = new_base
        self.nuke = nuke_tamu
        self.with_coords = with_coords

    def _convert_if_v2(self):
        if '@id' in self.manifest_data:
            converter = IIIFv2tov3Converter(
                v2_manifest=self.manifest_data,
                manifest_id=self.new_id,
            )
            self.manifest_data = converter.convert()

    def _create_transcriber(self, canvas):
        if self.with_coords:
            width = str(canvas.items[0].items[0].body.width)
            height = str(canvas.items[0].items[0].body.height)
            return GeminiTranscriber(
                prompt_path='prompts/gemini-htr-and-coords.md',
                width=width, height=height
            )
        return GeminiTranscriber()

    def _get_image_url(self, canvas):
        url = canvas.items[0].items[0].body.id
        if self.with_coords:
            url = url.replace('full/full', 'full/pct:25')
        return url

    def _add_transcription_annotations(self, canvas, response):
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if self.with_coords:
            word_coords = decode(response['transcription'])
            for coord in word_coords:
                print(coord)
                canvas.make_annotation(
                    motivation="tagging",
                    purpose="transcribing",
                    creator="gemini-3-pro-preview",
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
                creator="gemini-3-pro-preview",
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
                self._add_transcription_annotations(canvas, response)
                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                canvas.make_annotation(
                    motivation="commenting",
                    purpose="transcribing",
                    creator="gemini-3-pro-preview",
                    created=timestamp,
                    generator="iiif-paleography@v0.1.0",
                    generated=timestamp,
                    body={
                        "type": "TextualBody",
                        "language": "none",
                        "format": "text/markdown",
                        "value": response['thought_process']
                    },
                    target=canvas.id,
                )
            except Exception as e:
                print(f"\nError processing canvas {i} ({canvas.id}): {e}")
                print(f"Skipping this canvas and continuing...")
        return manifest


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
def transcribe_manifest(path: str, output: str, new_id: str, is_tamu: bool, with_coords: bool) -> None:
    json_data = load_manifest(path)
    builder = ManifestHTRBuilder(json_data, new_id=new_id, nuke_tamu=is_tamu, with_coords=with_coords)
    manifest = builder.build_htr()
    write_manifest(manifest, output)


@cli.command("list", help="Transcribe a list of IIIF Manifests")
@click.option("--path", "-p", help="The path to the list as a text file with ids on each line")
@click.option("--output", "-o", help="The output directory path to write each json", default="output")
@click.option("--is_tamu", "-t", is_flag=True, help="Whether the manifest is from TAMU and needs to get gross stuff purged")
@click.option("--with_coords", "-c", is_flag=True, help="Include coordinate annotations")
def transcribe_list(path: str, output: str, is_tamu: bool, with_coords: bool) -> None:
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
            )
            manifest = builder.build_htr()
            write_manifest(manifest, str(output_path))
