#Requires AutoHotkey v2.0
#SingleInstance Force

; Click the first field in the target form, then press F6.
; Data is typed into the window active when F6 is pressed.
KEY_DELAY_MS := 40
TAB_DELAY_MS := 70
PASTE_DELAY_MS := 80
TOOLTIP_DURATION_MS := 3000
SetKeyDelay(KEY_DELAY_MS, KEY_DELAY_MS)

scanned_records := Map()
review_required_count := 0
current_record_index := 1
is_entering := false

; Scanned record 1 (VALIDATED)
scanned_records[1] := {
    field_names: ["File No", "Form No", "Title", "First Name", "Last Name", "Initial", "Email", "Father Name", "DOB", "Gender", "Profession", "Mailing Street", "City", "Postal Code", "Country", "Service Provider", "File Ref", "Reference No", "SIM No", "Network Type", "Mobile Model", "IMEI 1", "IMEI 2", "Plan Type", "Card Type", "Contact", "Issue Date", "Renewal Date", "Installments", "Amount in Words", "Remarks"],
    values: ["186", "737", "Ms", "Laura", "Askham", "MLA", "laura.askham@btinternet.com", "K. M.Askham", "14/07/1970", "Female", "Fixed Income", "Dean House", "Vernham Dean, Hampshire Andover, SWT", "SP11 0JZ", "UK", "T-Mobile", "Gama - 827304692", "T-M95ez|&1#&$U8376", "SEVkoX903741414SR76", "‘CDMA+GSM", "Nokia 2260", "099917149005542", "%S++*% - && - 259583 -6", "AlacartePack", "Master Card Silver", "774", "06/03/2020", "06/11/2023", "31.83", "Thirty One Point Eight Three", "Not Applicable"],
    status: "VALIDATED"
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
    global KEY_DELAY_MS, TAB_DELAY_MS, PASTE_DELAY_MS
    global TOOLTIP_DURATION_MS, scanned_records, review_required_count, current_record_index, is_entering

    if (is_entering)
    {
        LogF6("F6 ignored: entry already in progress")
        return
    }
    if (!scanned_records.Has(current_record_index))
    {
        LogF6("SCANNED records available: " scanned_records.Count " | REVIEW_REQUIRED records available: " review_required_count " | Reason: no scanned record")
        ShowStatus("No scanned record available. Process an image first.")
        return
    }

    record := scanned_records[current_record_index]
    if (record.values.Length != 31)
    {
        ShowStatus("Scanned record does not contain 31 fields.")
        return
    }

    target_window := WinExist("A")
    if (!target_window)
    {
        ShowStatus("No active data-entry window found.")
        return
    }
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
        current_record_index += 1
        ShowStatus("Record entered successfully. Press F6 for the next record.")
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
