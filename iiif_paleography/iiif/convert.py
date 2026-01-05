import json
from iiif_prezi3 import Manifest, KeyValueString


class IIIFv2tov3Converter:
    def __init__(self, v2_manifest, manifest_id=None):
        self.v2_manifest = v2_manifest
        self.manifest_id = manifest_id if manifest_id else v2_manifest['@id']

    def convert(self):
        metadata = self.build_metadata()
        manifest = Manifest(
            id=self.manifest_id,
            label=self.v2_manifest['label'],
            metadata=metadata,
            thumbnail=[
                {"id": self.v2_manifest["thumbnail"]['@id'].strip(), "type": "Image"}
            ]
        )
        for canvas in self.v2_manifest['sequences'][0]['canvases']:
            manifest.make_canvas_from_iiif(
                url=canvas['images'][0]['@id'],
                id=canvas['@id'],
                label=canvas.get('label', ''),
                width=canvas['width'],
                height=canvas['height'],
            )

        return json.loads(manifest.json(indent=4))

    def build_metadata(self):
        metadata = []
        for pair in self.v2_manifest['metadata']:
            metadata.append(
                KeyValueString(
                    label=pair['label'],
                    value=pair['value'],
                )
            )
        return metadata


if __name__ == '__main__':
    with open("fixtures/mcinnis_39.json") as f:
        data = json.load(f)

    converter = IIIFv2tov3Converter(
        v2_manifest=data,
        manifest_id="https://markpbaggett.github.io/iiif-paleography/fixtures/mcinnis-39-v3.json"
    )
    data = converter.convert()
    with open("fixtures/mcinnis-39-v3.json", "w") as f:
        f.write(
            data.json(
                indent=4
            )
        )
