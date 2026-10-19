#!/usr/bin/env python3
"""Build a deterministic installable source ZIP, excluding machine-local state."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT_FILES = ("plugin.json", "steps.json", "gates.json", "SKILL.md", "README.md", "LICENSE", "licenses/Apache-2.0.txt", "SECURITY.md", "CHANGELOG.md", "VERIFICATION.md", "requirements.txt", "requirements-authoring.txt", "requirements-surfaces.txt", ".gitignore")
TREES = ("tools", "authoring", "resources_lib", "runtime", "recipes", "reference", "examples", "tests", "scripts", ".github")


def package(source, output):
    for name in ROOT_FILES:
        if not (source / name).is_file():
            raise ValueError("missing release file: " + name)
    manifest = json.loads((source / "plugin.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    if manifest.get("name") != "interior" or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("expected interior manifest with a stable semver version")
    files = [source / name for name in ROOT_FILES]
    for name in TREES:
        tree = source / name
        if tree.is_symlink():
            raise ValueError("release trees cannot be symlinks: " + name)
        for path in tree.rglob("*"):
            rel = path.relative_to(source)
            if (path.name == "_img2_local.py" or path.suffix in (".pyc", ".pyo")
                    or any(part in ("__pycache__", "node_modules", "dist", ".img2", ".venv", ".venv-blender", ".venv-images") for part in rel.parts)):
                continue
            if ((path.name.startswith(".env") and path.name != ".env.example")
                    or path.suffix.lower() in (".pem", ".key")):
                continue
            if path.is_symlink():
                raise ValueError("release source cannot contain symlinks: " + str(rel))
            if path.is_file():
                files.append(path)
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(source):
            raise ValueError("release file escapes source: " + str(path))
    for path in [source / "SKILL.md", *(source / "reference").glob("*.md")]:
        if len(path.read_text(encoding="utf-8").splitlines()) >= 150:
            raise ValueError("progressive-disclosure document must be under 150 lines: " + str(path))
    output.mkdir(parents=True, exist_ok=True)
    archive = output / ("img2interior-" + version + ".zip")
    temporary = archive.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temporary, "w") as bundle:
            for path in sorted(files, key=lambda p: p.relative_to(source).as_posix()):
                relative = "img2interior/" + path.relative_to(source).as_posix()
                info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                bundle.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksums = output / "SHA256SUMS"
    checksums.write_text(digest + "  " + archive.name + "\n", encoding="utf-8")
    return {"archive":str(archive), "sha256":digest, "bytes":archive.stat().st_size, "files":len(files), "format":"installable-source-zip", "excluded":[".git", "_img2_local.py", "__pycache__", ".img2", "credentials", "showcase-assets"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--output", type=Path, help="Output directory for the versioned ZIP and SHA256SUMS (default: SOURCE/dist)")
    args = parser.parse_args()
    source = args.source.resolve()
    try:
        print(json.dumps(package(source, args.output.resolve() if args.output else source / "dist"), indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
