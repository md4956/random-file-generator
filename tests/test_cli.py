import argparse
import hashlib
import tarfile
import zipfile

import pytest

from random_file_generator import cli as fg


@pytest.mark.parametrize("text,expected", [("1024", 1024), ("1k", 1024), ("2M", 2 * 1024**2), ("1.5K", 1536)])
def test_parse_size_ok(text, expected):
    assert fg.parse_size(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "0", "-5", "10X", "K"])
def test_parse_size_bad(text):
    with pytest.raises(argparse.ArgumentTypeError):
        fg.parse_size(text)


def only_output_dir(tmp_path):
    dirs = list(tmp_path.glob("generated_*"))
    assert len(dirs) == 1
    return dirs[0]


def test_files_mode_and_manifest(tmp_path):
    assert fg.main(["files", "3", "1K", "--output-dir", str(tmp_path)]) == 0
    out = only_output_dir(tmp_path)
    files = sorted(out.glob("*.bin"))
    assert len(files) == 3 and all(f.stat().st_size == 1024 for f in files)
    for line in (out / fg.MANIFEST_NAME).read_text().splitlines():
        digest, name = line.split("  ")
        assert hashlib.sha384((out / name).read_bytes()).hexdigest() == digest


def test_seed_is_reproducible(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    fg.main(["files", "1", "4K", "--seed", "7", "--output-dir", str(a)])
    fg.main(["files", "1", "4K", "--seed", "7", "--output-dir", str(b)])
    fa = next(a.glob("generated_*/*.bin")).read_bytes()
    fb = next(b.glob("generated_*/*.bin")).read_bytes()
    assert fa == fb


def test_zeros_pattern(tmp_path):
    fg.main(["files", "1", "2K", "--pattern", "zeros", "--output-dir", str(tmp_path)])
    assert next(tmp_path.glob("generated_*/*.bin")).read_bytes() == bytes(2048)


def test_tar_gz_archive(tmp_path):
    assert fg.main(["archive", "2", "3", "1K", "tar.gz", "--output-dir", str(tmp_path)]) == 0
    out = only_output_dir(tmp_path)
    archives = sorted(out.glob("archive_*.tar.gz"))
    assert len(archives) == 2
    with tarfile.open(archives[0]) as tf:
        assert len([m for m in tf.getmembers() if m.isfile()]) == 3
    assert not [p for p in out.iterdir() if p.is_dir()]  # temp dirs cleaned up


def test_zip_with_password(tmp_path):
    if fg.shutil.which("zip") is None:
        pytest.skip("zip not installed")
    assert fg.main(["archive", "1", "2", "1K", "zip", "pw", "--output-dir", str(tmp_path)]) == 0
    archive = next(tmp_path.glob("generated_*/archive_1.zip"))
    with zipfile.ZipFile(archive) as zf:
        assert len(zf.namelist()) == 2
        zf.setpassword(b"pw")
        assert len(zf.read(zf.namelist()[0])) == 1024


@pytest.mark.parametrize("argv", [
    ["files"], ["files", "2"], ["files", "x", "1K"], ["files", "0", "1K"], ["files", "1", "abc"],
    ["archive", "1", "1", "1K", "rar"], ["archive", "1", "1", "1K", "tar", "pw"],
])
def test_bad_args_exit_cleanly_without_output(tmp_path, argv):
    with pytest.raises(SystemExit) as exc:
        fg.main([*argv, "--output-dir", str(tmp_path)])
    assert exc.value.code != 0
    assert not list(tmp_path.glob("generated_*"))


def test_output_dirs_never_collide(tmp_path):
    first = fg.make_output_dir(tmp_path, "x")
    second = fg.make_output_dir(tmp_path, "x")
    assert first != second and first.is_dir() and second.is_dir()


def test_disk_space_check(tmp_path):
    with pytest.raises(SystemExit):
        fg.check_disk_space(tmp_path, 10**18)
