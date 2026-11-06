# random-file-generator

A small, dependency-free Python script that creates **files and archives filled with random data** — handy for testing anything that has to cope with files of a known size.

By default every file is filled with cryptographically random bytes (`os.urandom`), so each one is unique and effectively incompressible. Every generated item is printed with its **SHA-384 checksum** and saved to a `SHA384SUMS` file, so you can verify transfers, uploads, or storage round-trips afterwards.

## Features

- **Plain binary files** – any number of files at any size (`10K`, `5M`, `1.5G`, or raw bytes).
- **Archives** – generate N archives, each holding M random files, as `zip`, `tar`, or `tar.gz`.
- **Password-protected zips** – optionally encrypt `zip` archives with a password.
- **SHA-384 checksums** – printed for every item and saved to `SHA384SUMS` (verifiable with `sha384sum -c`).
- **Reproducible data** – `--seed` produces identical output on every run.
- **Compressible data** – `--pattern zeros` for testing compression.
- **Safe by default** – input is validated before anything is written, free disk space is checked up front, and output folders never overwrite each other.
- **Streaming writes** – data is written in 1 MiB chunks, so memory use stays flat even for multi-GB files.
- **No third-party Python packages.**

## Requirements

- Python 3.9+
- The `zip` command-line tool, *only* for `zip` archives (preinstalled on macOS and most Linux distributions; `sudo apt install zip` otherwise). `tar` and `tar.gz` use Python's standard library.

## Usage

```text
python fileGenerator.py files   <number> <size> [options]
python fileGenerator.py archive <archives> <files-per-archive> <size> <format> [password] [options]
```

| Argument | Meaning |
| --- | --- |
| `number` | How many plain files to create |
| `archives` | How many archives to create |
| `files-per-archive` | How many random files go inside each archive |
| `size` | Size of **each individual file**: bytes (`1048576`) or with a suffix `K`, `M`, `G` (1024-based, decimals allowed, e.g. `1.5G`) |
| `format` | `zip`, `tar`, or `tar.gz` |
| `password` | Optional; `zip` only |

Options (both modes):

| Option | Meaning |
| --- | --- |
| `--output-dir DIR` | Parent directory for the generated folder (default: current directory) |
| `--seed N` | Reproducible data. Fast and repeatable, but **not** cryptographically secure |
| `--pattern random\|zeros` | `random` (default) or all-zero bytes that compress extremely well |

Run `python fileGenerator.py --help` (or `files --help` / `archive --help`) for the built-in help.

> `size` is the size of each file *inside* an archive, not the size of the archive itself.

### 1. Generate plain files

Create 5 files of 10 MiB each:

```bash
python fileGenerator.py files 5 10M
```

```text
3f1c…  file_10M_1.bin
9a7b…  file_10M_2.bin
…
Output directory: generated_20260101_120000_files_5_10M
Checksums saved to: generated_20260101_120000_files_5_10M/SHA384SUMS
```

### 2. Generate archives

Three `zip` archives, each containing 4 files of 2 MiB:

```bash
python fileGenerator.py archive 3 4 2M zip
```

Two `tar.gz` archives with 10 files of 512 KiB each:

```bash
python fileGenerator.py archive 2 10 512K tar.gz
```

### 3. Generate password-protected zips

```bash
python fileGenerator.py archive 3 4 2M zip "s3cret"
```

Passwords are only supported for `zip`; using one with `tar`/`tar.gz` is rejected with an error.

### 4. Reproducible and compressible data

```bash
# Same seed -> byte-identical files every time
python fileGenerator.py files 3 1M --seed 42

# Highly compressible data (tar.gz will be tiny)
python fileGenerator.py archive 1 5 10M tar.gz --pattern zeros

# Write somewhere else
python fileGenerator.py files 10 100M --output-dir /mnt/scratch
```

## Output

Each run creates a new directory (a numeric suffix is added if the name already exists):

```text
generated_<YYYYMMDD_HHMMSS>_<mode>_<arg1>_<arg2>/
```

- `files` mode → `file_<size>_<n>.bin`
- `archive` mode → `archive_<n>.<format>` (files inside are named `file_<size>_<n>.bin`)
- Both modes → `SHA384SUMS`, in the standard `<hash>  <name>` format

Verify later, from inside the output folder:

```bash
sha384sum -c SHA384SUMS        # Linux
shasum -a 384 -c SHA384SUMS    # macOS
```

## Typical use cases

- Testing upload/download limits and timeouts of web apps, APIs, and object storage.
- Benchmarking disk, network, backup, and sync tools with data that can't be compressed or deduplicated.
- Exercising archive-handling code: extraction, virus-scanning pipelines, zip-bomb protection, password prompts.
- Verifying data integrity end-to-end by comparing SHA-384 hashes before and after transfer.
- Producing repeatable fixtures for automated tests (`--seed`).
- Filling storage to a known size.

## Tests

```bash
pip install pytest
pytest
```

## Notes and limitations

- With the default random data, a `tar.gz` is about the same size as the equivalent `tar`. Use `--pattern zeros` to test compression.
- Zip passwords use the `zip` tool's `-P` option (legacy ZipCrypto encryption). This is fine for testing password prompts, **not** for protecting real data, and the password is visible in the process list while running.
- The `zip` format requires the external `zip` binary; it is not available by default on Windows.
- Archive mode needs room for the archives plus one batch of temporary files; the script checks free space first and exits if it is insufficient.
- Generating very large files with `os.urandom` is limited by system randomness speed.

## License

No license has been specified yet; add one (e.g. MIT) if you want others to reuse this.
