"""Module wrapper for processing images and records."""

from pathlib import Path
from run_pipeline import process_image
from state_store import StateStore


def process_single_image(image_path: str | Path, starting_file_no: int = 24, db_path: str | Path = "output/pipeline_state.db") -> dict:
    path = Path(image_path)
    store = StateStore(Path(db_path), starting_file_no=starting_file_no)
    return process_image(path, starting_file_no, store)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        res = process_single_image(sys.argv[1])
        print(f"Processed {sys.argv[1]}: {res.get('counts')}")
