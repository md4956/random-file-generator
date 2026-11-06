"""Generate files and archives filled with random data, with SHA-384 checksums."""
from __future__ import annotations

import argparse
import hashlib
import os
import random
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

CHUNK_SIZE = 1024 * 1024  # 1 MiB
UNITS = {"K": 1024, "M": 1024**2, "G": 1024**3}
ARCHIVE_FORMATS = ("zip", "tar", "tar.gz")
MANIFEST_NAME = "SHA384SUMS"

# ------------------ Argument types ------------------


def parse_size(value: str) -> int:
    """Parse '1024', '10K', '5M', '1.5G' into a byte count (> 0)."""
    text = value.strip().upper()
    try:
        if text and text[-1] in UNITS:
            size = int(float(text[:-1]) * UNITS[text[-1]])
        else:
            size = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid size {value!r} (use bytes or a K/M/G suffix, e.g. 512K, 1.5G)"
        ) from None
    if size <= 0:
        raise argparse.ArgumentTypeError(f"size must be greater than zero: {value!r}")
    return size


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {value!r}") from None
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1: {value!r}")
    return number


# ------------------ Data + hashing ------------------

DataSource = Callable[[int], bytes]


def make_data_source(pattern: str, seed: Optional[int]) -> DataSource:
    """Return a function producing n bytes of the requested kind of data."""
    if pattern == "zeros":
        return lambda n: bytes(n)
    if seed is not None:
        rng = random.Random(seed)  # reproducible, NOT cryptographically secure
        return lambda n: rng.randbytes(n)
    return os.urandom


def write_unique_file(path: Path, size_bytes: int, source: DataSource) -> None:
    with open(path, "wb") as f:
        remaining = size_bytes
        while remaining > 0:
            chunk = source(min(CHUNK_SIZE, remaining))
            f.write(chunk)
            remaining -= len(chunk)


def sha384sum(path: Path) -> str:
    h = hashlib.sha384()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------ Archive creators ------------------


def create_zip(archive_path: Path, source_dir: Path, password: Optional[str] = None) -> None:
    """Zip source_dir so that extraction yields a single top-level folder named after it."""
    if password:
        # The standard library cannot write encrypted zips; use the external tool.
        cmd = ["zip", "-r", "-P", password, str(archive_path.resolve()), source_dir.name]
        subprocess.run(cmd, cwd=source_dir.parent, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.iterdir()):
            if path.is_file():
                zf.write(path, arcname=f"{source_dir.name}/{path.name}")


def create_tar(archive_path: Path, source_dir: Path, mode: str) -> None:
    with tarfile.open(archive_path, mode) as tf:
        for path in sorted(source_dir.iterdir()):
            if path.is_file():
                tf.add(path, arcname=f"{source_dir.name}/{path.name}")


def create_archive(fmt: str, archive_path: Path, source_dir: Path, password: Optional[str]) -> None:
    if fmt == "zip":
        create_zip(archive_path, source_dir, password)
    elif fmt == "tar":
        create_tar(archive_path, source_dir, "w")
    elif fmt == "tar.gz":
        create_tar(archive_path, source_dir, "w:gz")
    else:  # unreachable: argparse restricts choices
        raise ValueError(f"unsupported archive format: {fmt}")


# ------------------ Output handling ------------------


def make_output_dir(parent: Path, label: str) -> Path:
    """Create a fresh, uniquely named output directory (never reuses one)."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = parent / f"generated_{stamp}_{label}"
    candidate, counter = base, 1
    while True:
        try:
            candidate.mkdir(parents=True)
            return candidate
        except FileExistsError:
            counter += 1
            candidate = base.with_name(f"{base.name}_{counter}")


def check_disk_space(parent: Path, required: int) -> None:
    probe = parent
    while not probe.exists():
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    if required > free:
        raise SystemExit(
            f"error: not enough free disk space in {probe}: "
            f"need about {required:,} bytes, only {free:,} available"
        )


def record(manifest: list[str], digest: str, name: str) -> None:
    line = f"{digest}  {name}"  # two spaces: compatible with `sha384sum -c`
    manifest.append(line)
    print(line)


# ------------------ Modes ------------------


def run_files(args: argparse.Namespace, source: DataSource) -> None:
    check_disk_space(args.output_dir, args.number * args.size)
    out = make_output_dir(args.output_dir, f"files_{args.number}_{args.size_text}")
    manifest: list[str] = []
    for i in range(1, args.number + 1):
        path = out / f"file_{args.size_text}_{i}.bin"
        write_unique_file(path, args.size, source)
        record(manifest, sha384sum(path), path.name)
    finish(out, manifest)


def run_archive(args: argparse.Namespace, source: DataSource) -> None:
    per_archive = args.files_per_archive * args.size
    # worst case: one temp batch + all (incompressible) archives
    check_disk_space(args.output_dir, per_archive * (args.archives + 1))
    out = make_output_dir(args.output_dir, f"archive_{args.archives}_{args.files_per_archive}")
    manifest: list[str] = []
    for a in range(1, args.archives + 1):
        with tempfile.TemporaryDirectory(dir=out) as tmp:
            tmp_dir = Path(tmp) / f"archive_{a}"  # becomes the archive's top-level folder
            tmp_dir.mkdir()
            for i in range(1, args.files_per_archive + 1):
                write_unique_file(tmp_dir / f"file_{args.size_text}_{i}.bin", args.size, source)
            archive_path = out / f"archive_{a}.{args.format}"
            create_archive(args.format, archive_path, tmp_dir, args.password)
        record(manifest, sha384sum(archive_path), archive_path.name)
    finish(out, manifest)


def finish(out: Path, manifest: list[str]) -> None:
    (out / MANIFEST_NAME).write_text("\n".join(manifest) + "\n")
    print(f"\nOutput directory: {out}")
    print(f"Checksums saved to: {out / MANIFEST_NAME}")


# ------------------ CLI ------------------


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--output-dir", type=Path, default=Path.cwd(),
                        help="parent directory for the generated folder (default: current directory)")
    common.add_argument("--seed", type=int,
                        help="seed for reproducible (non-cryptographic) data; default is os.urandom")
    common.add_argument("--pattern", choices=("random", "zeros"), default="random",
                        help="'zeros' makes highly compressible data (default: random)")

    parser = argparse.ArgumentParser(
        prog="random-file-generator",
        description="Generate files and archives of random data with SHA-384 checksums.")
    sub = parser.add_subparsers(dest="mode", required=True)

    files = sub.add_parser("files", parents=[common], help="create plain binary files")
    files.add_argument("number", type=positive_int, help="how many files")
    files.add_argument("size", help="size of each file: bytes or K/M/G suffix (e.g. 10M, 1.5G)")

    arch = sub.add_parser("archive", parents=[common], help="create archives of random files")
    arch.add_argument("archives", type=positive_int, help="how many archives")
    arch.add_argument("files_per_archive", type=positive_int, help="files inside each archive")
    arch.add_argument("size", help="size of each file inside an archive (e.g. 2M)")
    arch.add_argument("format", choices=ARCHIVE_FORMATS, help="archive format")
    arch.add_argument("password", nargs="?", help="optional password (zip only)")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        args.size_text = args.size  # keep the user's spelling (e.g. "10M") for file names
        args.size = parse_size(args.size)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    if args.mode == "archive":
        if args.password and args.format != "zip":
            parser.error("password protection is only supported for zip archives")
        if args.format == "zip" and args.password and shutil.which("zip") is None:
            parser.error("the 'zip' command-line tool is required for password-protected zips but was not found")

    args.output_dir = args.output_dir.expanduser()
    source = make_data_source(args.pattern, args.seed)
    try:
        (run_files if args.mode == "files" else run_archive)(args, source)
    except subprocess.CalledProcessError as exc:
        print(f"error: archive tool failed: {exc.stderr.decode(errors='replace').strip()}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
