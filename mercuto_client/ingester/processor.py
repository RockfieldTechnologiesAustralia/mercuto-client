import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def _default_standard_clock(_: str):
    # Default clock function to get current time in seconds since epoch
    return datetime.now(timezone.utc).timestamp()


def _default_file_clock(filepath: str) -> float:
    # Default clock function to get file creation time in seconds since epoch
    return os.path.getctime(filepath)


def _default_free_space_checker(buffer_dir: str) -> float:
    """Returns the free space in MB on the partition where the buffer directory is located."""
    _, _, free = shutil.disk_usage(buffer_dir)
    return free / (1024 * 1024)


class FileProcessor:
    """
    System for processing files in a strict order with retry logic.

    Keeps an SQLite database to track files and their processing status.
    Keeps old files in the buffer and only deletes them once max_files is reached (whether processed or not).

    :param buffer_dir: Directory where files are stored
    :param db_path: Path to the SQLite database file for tracking file processing status.
    :param process_callback: Callable that processes a file. Should return True if processing is successful
    :param max_attempts: Maximum number of attempts to process a file before marking it as failed.
    :param max_files: Maximum number of files to keep in the buffer directory. If None, no limit is enforced.
    :param target_free_space_mb: Optional minimum free space in MB to keep on the partition where the buffer directory is located.
        This is combined with max_files to determine when to delete old files and takes precedence over max_files.
    :param clock: Optional callable that returns the timestamp for the file based on the filename. Takes in the file name as an argument
        and should return a float representing the timestamp in seconds since the epoch. Defaults to datetime.now().timestamp().
        This clock is NOT used when scanning existing files, it takes its own clock function.
    :param free_space_checker: Optional callable that returns the free space in MB on the partition where the buffer directory is located.
        Takes in the buffer directory path as an argument and should return a float representing the free space in MB.
        Defaults to checking the actual free space on the disk.


    Provides a callback for processing files, which should return True if successful.
    If processing fails, it retries up to max_attempts times before marking the file as failed.

    Periodically call `cleanup_old_files()` to remove old files from the buffer directory.
    Use `scan_existing_files()` to register files that were added while the system was offline.
    Use `process_next_file()` to process the next file in the buffer in strict order.
    Add files to the buffer using `add_file_to_db()`, or use `start_watching()` to automatically watch a directory for new files.

    Example usage:
    ```python
    processor = FileProcessor(...)
    processor.scan_existing_files()

    while True:
        processor.add_file_to_db("path/to/file.txt")
        processor.process_next_file()
    ```
    """

    def __init__(self, buffer_dir: str, db_path: str,
                 process_callback: Callable[[str], bool],
                 max_attempts: int,
                 max_files: Optional[int] = None,
                 target_free_space_mb: Optional[float] = None,
                 clock: Optional[Callable[[str], float]] = None,
                 free_space_checker: Optional[Callable[[str], float]] = None
                 ) -> None:
        self._buffer_dir = buffer_dir
        self._db_path = db_path
        self._max_files = max_files
        self._max_attempts = max_attempts
        self._process_callback = process_callback
        self._target_free_space_mb = target_free_space_mb
        self._clock = clock if clock is not None else _default_standard_clock
        self._free_space_checker = free_space_checker if free_space_checker is not None else _default_free_space_checker
        os.makedirs(self._buffer_dir, exist_ok=True)
        self._init_db()

    def get_db_path(self) -> str:
        """Returns the path to the SQLite database."""
        return self._db_path

    def get_buffer_dir(self) -> str:
        """Returns the path to the buffer directory."""
        return self._buffer_dir

    def _init_db(self) -> None:
        """Initialize SQLite database with attempt tracking."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_buffer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE,
            filepath TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            attempts INTEGER DEFAULT 0,
            timestamp REAL
        )
        """)
        conn.commit()
        conn.close()
        logger.info("Database initialized.")

    def scan_existing_files(self, clock: Optional[Callable[[str], float]] = None) -> None:
        """
        Detect files added while offline and process them.
        :param clock: Optional callable that returns the timestamp for the file based on the filename.
            If not provided, uses the file's creation time.
            This may be innaccurate if multiple files are added at once, or if the file system does not support accurate timestamps.

        """
        if clock is None:
            clock = _default_file_clock

        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        files_with_timestamps = [
            (filename, clock(os.path.join(self._buffer_dir, filename)))
            for filename in os.listdir(self._buffer_dir)
            if os.path.isfile(os.path.join(self._buffer_dir, filename))
        ]

        for filename, timestamp in sorted(files_with_timestamps, key=lambda x: x[1]):
            filepath = os.path.join(self._buffer_dir, filename)
            timestamp = clock(filepath)

            cursor.execute(
                "SELECT COUNT(*) FROM file_buffer WHERE filename = ?", (filename,))
            exists: int = cursor.fetchone()[0]

            if not exists:
                logger.info(f"Registering existing {filename} for processing...")
                cursor.execute("INSERT INTO file_buffer (filename, filepath, status, attempts, timestamp) VALUES (?, ?, 'pending', 0, ?)",
                               (filename, filepath, timestamp))

        conn.commit()
        conn.close()

    def process_next_file(self) -> Optional[str]:
        """
        Attempt to process the next file in the sequence (if exists), ensuring strict order.
        Returns the filepath of the processed file if successful or None if no pending files are found or failed.
        """
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT filepath, attempts FROM file_buffer WHERE status = 'pending' ORDER BY timestamp ASC LIMIT 1")

        pending_files: list[tuple[str, int]] = cursor.fetchall()
        conn.close()

        assert len(pending_files) <= 1, "More than one pending file found, which violates strict order."

        for (filepath, attempts) in pending_files:
            if self._process_file(filepath, attempts):
                return filepath
        return None

    def _process_file(self, filepath: str, attempts: int) -> bool:
        if not os.path.exists(filepath):
            logger.warning(f"File {filepath} does not exist. Skipping.")
            self._mark_as_failed(filepath)
        try:
            success: bool = self._process_callback(filepath)
        except Exception as e:
            logger.error(f"Processing error for {filepath}: {e}")
            success = False

        if success:
            self._mark_as_processed(filepath)
            return True

        if attempts >= self._max_attempts:
            logger.warning(
                f"Max retries reached for {filepath}. Moving to next file.")

            self._mark_as_failed(filepath)
            return True  # Give up and move to next file
        else:
            self._increment_attempt(filepath)
            return False

    def _increment_attempt(self, filepath: str) -> None:
        # Reopen DB to update attempt count
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE file_buffer SET attempts = attempts + 1 WHERE filepath = ?", (filepath,))
        conn.commit()
        conn.close()

    def _mark_as_failed(self, filepath: str) -> None:
        """Marks a file as failed in the database."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE file_buffer SET status = 'failed' WHERE filepath = ?", (filepath,))
        conn.commit()
        conn.close()
        logger.info(f"File {filepath} marked as failed.")

    def _mark_as_processed(self, filepath: str) -> None:
        """Marks a file as processed in the database."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE file_buffer SET status = 'processed' WHERE filepath = ?", (filepath,))
        conn.commit()
        conn.close()
        logger.info(f"File {filepath} marked as processed.")

    def cleanup_old_files_with_max_files(self) -> None:
        """Remove old files beyond the max file count."""
        if self._max_files is None:
            return
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT filepath FROM file_buffer ORDER BY timestamp DESC LIMIT -1 OFFSET ?", (self._max_files,))
        files_to_delete: list[tuple[str]] = cursor.fetchall()
        conn.close()

        for (filepath,) in reversed(files_to_delete):
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM file_buffer WHERE filepath = ?", (filepath,))
            conn.commit()
            conn.close()
            try:
                os.remove(filepath)
                logger.info(f"Deleted old file {filepath}")
            except FileNotFoundError:
                logger.warning(f"File {filepath} does not exist for deletion.")
            except Exception as e:
                logger.error(f"Error deleting file {filepath}: {e}")

    def cleanup_old_files(self) -> None:
        """Remove old files based on max_files and free space."""
        if self._max_files is not None:
            self.cleanup_old_files_with_max_files()

        if self._target_free_space_mb is not None:
            self.cleanup_old_files_with_free_space()

    def cleanup_old_files_with_free_space(self) -> None:
        """Remove old files ensuring free space is maintained."""
        if self._target_free_space_mb is None:
            return

        count = 0
        while self._free_space_checker(self._buffer_dir) < self._target_free_space_mb:
            if not self._delete_oldest_file():
                logger.warning("No more files to delete to free up space.")
                break
            count += 1
            if count > 1000:
                logger.error("Too many iterations trying to free space, aborting.")
                break

    def _delete_oldest_file(self) -> bool:
        """Deletes the oldest file in the buffer directory."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT filepath FROM file_buffer ORDER BY timestamp ASC LIMIT 1")
        oldest_file: Optional[tuple[str]] = cursor.fetchone()
        if not oldest_file:
            logger.info("No files to delete.")
            conn.close()
            return False

        filepath = oldest_file[0]
        cursor.execute(
            "DELETE FROM file_buffer WHERE filepath = ?", (filepath,))
        conn.commit()
        conn.close()
        try:
            os.remove(filepath)
            logger.info(f"Deleted oldest file {filepath}")
        except FileNotFoundError:
            logger.warning(f"Oldest file {filepath} does not exist.")
        except Exception as e:
            logger.error(f"Error deleting oldest file {filepath}: {e}")

        return True

    def add_file_to_db(self, filepath: str) -> None:
        """Adds a new file to database to be processed on the next call to process_next_file."""
        timestamp = self._clock(filepath)
        filename: str = os.path.basename(filepath)
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        cursor.execute("""
        INSERT OR IGNORE INTO file_buffer (filename, filepath, status, attempts, timestamp)
        VALUES (?, ?, 'pending', 0, ?)
        """, (filename, filepath, timestamp))

        conn.commit()
        conn.close()
