#Requires AutoHotkey v2.0
#SingleInstance Force

; Set this to a distinctive title or ahk_exe selector for the data-entry application.
; Leaving it blank disables F6 rather than sending data to an arbitrary window.
TARGET_WINDOW_TITLE := ""
KEY_DELAY_MS := 40
TAB_DELAY_MS := 70
PASTE_DELAY_MS := 80
TOOLTIP_DURATION_MS := 3000
SetKeyDelay(KEY_DELAY_MS, KEY_DELAY_MS)

validated_records := Map()
review_required_count := 1
current_record_index := 1
is_entering := false

F6::{
    LogF6("F6 pressed")
    EnterCurrentRecord()
}

Esc::{
    ExitApp
}

EnterCurrentRecord()
{
    global TARGET_WINDOW_TITLE, KEY_DELAY_MS, TAB_DELAY_MS, PASTE_DELAY_MS
    global TOOLTIP_DURATION_MS, validated_records, review_required_count, current_record_index, is_entering

    if (is_entering)
    {
        LogF6("F6 ignored: entry already in progress")
        return
    }
    if (!validated_records.Has(current_record_index))
    {
        LogF6("VALIDATED records available: " validated_records.Count " | REVIEW_REQUIRED records available: " review_required_count " | Reason: no validated record")
        ShowStatus("No VALIDATED record available.")
        return
    }
    if (TARGET_WINDOW_TITLE = "" || !WinActive(TARGET_WINDOW_TITLE))
    {
        LogF6("F6 blocked: configured data-entry window is not active")
        ShowStatus("Open the configured data-entry form first.")
        return
    }

    record := validated_records[current_record_index]
    if (record.values.Length != 31)
    {
        ShowStatus("Validated record does not contain 31 fields.")
        return
    }

    target_window := WinExist("A")
    is_entering := true
    ShowStatus("Entering record...")
    try
    {
        for index, value in record.values
        {
            if (!WinActive("ahk_id " target_window))
            {
                ShowStatus("Data-entry window is not active.")
                return
            }
            SendText(value)
            Sleep(PASTE_DELAY_MS)
            if (index < 31)
            {
                Send("{Tab}")
                Sleep(TAB_DELAY_MS)
            }
        }
        ShowStatus("Record entered successfully.")
    }
    finally
    {
        is_entering := false
    }
}

ShowStatus(message)
{
    global TOOLTIP_DURATION_MS
    ToolTip(message)
    SetTimer(ClearStatus, -TOOLTIP_DURATION_MS)
}

ClearStatus()
{
    ToolTip()
}

LogF6(message)
{
    FileAppend(A_Now ": " message "`n", A_ScriptDir "\f6_diagnostics.log")
}
