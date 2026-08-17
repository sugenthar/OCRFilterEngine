"""Generate a safety-first AutoHotkey v2 data-entry script."""

from pathlib import Path
from typing import Any, Dict, List


def ahk_escape(value: Any) -> str:
    """Escape an AutoHotkey v2 double-quoted string literal without dropping data."""
    text = str(value) if value is not None else ""
    return text.replace("`", "``").replace('"', '`"').replace("\r", "").replace("\n", "`n")


def generate_ahk(records: List[Dict[str, Any]], path: Path, review_count: int = 0) -> None:
    """Write an AHK v2 script containing only validated records and F6/Escape hotkeys."""
    validated_records = [record for record in records if record.get("status") == "VALIDATED"]
    lines = [
        "#Requires AutoHotkey v2.0",
        "#SingleInstance Force",
        "",
        "; Set this to a distinctive title or ahk_exe selector for the data-entry application.",
        "; Leaving it blank disables F6 rather than sending data to an arbitrary window.",
        'TARGET_WINDOW_TITLE := ""',
        "KEY_DELAY_MS := 40",
        "TAB_DELAY_MS := 70",
        "PASTE_DELAY_MS := 80",
        "TOOLTIP_DURATION_MS := 3000",
        "SetKeyDelay(KEY_DELAY_MS, KEY_DELAY_MS)",
        "",
        "validated_records := Map()",
        f"review_required_count := {review_count}",
        "current_record_index := 1",
        "is_entering := false",
        "",
    ]

    for index, record in enumerate(validated_records, start=1):
        fields = record.get("fields", {})
        field_names = list(fields.keys())
        values = [field.get("value", "") for field in fields.values()]
        if len(values) != 31:
            continue
        lines.extend([
            f"; Validated record {index}",
            f"validated_records[{index}] := {{",
            "    field_names: [" + ", ".join(f'"{ahk_escape(name)}"' for name in field_names) + "],",
            "    values: [" + ", ".join(f'"{ahk_escape(value)}"' for value in values) + "]",
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
        "    global TARGET_WINDOW_TITLE, KEY_DELAY_MS, TAB_DELAY_MS, PASTE_DELAY_MS",
        "    global TOOLTIP_DURATION_MS, validated_records, review_required_count, current_record_index, is_entering",
        "",
        "    if (is_entering)",
        "    {",
        '        LogF6("F6 ignored: entry already in progress")',
        "        return",
        "    }",
        "    if (!validated_records.Has(current_record_index))",
        "    {",
        '        LogF6("VALIDATED records available: " validated_records.Count " | REVIEW_REQUIRED records available: " review_required_count " | Reason: no validated record")',
        '        ShowStatus("No VALIDATED record available.")',
        "        return",
        "    }",
        "    if (TARGET_WINDOW_TITLE = \"\" || !WinActive(TARGET_WINDOW_TITLE))",
        "    {",
        '        LogF6("F6 blocked: configured data-entry window is not active")',
        '        ShowStatus("Open the configured data-entry form first.")',
        "        return",
        "    }",
        "",
        "    record := validated_records[current_record_index]",
        "    if (record.values.Length != 31)",
        "    {",
        '        ShowStatus("Validated record does not contain 31 fields.")',
        "        return",
        "    }",
        "",
        "    target_window := WinExist(\"A\")",
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
        '        ShowStatus("Record entered successfully.")',
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
