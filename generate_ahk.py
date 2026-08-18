"""Generate a safety-first AutoHotkey v2 data-entry script."""

from pathlib import Path
from typing import Any, Dict, List


def ahk_escape(value: Any) -> str:
    """Escape an AutoHotkey v2 double-quoted string literal without dropping data."""
    text = str(value) if value is not None else ""
    return text.replace("`", "``").replace('"', '`"').replace("\r", "").replace("\n", "`n")


def generate_ahk(records: List[Dict[str, Any]], path: Path, review_count: int = 0) -> None:
    """Write an AHK v2 script for every complete 31-field OCR record."""
    scanned_records = [
        record for record in records
        if record.get("status") in {"VALIDATED", "REVIEW_REQUIRED"}
        and len(record.get("fields", {})) == 31
    ]
    lines = [
        "#Requires AutoHotkey v2.0",
        "#SingleInstance Force",
        "",
        "; Click the first field in the target form, then press F6.",
        "; Data is typed into the window active when F6 is pressed.",
        "KEY_DELAY_MS := 40",
        "TAB_DELAY_MS := 70",
        "PASTE_DELAY_MS := 80",
        "TOOLTIP_DURATION_MS := 3000",
        "SetKeyDelay(KEY_DELAY_MS, KEY_DELAY_MS)",
        "",
        "scanned_records := Map()",
        f"review_required_count := {review_count}",
        "current_record_index := 1",
        "is_entering := false",
        "",
    ]

    for index, record in enumerate(scanned_records, start=1):
        fields = record.get("fields", {})
        field_names = list(fields.keys())
        values = [field.get("value", "") for field in fields.values()]
        if len(values) != 31:
            continue
        lines.extend([
            f"; Scanned record {index} ({record.get('status', 'UNKNOWN')})",
            f"scanned_records[{index}] := {{",
            "    field_names: [" + ", ".join(f'"{ahk_escape(name)}"' for name in field_names) + "],",
            "    values: [" + ", ".join(f'"{ahk_escape(value)}"' for value in values) + "],",
            f'    status: "{ahk_escape(record.get("status", "UNKNOWN"))}"',
            "}",
            "",
        ])

    lines.extend([
        "F6::{",
        '    LogF6("F6 pressed")',
        "    EnterCurrentRecord()",
        "}",
        "",
        "Esc::{",
        "    ExitApp",
        "}",
        "",
        "EnterCurrentRecord()",
        "{",
        "    global KEY_DELAY_MS, TAB_DELAY_MS, PASTE_DELAY_MS",
        "    global TOOLTIP_DURATION_MS, scanned_records, review_required_count, current_record_index, is_entering",
        "",
        "    if (is_entering)",
        "    {",
        '        LogF6("F6 ignored: entry already in progress")',
        "        return",
        "    }",
        "    if (!scanned_records.Has(current_record_index))",
        "    {",
        '        LogF6("SCANNED records available: " scanned_records.Count " | REVIEW_REQUIRED records available: " review_required_count " | Reason: no scanned record")',
        '        ShowStatus("No scanned record available. Process an image first.")',
        "        return",
        "    }",
        "",
        "    record := scanned_records[current_record_index]",
        "    if (record.values.Length != 31)",
        "    {",
        '        ShowStatus("Scanned record does not contain 31 fields.")',
        "        return",
        "    }",
        "",
        "    target_window := WinExist(\"A\")",
        "    if (!target_window)",
        "    {",
        '        ShowStatus("No active data-entry window found.")',
        "        return",
        "    }",
        "    is_entering := true",
        '    ShowStatus("Entering record...")',
        "    try",
        "    {",
        "        for index, value in record.values",
        "        {",
        "            if (!WinActive(\"ahk_id \" target_window))",
        "            {",
        '                ShowStatus("Data-entry window is not active.")',
        "                return",
        "            }",
        "            SendText(value)",
        "            Sleep(PASTE_DELAY_MS)",
        "            if (index < 31)",
        "            {",
        '                Send("{Tab}")',
        "                Sleep(TAB_DELAY_MS)",
        "            }",
        "        }",
        "        current_record_index += 1",
        '        ShowStatus("Record entered successfully. Press F6 for the next record.")',
        "    }",
        "    finally",
        "    {",
        "        is_entering := false",
        "    }",
        "}",
        "",
        "ShowStatus(message)",
        "{",
        "    global TOOLTIP_DURATION_MS",
        "    ToolTip(message)",
        "    SetTimer(ClearStatus, -TOOLTIP_DURATION_MS)",
        "}",
        "",
        "ClearStatus()",
        "{",
        "    ToolTip()",
        "}",
        "",
        "LogF6(message)",
        "{",
        '    FileAppend(A_Now ": " message "`n", A_ScriptDir "\\f6_diagnostics.log")',
        "}",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
