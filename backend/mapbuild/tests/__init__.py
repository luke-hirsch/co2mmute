"""The map builder's tests: each rule on a small hand-made input, and one whole build of a cut of
real data (`data/bremen-mitte/`: Bremen's station and old town, OSM, Zensus, GHSL and the
timetable as of October 2026), offline."""

import gzip
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

DATA = Path(__file__).parent / "data"


def fixture_dir(name="bremen-mitte", into=None):
    """the fixture as an area's cache directory (unzipped), in a fresh temporary directory."""
    d = Path(into or tempfile.mkdtemp(prefix="mapbuild-"))
    d.mkdir(parents=True, exist_ok=True)
    for p in (DATA / name).iterdir():
        if p.suffix == ".gz":
            (d / p.name[:-3]).write_bytes(gzip.decompress(p.read_bytes()))
        else:
            shutil.copy(p, d / p.name)
    return d


@contextmanager
def offline():
    """a test never downloads: anything not in the cache fails the test."""

    def refuse(*args, **kwargs):
        raise AssertionError(f"a test tried to download: {args[:1]}")

    with mock.patch("mapbuild.download._request", refuse), mock.patch(
        "mapbuild.download._file", refuse
    ):
        yield
