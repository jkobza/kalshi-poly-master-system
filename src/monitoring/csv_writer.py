"""
Generic append-only CSV event writer.

Reusable for trade logs, opportunity logs, or any other row-oriented event stream.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterable, Mapping


class CsvEventWriter:
    """
    Append rows to a CSV file, creating the parent directory and header on first write.
    """

    def __init__(self, path: Path, fieldnames: Iterable[str]):
        self.path = Path(path)
        self.fieldnames = list(fieldnames)

    def append(self, row: Mapping[str, object]) -> None:
        """
        Append one row. Missing fields are written as empty strings.
        """
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            file_exists = self.path.exists()
            with self.path.open("a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerow({field: row.get(field, "") for field in self.fieldnames})
        except Exception:
            logging.exception("Failed to append CSV row to %s", self.path)
