"""Install the owner's licensed IRANSansX Persian webfont package locally."""

import argparse
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile


WEIGHTS = (
    (100, "Thin"), (200, "UltraLight"), (300, "Light"), (400, "Regular"),
    (500, "Medium"), (600, "DemiBold"), (700, "Bold"), (800, "ExtraBold"),
    (900, "Black"), (950, "ExtraBlack"), (1000, "Heavy"),
)


def install(archive_path: Path, destination: Path) -> None:
    names = {f"IRANSansXFaNum-{weight}.woff2": value for value, weight in WEIGHTS}
    with ZipFile(archive_path) as archive:
        entries = {
            path.name: info for info in archive.infolist()
            if (path := PurePosixPath(info.filename)).name in names
            and "Farsi numerals" in path.parts
            and path.parent.name.lower() == "woff2"
        }
        missing = names.keys() - entries.keys()
        if missing:
            raise ValueError("Missing Persian WOFF2 faces: " + ", ".join(sorted(missing)))
        if any(info.file_size > 512_000 for info in entries.values()):
            raise ValueError("A webfont in the archive exceeds the expected size.")
        fonts = {name: archive.read(entries[name]) for name in names}
        if any(data[:4] != b"wOF2" for data in fonts.values()):
            raise ValueError("The archive contains an invalid WOFF2 file.")

    destination.mkdir(parents=True, exist_ok=True)
    for name, data in fonts.items():
        (destination / name).write_bytes(data)

    faces = [
        f'@font-face {{ font-family: IranSansX; font-style: normal; font-weight: {weight}; '
        f'font-display: swap; src: url("./{name}") format("woff2"); }}'
        for name, weight in names.items()
    ]
    stylesheet = destination / "faces.css"
    temporary_stylesheet = stylesheet.with_suffix(".tmp")
    temporary_stylesheet.write_text("\n".join(faces) + "\n", encoding="utf-8")
    temporary_stylesheet.replace(stylesheet)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    destination = Path(__file__).resolve().parents[1] / "public" / "fonts" / "iransansx"
    try:
        install(args.archive, destination)
    except (OSError, ValueError, BadZipFile) as error:
        parser.error(str(error))
    print(f"Installed {len(WEIGHTS)} Persian webfont weights in {destination}")


if __name__ == "__main__":
    main()
