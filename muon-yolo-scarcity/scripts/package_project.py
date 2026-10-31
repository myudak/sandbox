"""Package source and optional numeric evidence; omit images, labels and weights."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-evidence", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "deliverables/muon_yolo_research_project.zip")
    args = parser.parse_args()
    files = {}
    for folder in ("src", "scripts", "tests", "analysis_tests", "configs", "research", "notebooks", "handoff", "kaggle", "paper"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc" and not path.name.endswith(".tmp"):
                files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for name in ("README.md", ".gitignore", "requirements.txt", "requirements-dev.txt"):
        files[name] = (ROOT / name).read_bytes()
    if args.with_evidence:
        evidence = args.with_evidence.resolve()
        for path in evidence.rglob("*"):
            relative = path.relative_to(evidence)
            if not path.is_file() or any(part in {"images", "labels", "annotation_examples", "initial_weights", "weights"} for part in relative.parts):
                continue
            if path.suffix not in {".json", ".csv", ".png", ".svg", ".md", ".yaml", ".txt"} or path.name == "corruption.json" or path.name.startswith('private_'):
                continue
            files[f"evidence/{relative.as_posix()}"] = path.read_bytes()
    manifest = {"purpose": "Private research development handoff; not a publication claim",
                "source_images_included": False, "model_weights_included": False,
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files["bundle_manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError("Bundle output must stay inside the project workspace")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    with zipfile.ZipFile(temporary) as archive:
        assert archive.testzip() is None
        for name, expected in manifest["files"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected
    temporary.replace(output)
    print(f"Verified {len(files)} packaged files: {output}")


if __name__ == "__main__":
    main()
