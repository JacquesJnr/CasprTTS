"""Record installed dependencies, their shipped notices, and frozen native files."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import platform
import re
import shutil
import sys
from pathlib import Path


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory(bundle, output):
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(__file__).parent / "licenses", output / "upstream-notices", dirs_exist_ok=True)
    for candidate in ("LICENSE.txt", "LICENSE"):
        source = Path(sys.base_prefix) / candidate
        if source.is_file():
            shutil.copy2(source, output / "Python-LICENSE.txt")
            break
    packages = []
    for dist in sorted(metadata.distributions(), key=lambda d: d.metadata["Name"].lower()):
        name = dist.metadata["Name"]
        notices = []
        for item in dist.files or []:
            if re.search(r"(?i)(license|copying|copyright|notice)", str(item)):
                source = Path(dist.locate_file(item))
                if source.is_file():
                    # Flatten safely: wheel paths can contain ../ for scripts.
                    target = output / "licenses" / name / str(item).replace("/", "_").replace("\\", "_")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    notices.append(str(target.relative_to(output)))
        packages.append(dict(name=name, version=dist.version,
                             license=dist.metadata.get("License-Expression") or dist.metadata.get("License"),
                             project_urls=dist.metadata.get_all("Project-URL", []),
                             homepage=dist.metadata.get("Home-page"), notices=notices,
                             notice_review_required=not bool(notices)))
    import pefile
    natives = []
    for path in sorted(bundle.rglob("*")):
        if path.suffix.lower() not in (".dll", ".pyd", ".exe"):
            continue
        pe = pefile.PE(str(path), fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        imports = sorted(entry.dll.decode("ascii") for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []))
        pe.close()
        natives.append(dict(path=path.relative_to(bundle).as_posix(), sha256=digest(path), imports=imports))
    (output / "dependencies.json").write_text(json.dumps(dict(
        python=platform.python_version(), architecture=platform.machine(),
        scope="Complete build environment; some build-only packages are not frozen",
        packages=packages, native_files=natives), indent=2), encoding="utf-8")
    (output / "NOTICE.txt").write_text(
        "Caspr TTS dependency inventory\n\n"
        "No voice models, Microsoft voices, or audio drivers are redistributed.\n"
        "Piper 1.4.2 is GPL-3.0-or-later; PySide6/Qt has LGPL/GPL/commercial terms.\n"
        "dependencies.json records package metadata and native imports; licenses/ copies shipped notices.\n"
        "This inventory is not a complete source-delivery or license-compliance determination.\n"
        "Release maintainers must provide applicable corresponding source and review native notices.\n",
        encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    inventory(args.bundle, args.output)
