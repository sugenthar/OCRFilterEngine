"""Advanced Data Entry Automation Pipeline with OCR Preprocessing, Validation, and State Persistence."""

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageOps

from calculations import calculate_fields
from extract_fields import extract_record
from field_extractor import (
    group_rows_into_records,
    group_words_into_rows,
    read_ocr_words,
)
from generate_ahk import generate_ahk
from ocr import (
    BoundingBox,
    ImageQualityReport,
    OCRRow,
    OCRToken,
    RawRecord,
    TesseractEngine,
    analyze_image_quality,
    cluster_tokens_into_rows,
    convert_image_for_ocr,
    re_ocr_region,
    segment_rows_into_records,
)
from ocr.field_localization import attach_token_span_regions, locate_field_regions
from ocr.targeted_ocr import run_multi_pass_targeted_ocr
from state_store import StateStore
from validator import validate_record

OUTPUT = Path("output")
INBOX = Path("images/inbox")
ARCHIVE = Path("images/archive")
HD_ARCHIVE = ARCHIVE / "hd"
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write JSON through a sibling temporary file so readers never see partial JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary_path.replace(path)


def write_conversion_proof(conversion: Any, source_digest: str) -> Dict[str, Any]:
    """Write a checksum sidecar next to the archived HD image before OCR starts."""
    converted_path = Path(conversion.output_path)
    proof_path = converted_path.with_suffix(".json")
    proof = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_sha256": source_digest,
        "converted_sha256": StateStore.file_hash(converted_path),
        "conversion": conversion.to_dict(),
    }
    atomic_write_json(proof_path, proof)
    proof["proof_path"] = str(proof_path)
    return proof


def configure_logging() -> None:
    OUTPUT.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(OUTPUT / "pipeline.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def read_positive_integer(prompt: str) -> int:
    """Read a positive integer without accepting blank, decimal, or negative input."""
    while True:
        raw_value = input(prompt).strip()
        if raw_value.isdigit() and int(raw_value) > 0:
            return int(raw_value)
        print("Please enter a positive integer.")


def read_yes_no(prompt: str) -> bool:
    """Read an explicit yes/no decision; never silently select a default."""
    while True:
        answer = input(prompt).strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please enter Y or N.")


def configure_daily_watch_session(store: StateStore) -> int:
    """Interactively establish a safe daily watcher session without resetting history."""
    state = store.numbering_state()
    print("\n" + "=" * 60)
    print("       DATA ENTRY AUTOMATION - DAILY STARTUP")
    print("=" * 60)
    print("\nPrevious saved numbering:\n")
    print(f"    File No              : {state['file_no']}")
    print(f"    Last Form No         : {state['last_form_no'] if state['last_form_no'] is not None else 'None'}")
    print(f"    Next Form No         : {state['next_form_no']}")

    if read_yes_no("\nContinue with previous numbering? [Y/N]: "):
        store.record_continuation_session()
        logging.info("Daily startup session initialized: continuing existing numbering state")
        logging.info("Active File No: %s | Next Form No: %s", state["file_no"], state["next_form_no"])
        print("\nUsing saved numbering.")
        print(f"\n    File No              : {state['file_no']}")
        print(f"    Starting Form No     : {state['next_form_no']}")
        return int(state["file_no"])

    logging.info("Operator selected new daily numbering configuration")
    while True:
        file_no = read_positive_integer("\nEnter today's File No: ")
        form_no = read_positive_integer("Enter today's Starting Form No: ")
        valid, reason = store.validate_new_numbering(file_no, form_no)
        if not valid:
            print(f"\nWARNING: {reason}")
            logging.warning("New numbering configuration rejected: %s", reason)
            continue

        print("\n" + "-" * 60)
        print("New numbering configuration\n")
        print(f"File No              : {file_no}")
        print(f"Starting Form No     : {form_no}")
        print("-" * 60)
        if not read_yes_no("\nStart watcher with these values? [Y/N]: "):
            print("\nConfiguration cancelled. Please enter new values.")
            continue

        store.start_daily_session(file_no, form_no)
        logging.info("New daily numbering configuration confirmed: File No=%s Starting Form No=%s", file_no, form_no)
        print("\nConfiguration saved. Starting watcher...")
        return file_no


def record_fingerprint(record: Dict[str, Any]) -> str:
    """Generate deterministic SHA256 signature for a record based on raw OCR text values."""
    values = "|".join(data.get("raw_text", "") for data in record.get("fields", {}).values())
    return hashlib.sha256(values.encode("utf-8")).hexdigest()


def wait_for_file_stability(path: Path, timeout: float = 12.0, check_interval: float = 0.5) -> bool:
    """Ensure the file copy has completely finished and the image can be successfully decoded."""
    start_time = time.time()
    last_signature: Optional[Tuple[int, int]] = None
    stable_checks = 0

    while time.time() - start_time < timeout:
        if not path.exists() or not path.is_file():
            return False
        try:
            stat = path.stat()
            signature = (stat.st_size, stat.st_mtime_ns)
            if stat.st_size == 0:
                logging.info("IMAGE WAITING FOR FILE CONTENT: %s (SIZE=0)", path.name)
                last_signature = None
                stable_checks = 0
            elif signature == last_signature:
                stable_checks += 1
            else:
                logging.info("IMAGE STABILITY CHECK: %s (SIZE=%d)", path.name, stat.st_size)
                last_signature = signature
                stable_checks = 1
            if stable_checks >= 2:
                with Image.open(path) as img:
                    img.verify()
                logging.info("IMAGE DECODE OK: %s", path.name)
                return True
        except (PermissionError, OSError, Image.UnidentifiedImageError):
            pass
        time.sleep(check_interval)

    # Final attempt
    try:
        if path.exists() and path.stat().st_size > 0:
            with Image.open(path) as img:
                img.verify()
            return True
    except Exception:
        pass

    return False


def attach_field_regions(ocr_record: Dict[str, Any], record: Dict[str, Any]) -> None:
    """Attach label-anchored field regions and provenance to the extracted record."""
    regions = locate_field_regions(RawRecord.from_dict(ocr_record))
    for field_name, region in regions.items():
        record["fields"].setdefault(field_name, {})["field_region"] = region.to_dict()
        logging.info(
            "FIELD REGION: Record=%s Field=%s Label=%r Label bbox=%s Value region=%s Region confidence=%.2f",
            record.get("record_number"), field_name, region.anchor_label,
            region.label_bbox.to_dict(), region.value_bbox.to_dict(), region.confidence,
        )
    # Fallback to token spans for fields without explicit inline labels
    attach_token_span_regions(record["fields"])


def create_debug_image(path: Path, record: Dict[str, Any]) -> Path:
    """Render extracted regions and token bounds for visual localization inspection."""
    debug_dir = OUTPUT / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(path) as source:
        canvas = ImageOps.exif_transpose(source).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    colors = {
        "IMEI 1": "lime",
        "IMEI 2": "blue",
        "Postal Code": "yellow",
        "Reference No": "orange",
        "Email": "purple",
        "Mobile Model": "cyan",
        "SIM No": "magenta",
        "Contact": "deepskyblue",
    }

    for name, field in record["fields"].items():
        color = colors.get(name, "red")
        # Draw individual token bounding boxes
        for box in field.get("coordinates", []):
            draw.rectangle((box["x"], box["y"], box["x"] + box["width"], box["y"] + box["height"]), outline=color, width=1)
        
        region_info = field.get("field_region", {})
        region = region_info.get("region")
        if region:
            rx, ry, rw, rh = region["x"], region["y"], region["width"], region["height"]
            draw.rectangle((rx, ry, rx + rw, ry + rh), outline=color, width=3)
            draw.text((rx, max(0, ry - 14)), name, fill=color)

        label_box = region_info.get("anchor_bbox")
        if label_box and region_info.get("anchor_label"):
            lx, ly, lw, lh = label_box["x"], label_box["y"], label_box["width"], label_box["height"]
            draw.rectangle((lx, ly, lx + lw, ly + lh), outline="white", width=1)

    result = debug_dir / f"debug_{path.stem}_record_{record.get('record_number', 1)}.png"
    canvas.save(result)
    return result


def run_targeted_retries(path: Path, record: Dict[str, Any], issues: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Re-read uncertain bounded fields using multi-pass targeted OCR and candidate consensus."""
    failed_fields = {issue["field"] for issue in issues}
    localization_issues: List[Dict[str, str]] = []

    for name, field in record["fields"].items():
        if name not in failed_fields and not field.get("needs_review"):
            continue

        region_data = field.get("field_region", {}).get("region")
        if not region_data:
            field["targeted_ocr"] = {"attempted": False, "decision": "FIELD_REGION_NOT_LOCATED"}
            localization_issues.append({
                "field": name,
                "reason": "FIELD_REGION_NOT_LOCATED",
                "detail": f"No field region was located for {name}; broad scanning is forbidden.",
            })
            continue

        bbox = BoundingBox(
            x=region_data["x"],
            y=region_data["y"],
            width=region_data["width"],
            height=region_data["height"],
        )

        logging.info("TARGETED OCR START: Record=%s Field=%s Region=%s", record.get("record_number"), name, bbox.to_dict())
        retry_res = run_multi_pass_targeted_ocr(path, name, bbox)
        field["targeted_ocr"] = retry_res

        decision = retry_res.get("decision", "NO_SAFE_CORRECTION")
        if decision in ("ACCEPTED_STRICT_IMEI", "ACCEPTED_POSTCODE", "ACCEPTED_CONSENSUS"):
            new_val = retry_res["value"]
            new_conf = retry_res.get("confidence", 85.0)
            new_tokens = retry_res.get("tokens", [])
            coords = [
                {"x": t["x"], "y": t["y"], "width": t["width"], "height": t["height"]}
                for t in new_tokens if isinstance(t, dict) and "x" in t
            ]
            field.update({
                "value": new_val,
                "raw_text": retry_res.get("raw_text", new_val),
                "confidence": new_conf,
                "needs_review": False,
                "coordinates": coords if coords else field.get("coordinates", []),
                "source_tokens": new_tokens if new_tokens else field.get("source_tokens", []),
            })
            logging.info(
                "TARGETED OCR ACCEPTED: Record=%s Field=%s Value=%r Conf=%.1f Decision=%s",
                record.get("record_number"), name, new_val, new_conf, decision,
            )
        else:
            logging.warning(
                "TARGETED OCR FAILED: Record=%s Field=%s Decision=%s Reason=%s",
                record.get("record_number"), name, decision, retry_res.get("reason", "NO_SAFE_CORRECTION"),
            )

    return localization_issues


def attach_review_evidence(record: Dict[str, Any], issues: List[Dict[str, str]]) -> None:
    """Make every review decision inspectable in JSON and the pipeline log."""
    reasons: Dict[str, List[str]] = {}
    for issue in issues:
        reasons.setdefault(issue["field"], []).append(issue["reason"])

    for name, field in record["fields"].items():
        field["normalized_value"] = field.get("value", "")
        field["validation"] = "REVIEW" if name in reasons else "PASS"
        field["failure_reasons"] = reasons.get(name, [])
        field.setdefault("targeted_ocr", {"attempted": False, "decision": "NOT_REQUIRED"})
        if name in reasons:
            logging.warning(
                "RECORD %s FIELD %s | raw=%r normalized=%r confidence=%s validation=REVIEW reasons=%s targeted=%s",
                record.get("record_number"), name, field.get("raw_text"), field.get("value"),
                field.get("confidence"), ",".join(reasons[name]), field["targeted_ocr"],
            )

    if issues:
        logging.warning("RECORD %s STATUS: REVIEW_REQUIRED", record.get("record_number"))
    else:
        logging.info("RECORD %s STATUS: VALIDATED", record.get("record_number"))


def run_ocr_and_segmentation(
    path: Path,
    variant: str = "A",
    engine: Optional[TesseractEngine] = None,
    coordinate_scale: float = 1.0,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Execute OCR, row clustering, and segmentation with original-image coordinates."""
    if engine is None:
        engine = TesseractEngine()

    tokens, _ = engine.run_ocr(path, variant=variant, psm=6, coordinate_scale=coordinate_scale)
    rows = cluster_tokens_into_rows(tokens)
    records, unassigned = segment_rows_into_records(rows)
    return [rec.to_dict() for rec in records], [un.to_dict() for un in unassigned]


def debug_ocr_image(path: Path) -> List[Path]:
    """Generate annotated OCR localization images for inspection."""
    engine = TesseractEngine()
    debug_path = OUTPUT / "converted" / f"{path.stem}_debug_hd.png"
    conversion = convert_image_for_ocr(path, debug_path)
    records, _ = run_ocr_and_segmentation(
        debug_path, variant="C", engine=engine, coordinate_scale=conversion.scale
    )
    debug_images: List[Path] = []
    for raw_record in records:
        record = extract_record(raw_record, "DEBUG", 0)
        attach_field_regions(raw_record, record)
        debug_images.append(create_debug_image(path, record))
    return debug_images


def process_image(
    path: Path,
    starting_file_no: int,
    store: StateStore,
    engine: Optional[TesseractEngine] = None,
    retry_existing: bool = False,
) -> Dict[str, Any]:
    """Process a single image file through OCR, extraction, validation, persistence, and AHK generation."""
    if engine is None:
        engine = TesseractEngine()

    digest = store.file_hash(path)
    if store.image_seen(digest) and not retry_existing:
        logging.info("Skipped duplicate image: %s", path.name)
        return {"image": str(path), "skipped_duplicate": True, "records": []}

    try:
        # Step 1: Create and archive the HD OCR source before scanning it.
        # OCR reads this exact archived image, while the original is retained
        # for audit and targeted field retries.
        converted_path = HD_ARCHIVE / f"{path.stem}_{digest[:12]}_hd.png"
        conversion = convert_image_for_ocr(path, converted_path)
        conversion_proof = write_conversion_proof(conversion, digest)
        logging.info(
            "HD ARCHIVE CREATED BEFORE OCR: %s %sx%s -> %sx%s (scale %.2fx, proof=%s)",
            path.name,
            conversion.original_size[0], conversion.original_size[1],
            conversion.converted_size[0], conversion.converted_size[1],
            conversion.scale,
            conversion_proof["proof_path"],
        )

        # Step 2: Quality analysis of the converted OCR source.
        quality_report = analyze_image_quality(converted_path)
        if not quality_report.is_valid:
            logging.warning("Image quality issue on %s: %s", path.name, quality_report.error)
            if quality_report.is_blank:
                logging.error("ZERO_RECORD_IMAGE: %s is blank/corrupt", path.name)
                (OUTPUT / "failed_records.json").write_text(
                    json.dumps({"image": str(path), "error": "ZERO_RECORD_IMAGE (blank/corrupt)", "records": []}, indent=2),
                    encoding="utf-8",
                )
                return {"image": str(path), "records": [], "counts": {"VALIDATED": 0, "REVIEW_REQUIRED": 0, "FAILED": 1}}

        # Step 3: Multi-pass OCR evaluation of the archived HD copy.
        ocr_candidates = []
        variants = ["A", "B", "C"]
        if quality_report.contrast < 20:
            variants.append("D")
        for variant in variants:
            candidate_records, candidate_unassigned = run_ocr_and_segmentation(
                converted_path, variant=variant, engine=engine, coordinate_scale=conversion.scale
            )
            confidences = [
                word.get("confidence", 0.0)
                for candidate in candidate_records
                for row in candidate.get("rows", [])
                for word in row.get("words", [])
            ]
            average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            ocr_candidates.append((candidate_records, candidate_unassigned, average_confidence, variant))
            logging.info(
                "OCR variant %s on %s: records=%d mean_confidence=%.1f",
                variant, path.name, len(candidate_records), average_confidence,
            )

        ocr_records, unassigned_rows, _, selected_variant = max(
            ocr_candidates,
            key=lambda item: (bool(item[0]), item[2]),
        )
        logging.info("Selected OCR variant %s for %s", selected_variant, path.name)

        if not ocr_records:
            logging.error("ZERO_RECORD_IMAGE: No records detected in %s", path.name)
            (OUTPUT / "failed_records.json").write_text(
                json.dumps({"image": str(path), "error": "ZERO_RECORD_IMAGE", "records": []}, indent=2),
                encoding="utf-8",
            )
            return {"image": str(path), "records": [], "counts": {"VALIDATED": 0, "REVIEW_REQUIRED": 0, "FAILED": 1}}

        # Step 4: Allocate unique File No (only after OCR verifies valid content)
        assigned_file_no = store.get_or_allocate_file_no(digest, starting_file_no=starting_file_no)
        file_no_str = str(assigned_file_no)

        records: List[Dict[str, Any]] = []
        for ocr_record in ocr_records:
            provisional = extract_record(ocr_record, file_no_str, 0)
            fingerprint = record_fingerprint(provisional)
            form_no = store.form_no_for(fingerprint)
            record = extract_record(ocr_record, file_no_str, form_no)
            attach_field_regions(ocr_record, record)
            
            logging.info("FIELD OWNERSHIP: Record=%s Field=Mobile Model Tokens=%r", record.get("record_number"), record["fields"].get("Mobile Model", {}).get("raw_text"))
            logging.info("FIELD OWNERSHIP: Record=%s Field=IMEI 1 Tokens=%r", record.get("record_number"), record["fields"].get("IMEI 1", {}).get("raw_text"))

            calculate_fields(record)
            issues = validate_record(record)
            if issues:
                localization_issues = run_targeted_retries(path, record, issues)
                calculate_fields(record)
                issues = validate_record(record) + localization_issues
            attach_review_evidence(record, issues)
            
            if os.environ.get("DEBUG_OCR_FIELDS", "").lower() in {"1", "true", "yes"}:
                debug_path = create_debug_image(path, record)
                record["debug_image"] = str(debug_path)
                logging.info("OCR field debug image: %s", debug_path)

            record["issues"] = issues
            record["status"] = "VALIDATED" if not issues else "REVIEW_REQUIRED"
            record["fingerprint"] = fingerprint
            store.set_record_status(fingerprint, record["status"])
            records.append(record)

        result = {
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "image": str(path),
            "converted_image": str(converted_path),
            "conversion": conversion.to_dict(),
            "conversion_proof": conversion_proof,
            "file_no": assigned_file_no,
            "ocr_variant": selected_variant,
            "image_quality": quality_report.summary(),
            "record_count": len(records),
            "unassigned_rows": unassigned_rows,
            "records": records,
        }

        # Atomic writes to output files
        OUTPUT.mkdir(parents=True, exist_ok=True)
        atomic_write_json(OUTPUT / "structured_data.json", result)

        successful = [r for r in records if r["status"] == "VALIDATED"]
        review = [r for r in records if r["status"] == "REVIEW_REQUIRED"]

        atomic_write_json(OUTPUT / "successful_records.json", {"image": str(path), "file_no": assigned_file_no, "records": successful})
        atomic_write_json(OUTPUT / "review.json", {"image": str(path), "file_no": assigned_file_no, "records": review})
        atomic_write_json(OUTPUT / "failed_records.json", {"image": str(path), "records": []})
        atomic_write_json(OUTPUT / f"records_file_{assigned_file_no}.json", result)

        # Generate F6 data-entry for every complete scanned record. Validation
        # results remain in JSON but never suppress a scanned record from F6.
        generate_ahk(records, OUTPUT / "data_entry.ahk", review_count=len(review))
        store.mark_image_processed(digest, assigned_file_no, path)

        counts = {"VALIDATED": len(successful), "REVIEW_REQUIRED": len(review), "FAILED": 0}
        logging.info("Processed %s (File No %d): %s", path.name, assigned_file_no, counts)
        return {**result, "counts": counts}

    except Exception as error:
        logging.exception("Failed to process %s", path)
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / "failed_records.json").write_text(
            json.dumps({"image": str(path), "error": str(error), "records": []}, indent=2),
            encoding="utf-8",
        )
        return {"image": str(path), "records": [], "counts": {"VALIDATED": 0, "REVIEW_REQUIRED": 0, "FAILED": 1}}


def archive_image(path: Path) -> None:
    """Move processed image safely from inbox to archive."""
    try:
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        destination = ARCHIVE / path.name
        if destination.exists():
            destination = ARCHIVE / f"{path.stem}_{int(time.time())}{path.suffix}"
        shutil.move(str(path), str(destination))
    except Exception as exc:
        logging.warning("Could not archive %s: %s", path.name, exc)


def rebuild_ahk_from_latest_output(output_dir: Path = OUTPUT) -> Tuple[int, int]:
    """Rebuild F6 data entry from the latest successful and review JSON files."""
    records: List[Dict[str, Any]] = []
    review_count = 0
    seen = set()
    for filename in ("successful_records.json", "review.json"):
        path = output_dir / filename
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        source_records = payload.get("records", [])
        if filename == "review.json":
            review_count = len(source_records)
        for record in source_records:
            key = record.get("fingerprint") or f"{record.get('form_no')}:{record.get('record_number')}"
            if key in seen:
                continue
            seen.add(key)
            records.append(record)

    generate_ahk(records, output_dir / "data_entry.ahk", review_count=review_count)
    return len(records), review_count


def watch_inbox(starting_file_no: int, store: StateStore, poll_interval: float = 1.0) -> None:
    """Continuously monitor images/inbox for newly dropped images and process them sequentially."""
    INBOX.mkdir(parents=True, exist_ok=True)
    logging.info(
        "Watching %s for new images (.png, .jpg, .jpeg, .bmp, .webp). Polling latency ~1s. Ctrl+C to stop.",
        INBOX,
    )

    seen_in_loop = set()
    engine = TesseractEngine()

    while True:
        try:
            candidates = sorted(
                [p for p in INBOX.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_TYPES],
                key=lambda p: p.stat().st_mtime,
            )
            for image in candidates:
                if str(image) not in seen_in_loop:
                    seen_in_loop.add(str(image))
                    logging.info("Image detected: %s (size: %d bytes)", image.name, image.stat().st_size)

                if not wait_for_file_stability(image):
                    continue

                logging.info("Image ready: %s (file stable and readable)", image.name)
                logging.info("Processing started: %s", image.name)

                result = process_image(image, starting_file_no, store, engine=engine)
                logging.info("Processing completed: %s", image.name)
                seen_in_loop.discard(str(image))

                archive_image(image)

        except KeyboardInterrupt:
            raise
        except Exception as e:
            logging.exception("Error during watcher cycle: %s", e)

        time.sleep(poll_interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Advanced Data Entry Automation Pipeline")
    parser.add_argument("--file-no", type=int, default=None, help="Starting File No (default 28). Increments by 1 every 4 images.")
    parser.add_argument("--starting-form-no", type=int, default=None, help="Starting Form No (default 110). Persistent sequential Form No.")
    parser.add_argument("--once", type=Path, help="Process one image immediately.")
    parser.add_argument("--watch", action="store_true", help="Continuously process new images in images/inbox.")
    parser.add_argument("--reset", action="store_true", help="Reset state store counters to starting File No (28) and Form No (110).")
    parser.add_argument("--review", action="store_true", help="Show detailed reasons for records currently awaiting review.")
    parser.add_argument("--rebuild-ahk", action="store_true", help="Rebuild the F6 script from the latest scanned JSON records.")
    parser.add_argument(
        "--continue-session", action="store_true",
        help="Start --watch with the saved numbering state and without an interactive prompt.",
    )
    parser.add_argument("--debug-ocr", type=Path, help="Generate annotated OCR field-localization images without allocation.")
    parser.add_argument("--interval", type=int, default=120, help="Preserved for compatibility. In watch mode, detection runs every ~1s.")
    args = parser.parse_args()

    if args.continue_session and not args.watch:
        parser.error("--continue-session can only be used with --watch")

    if not args.once and not args.watch and not args.reset and not args.review and not args.rebuild_ahk and not args.debug_ocr:
        parser.error("choose --once IMAGE, --watch, --review, --rebuild-ahk, --debug-ocr IMAGE, or --reset")

    configure_logging()
    store = StateStore(OUTPUT / "pipeline_state.db")

    if args.reset:
        target_form = args.starting_form_no if args.starting_form_no is not None else 110
        target_file = args.file_no if args.file_no is not None else 28
        store.reset_state(starting_form_no=target_form, starting_file_no=target_file)
        logging.info("StateStore successfully reset: Starting File No = %d, Starting Form No = %d", target_file, target_form)
        if not args.once and not args.watch:
            print(f"State reset: File No = {target_file}, Form No = {target_form}")
            return

    if args.review:
        review_path = OUTPUT / "review.json"
        if not review_path.exists():
            print("No review output exists yet.")
            return
        review_data = json.loads(review_path.read_text(encoding="utf-8"))
        records = review_data.get("records", [])
        print(f"Review records: {len(records)}")
        for record in records:
            print(f"\nRecord {record.get('record_number')} (Form {record.get('form_no')}):")
            for issue in record.get("issues", []):
                field = record.get("fields", {}).get(issue["field"], {})
                print(
                    f"- {issue['field']}: {issue['reason']} | raw={field.get('raw_text')!r} "
                    f"| value={field.get('value')!r} | confidence={field.get('confidence')} "
                    f"| targeted={field.get('targeted_ocr', {}).get('decision', 'NOT_RUN')}"
                )
        return

    if args.rebuild_ahk:
        record_count, review_count = rebuild_ahk_from_latest_output()
        print(f"F6 script rebuilt: {record_count} scanned record(s), {review_count} review warning(s).")
        print(f"Output: {OUTPUT / 'data_entry.ahk'}")
        return

    if args.debug_ocr:
        images = debug_ocr_image(args.debug_ocr)
        if images:
            print("Debug images:")
            for image in images:
                print(image)
        else:
            print("No records detected; no debug image created.")
        return

    if args.starting_form_no is not None and not args.reset and not args.watch:
        store.set_next_form_no(args.starting_form_no)
    if args.file_no is not None and not args.reset and not args.watch:
        store.set_starting_file_no(args.file_no)

    highest_form = store.get_highest_form_no()
    next_form = store.get_next_form_no()
    highest_file = store.get_highest_file_no()
    next_file = store.get_next_file_no()

    logging.info(
        "StateStore active | Form No: max=%s, next=%s | File No: max=%s, next=%s",
        highest_form,
        next_form,
        highest_file,
        next_file,
    )

    starting_file_no = args.file_no if args.file_no is not None else store.get_next_file_no()

    if args.once:
        result = process_image(args.once, starting_file_no, store)
        print(json.dumps(result.get("counts", {}), indent=2))
        return

    try:
        if args.continue_session:
            starting_file_no = store.get_next_file_no()
            logging.info("Watcher continuing saved numbering without an interactive prompt.")
        else:
            starting_file_no = configure_daily_watch_session(store)
        watch_inbox(starting_file_no, store, poll_interval=1.0)
    except KeyboardInterrupt:
        logging.info("Watcher stopped safely.")


if __name__ == "__main__":
    main()
