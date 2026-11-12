
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def save_proposals_safely(proposals, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True, exist_ok=True
    )

    backup_path = None

    if output_path.exists():
        backup_dir = output_path.parent / "backups"
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now(
            timezone.utc
        ).strftime("%Y%m%d_%H%M%S_%f")

        backup_path = backup_dir / (
            f"{output_path.stem}_{timestamp}.json"
        )

        shutil.copy2(output_path, backup_path)

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            json.dump(
                proposals,
                temp_file,
                indent=2,
                ensure_ascii=False,
            )
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = Path(temp_file.name)

        os.replace(temp_path, output_path)

    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()

    return backup_path


if __name__ == "__main__":
    print(
        "Proposal storage module ready. "
        "No files were modified."
    )
