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
review_required_count := 0
current_record_index := 1
is_entering := false

; Validated record 1
validated_records[1] := {
    field_names: ["File No", "Form No", "Title", "First Name", "Last Name", "Initial", "Email", "Father Name", "DOB", "Gender", "Profession", "Mailing Street", "City", "Postal Code", "Country", "Service Provider", "File Ref", "Reference No", "SIM No", "Network Type", "Mobile Model", "IMEI 1", "IMEI 2", "Plan Type", "Card Type", "Contact", "Issue Date", "Renewal Date", "Installments", "Amount in Words", "Remarks"],
    values: ["approved-1", "approved-2", "approved-3", "approved-4", "approved-5", "approved-6", "approved-7", "approved-8", "approved-9", "approved-10", "approved-11", "approved-12", "approved-13", "approved-14", "approved-15", "approved-16", "approved-17", "approved-18", "approved-19", "approved-20", "approved-21", "approved-22", "approved-23", "approved-24", "approved-25", "approved-26", "approved-27", "approved-28", "approved-29", "approved-30", "approved-31"]
}

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
