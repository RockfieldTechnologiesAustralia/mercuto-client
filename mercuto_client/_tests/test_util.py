
import os
import shutil
from pathlib import Path

from .. import util


def test_get_free_space_excluding_files_with_real_dir(tmp_path: Path):
    # Start with an empty directory
    du = shutil.disk_usage(tmp_path)
    initial_estimate = util.get_free_space_excluding_files(str(tmp_path))

    # For an empty dir, estimate should match current free space
    assert initial_estimate == du.free

    # Create some files totaling a few MiB
    sizes = [1 * 1024 * 1024, 10 * 1024 * 1024, 512 * 1024]  # 1MiB, 10MiB, 512KiB
    for idx, size in enumerate(sizes, start=1):
        p = tmp_path / f"file_{idx}.bin"
        with open(p, "wb") as f:
            f.write(os.urandom(size))

    # Add a subdirectory with more files
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    sub_sizes = [2 * 1024 * 1024, 3 * 1024 * 1024]  # 2MiB, 3MiB
    for idx, size in enumerate(sub_sizes, start=1):
        p = subdir / f"subfile_{idx}.bin"
        with open(p, "wb") as f:
            f.write(os.urandom(size))

    # After adding files, the function adds back their sizes, so the estimate
    # should remain effectively the same as before. Allow minor FS overhead.
    after_estimate = util.get_free_space_excluding_files(str(tmp_path))

    # Tolerance accounts for filesystem metadata/cluster rounding
    tolerance = 64 * 1024  # 64 KiB
    assert abs(after_estimate - initial_estimate) <= tolerance

    # Ensure the total size using the get_directory_size() function matches
    assert util.get_directory_size(str(tmp_path)) == sum(sizes) + sum(sub_sizes)
