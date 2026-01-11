from iiif_prezi3 import Manifest
from iiif_paleography.gemini import GeminiTranscriber
from iiif_paleography.iiif import IIIFv2tov3Converter
import json
import click
import requests
from tqdm import tqdm
from pathlib import Path


class ManifestHTRBuilder:
    def __init__(self, manifest: Manifest, new_id=None, new_base="https://example.org", nuke_tamu=False):
        self.manifest_data = manifest
        self.new_id = new_id if new_id else self.manifest_data.get("id", self.manifest_data.get("@id"))
        self.new_base = new_base
        self.nuke = nuke_tamu

    def build_htr(self):
        if '@id' in self.manifest_data:
            converter = IIIFv2tov3Converter(
                v2_manifest=self.manifest_data,
                manifest_id=self.new_id,
            )
            self.manifest_data = converter.convert()
        manifest = Manifest(
            **self.manifest_data
        )
        if self.new_id:
            manifest.id = self.new_id
        if self.nuke:
            manifest.thumbnail[0].id = manifest.thumbnail[0].id.replace('!100,100', 'pct:25')
        i = 0
        transcriber = GeminiTranscriber()
        for canvas in tqdm(manifest.items):
            image = canvas.items[0].items[0].body.id
            if self.nuke:
                canvas.label['none'][0] = f"Page {i}"
            api_response = transcriber.transcribe(image)
            response = transcriber.get_response_dict(api_response)
            canvas.make_annotation(
                motivation="transcribing",
                body={
                    "type": "TextualBody",
                    "language": "en",
                    "format": "text/html",
                    "purpose": "transcribing",
                    "value": f"<span>{response['transcription']}</span>"
                },
               target=canvas.id
            )
            # @TODO:  I need to escape markup in the value so that it isn't rendered as HTML.
            canvas.make_annotation(
                motivation="commenting",
                body={
                    "type": "TextualBody",
                    "language": "none",
                    "format": "text/markdown",
                    "value": response['thought_process']
                },
                target=canvas.id,
            )
            i += 1
        return manifest

@click.group()
def cli() -> None:
    pass


@cli.command(
    "manifest", help="Transcribe a single IIIF Manifest"
)
@click.option(
    "--path",
    "-p",
    help="The path to the Manifest",
)
@click.option(
    "--output",
    "-o",
    help="The output file path",
    default="fixtures/transcribed.json",
)
@click.option(
    "--new_id",
    "-n",
    help="A new identifier for your manifest",
)
@click.option(
    "--is_tamu",
    "-t",
    is_flag=True,
    help="Whether the manifest is from TAMU and needs to get gross stuff purged",
)
def transcribe_manifest(path: str, output: str, new_id: str, is_tamu: bool) -> None:
    if path.startswith("https"):
        r = requests.get(path)
        if r.status_code != 200:
            raise click.ClickException(f"{r.status_code}: {r.text} on {path}")
        json_data = r.json()
    else:
        with open(path, 'r') as f:
            json_data = json.load(f)
    if new_id:
        identifier = new_id
        builder = ManifestHTRBuilder(
            json_data,
            new_id=identifier,
            nuke_tamu=is_tamu,
        )
    else:
        builder = ManifestHTRBuilder(
            json_data,
            nuke_tamu=is_tamu,
        )
    manifest = builder.build_htr()
    with open(output, 'w') as f:
        json_str = manifest.json()
        json_obj = json.loads(json_str)
        f.write(json.dumps(json_obj, indent=4))
    print(f"HTR manifest written to {output}")


@cli.command(
    "list", help="Transcribe a list of IIIF Manifests"
)
@click.option(
    "--path",
    "-p",
    help="The path to the list as a text file with ids on each line",
)
@click.option(
    "--output",
    "-o",
    help="The output directory path to write each json",
    default="output",
)
@click.option(
    "--is_tamu",
    "-t",
    is_flag=True,
    help="Whether the manifest is from TAMU and needs to get gross stuff purged",
)
def transcribe_list(path: str, output: str, is_tamu: bool) -> None:
    all_ids = []
    with open(path, 'r') as f:
        for line in f:
            if line.strip() != "" and line.strip() not in all_ids:
                all_ids.append(line.strip())
    for id in tqdm(all_ids):
        path = Path(f"{output}/mcinnis-{id}.json")
        if not path.exists():
            r = requests.get(f"https://api-pre.library.tamu.edu/iiif-service/fedora/presentation/bb/97/f2/3e/bb97f23e-803a-4bd6-8406-06802623554c/mcinnis_objects/{id}")
            if r.status_code != 200:
                raise click.ClickException(f"{r.status_code}: {r.text} on {path}")
            json_data = r.json()
            builder = ManifestHTRBuilder(
                json_data,
                new_id=f"https://tamulib-dc-labs.github.io/custom-iiif-manifests/manifests/mcinnis/mcinnis-{id}.json",
                nuke_tamu=is_tamu,
            )
            manifest = builder.build_htr()
            with open(f"{output}/mcinnis-{id}.json", 'w') as f:
                json_str = manifest.json()
                json_obj = json.loads(json_str)
                f.write(json.dumps(json_obj, indent=4))
            print(f"HTR manifest written to {output}")