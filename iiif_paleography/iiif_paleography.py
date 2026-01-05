from iiif_prezi3 import Manifest
from iiif_paleography.gemini import GeminiTranscriber
import json


class ManifestHTRBuilder:
    def __init__(self, manifest: Manifest, new_id=None, new_base="https://example.org"):
        self.manifest_data = manifest
        self.new_id = new_id if new_id else self.manifest_data['id']
        self.new_base = new_base

    def build_htr(self):
        manifest = Manifest(
            **self.manifest_data
        )
        if self.new_id:
            manifest.id = self.new_id
        i = 0
        transcriber = GeminiTranscriber()
        for canvas in manifest.items:
            image = canvas.items[0].items[0].body.id
            api_response = transcriber.transcribe(image)
            response = transcriber.get_response_dict(api_response)
            canvas.make_annotation(
                motivation="transcribing",
                body={
                    "type": "TextualBody",
                    "language": "en",
                    "format": "text/plain",
                    "value": response['transcription']
                },
               target=canvas.id
            )
            canvas.make_annotation(
                motivation="commenting",
                body={
                    "type": "TextualBody",
                    "language": "none",
                    "format": "text/plain",
                    "value": response['thought_process']
                },
                target=canvas.id,
            )
            i += 1
        return manifest


if __name__ == '__main__':
    with open('fixtures/mcinnis-39-v3.json', 'r') as f:
        json_data = json.load(f)
    builder = ManifestHTRBuilder(json_data, new_id="https://example.org/1234")
    manifest = builder.build_htr()
    output_file = 'fixtures/mcinnis-39-v3-htr.json'
    with open(output_file, 'w') as f:
        f.write(manifest.json(indent=4))
    print(f"HTR manifest written to {output_file}")