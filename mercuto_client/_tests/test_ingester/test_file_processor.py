import os
import sqlite3
import tempfile
import time
from typing import Generator, Tuple

import pytest

from ...ingester.processor import FileProcessor


def mock_process_callback(filepath: str) -> bool:
    return "success" in filepath  # Simulate success if filename contains "success"


@pytest.fixture
def temp_env() -> Generator[Tuple[FileProcessor, str, str], None, None]:
    """Setup temporary directory and database"""
    buffer_dir: str = tempfile.mkdtemp()
    workdir = tempfile.mkdtemp()
    db_path: str = os.path.join(workdir, "test_buffer.db")

    processor: FileProcessor = FileProcessor(
        buffer_dir=buffer_dir,
        db_path=db_path,
        max_files=3,
        max_attempts=2,
        process_callback=mock_process_callback
    )

    yield processor, buffer_dir, db_path

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


def test_init_db(temp_env: Tuple[FileProcessor, str, str]) -> None:
    """Verify database initialization"""
    processor, _, db_path = temp_env
    conn: sqlite3.Connection = sqlite3.connect(db_path)
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='file_buffer'")
    assert cursor.fetchone() is not None  # Table should exist
    conn.close()


def test_register_file(temp_env: Tuple[FileProcessor, str, str]) -> None:
    """Check if new files are correctly registered in the database"""
    processor, buffer_dir, _ = temp_env
    test_file: str = os.path.join(buffer_dir, "file1.txt")

    # Create a test file
    with open(test_file, "w") as f:
        f.write("Test content")

    processor.add_file_to_db(test_file)

    conn: sqlite3.Connection = sqlite3.connect(processor.get_db_path())
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(
        "SELECT filename FROM file_buffer WHERE filename = 'file1.txt'")
    assert cursor.fetchone() is not None  # File should be registered
    conn.close()


def test_file_processing(temp_env: Tuple[FileProcessor, str, str]) -> None:
    """Verify file processing and persistence"""
    processor, buffer_dir, _ = temp_env
    test_file: str = os.path.join(buffer_dir, "success_file.txt")

    with open(test_file, "w") as f:
        f.write("Test content")

    processor.add_file_to_db(test_file)
    processor.process_next_file()

    conn: sqlite3.Connection = sqlite3.connect(processor.get_db_path())
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(
        "SELECT status FROM file_buffer WHERE filename = 'success_file.txt'")
    # File should be marked as processed
    assert cursor.fetchone()[0] == "processed"
    conn.close()


def test_file_processing_in_order(temp_env: Tuple[FileProcessor, str, str]) -> None:
    """Verify file processing and persistence"""
    processor, buffer_dir, _ = temp_env

    # Make some test files but with a reverse name so the order on the filesystem is not the same as the order in the database
    for i in reversed(range(5)):
        test_file: str = os.path.join(buffer_dir, f"success_file_{i}.txt")
        with open(test_file, "w") as f:
            f.write("Test content")

        processor.add_file_to_db(test_file)

    for i in reversed(range(5)):
        processed = processor.process_next_file()
        assert processed is not None, "Should process a file"
        name = os.path.basename(processed)
        assert name == f'success_file_{i}.txt', f"Should process files in order, got {name}"


def test_retry_attempts(temp_env: Tuple[FileProcessor, str, str]) -> None:
    """Ensure failed files are retried up to max_attempts"""
    processor, buffer_dir, _ = temp_env
    test_file: str = os.path.join(buffer_dir, "fail_file.txt")

    with open(test_file, "w") as f:
        f.write("Test content")

    processor.add_file_to_db(test_file)

    for _ in range(2):
        processor.process_next_file()

    conn: sqlite3.Connection = sqlite3.connect(processor.get_db_path())
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(
        "SELECT attempts FROM file_buffer WHERE filename = 'fail_file.txt'")
    # Should match max_attempts
    assert cursor.fetchone()[0] == 2
    conn.close()


@pytest.mark.parametrize("filename_part", ["success", "unprocessed", "failed"])
def test_cleanup_old_files_different_processing_status(temp_env: Tuple[FileProcessor, str, str], filename_part: str) -> None:
    """Ensure cleanup keeps only max_files, no matter the file status"""
    processor, buffer_dir, _ = temp_env

    # Create more files than max_files limit
    for i in range(5):
        test_file: str = os.path.join(buffer_dir, f"{filename_part}{i}.txt")
        with open(test_file, "w") as f:
            f.write("Test content")
        processor.add_file_to_db(test_file)
        if filename_part != 'unprocessed':
            # Process files that are not unprocessed
            processor.process_next_file()

    processor.cleanup_old_files()

    conn: sqlite3.Connection = sqlite3.connect(processor.get_db_path())
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM file_buffer")
    # Should retain only max_files
    assert cursor.fetchone()[0] == 3

    # The last fiiles should be index 2,3,4
    cursor.execute(
        "SELECT filename FROM file_buffer ORDER BY timestamp ASC")
    remaining_files: list[tuple[str]] = cursor.fetchall()
    expected_files = [f"{filename_part}2.txt", f"{filename_part}3.txt", f"{filename_part}4.txt"]
    assert [f[0] for f in remaining_files] == expected_files

    conn.close()


def test_scan_existing_files(temp_env: Tuple[FileProcessor, str, str]) -> None:
    """Ensure that new files added are detected"""
    processor, buffer_dir, _ = temp_env

    for i in range(5):
        test_file = os.path.join(buffer_dir, f"file{i}.txt")
        with open(test_file, "w") as f:
            f.write("Test content")
        time.sleep(0.05)

    processor.scan_existing_files()
    conn: sqlite3.Connection = sqlite3.connect(processor.get_db_path())
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(
        "SELECT filename FROM file_buffer ORDER BY timestamp asc")

    files: list[tuple[str]] = cursor.fetchall()
    conn.close()
    assert files == [('file0.txt',), ('file1.txt',), ('file2.txt',), ('file3.txt',), ('file4.txt',)]


def test_scan_existing_files_that_havnt_been_processed(temp_env: Tuple[FileProcessor, str, str]) -> None:
    """Ensure that new files added are detected"""
    processor, buffer_dir, _ = temp_env

    for i in range(5):
        test_file = os.path.join(buffer_dir, f"file{i}.txt")
        with open(test_file, "w") as f:
            f.write("Test content")
        time.sleep(0.05)

        if i < 3:
            # Simulate adding for the first 3 files
            processor.add_file_to_db(test_file)
        if i < 2:
            # Simulate processing for the first 2 files
            processor.process_next_file()

    time.sleep(0.05)
    processor.scan_existing_files()
    conn: sqlite3.Connection = sqlite3.connect(processor.get_db_path())
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(
        "SELECT filename FROM file_buffer ORDER BY timestamp asc")

    files: list[tuple[str]] = cursor.fetchall()
    conn.close()
    assert files == [('file0.txt',), ('file1.txt',), ('file2.txt',), ('file3.txt',), ('file4.txt',)]
