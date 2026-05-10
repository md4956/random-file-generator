#!/usr/bin/env python3
import os
import sys
import hashlib
import tarfile
import tempfile
import subprocess
from datetime import datetime

# ------------------ Helpers ------------------

def parse_size(size_str):
    size_str = size_str.upper()
    units = {"K": 1024, "M": 1024**2, "G": 1024**3}
    if size_str[-1] in units:
        return int(float(size_str[:-1]) * units[size_str[-1]])
    return int(size_str)

def write_unique_file(path, size_bytes):
    with open(path, "wb") as f:
        remaining = size_bytes
        while remaining > 0:
            chunk = os.urandom(min(1024 * 1024, remaining))
            f.write(chunk)
            remaining -= len(chunk)

def sha384sum(path):
    h = hashlib.sha384()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

helper_message = """
            Invalid arguments.

            Usage:
                python fileGenerator.py files <number> <size>
                python fileGenerator.py archive <archive-number> <file-per-archive> <size> <format> [password]

            Formats: zip | tar | tar.gz
            
            """

# ------------------ Archive creators ------------------

def create_zip(archive_path, source_dir, password=None):
    archive_path = os.path.abspath(archive_path)

    cmd = ["zip", "-j", "-r"]
    if password:
        cmd.extend(["-P", password])

    cmd.append(archive_path)

    for name in os.listdir(source_dir):
        cmd.append(os.path.join(source_dir, name))

    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
    )

def create_tar(archive_path, source_dir, mode):
    with tarfile.open(archive_path, mode) as tf:
        tf.add(source_dir, arcname=".")

# ------------------ Main ------------------

def main():
    if len(sys.argv) < 2:
        print(helper_message)
        sys.exit(1)

    mode = sys.argv[1]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = f"generated_{timestamp}_{mode}_{sys.argv[2]}_{sys.argv[3]}"
    os.makedirs(base_dir, exist_ok=True)

    hash_results = []

    # Scenario 1: plain files
    if mode == "files":
        x = int(sys.argv[2])
        size = parse_size(sys.argv[3])

        for i in range(1, x + 1):
            path = os.path.join(base_dir, f"file_{sys.argv[3]}_{i}.bin")
            write_unique_file(path, size)
            hash_results.append((sha384sum(path), os.path.basename(path)))
            print(f'{sha384sum(path)} {os.path.basename(path)}') # new

    # Scenario 2 & 3: archives
    elif mode == "archive":
        z = int(sys.argv[2])
        x = int(sys.argv[3])
        size = parse_size(sys.argv[4])
        archive_format = sys.argv[5]
        password = sys.argv[6] if len(sys.argv) > 6 else None

        if password and archive_format != "zip":
            print("Password protection is only supported for zip archives")
            sys.exit(1)

        for a in range(1, z + 1):
            with tempfile.TemporaryDirectory() as tmp:
                for i in range(1, x + 1):
                    fpath = os.path.join(tmp, f"file_{sys.argv[4]}_{i}.bin")
                    write_unique_file(fpath, size)

                archive_name = f"archive_{a}.{archive_format}"
                archive_path = os.path.join(base_dir, archive_name)

                if archive_format == "zip":
                    create_zip(archive_path, tmp, password)
                elif archive_format == "tar":
                    create_tar(archive_path, tmp, "w")
                elif archive_format == "tar.gz":
                    create_tar(archive_path, tmp, "w:gz")
                else:
                    print("Unsupported archive format")
                    sys.exit(1)

                hash_results.append((sha384sum(archive_path), archive_name))
                print(f'{sha384sum(archive_path)} {archive_name}') # new

    else:
        print(helper_message)
        sys.exit(1)

    # Validation output
    # print("\nSHA384 HASH LIST\n")
    # for h, name in hash_results:
    #     print(f"{h}  {name}")

    print(f"\nOutput directory: {base_dir}")

if __name__ == "__main__":
    main()
