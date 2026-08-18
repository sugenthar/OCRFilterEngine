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
    values: ["190", "754", "Prof", "Bal", "Garcha", "PBG", "bal.garcha@kepplestonemanor.com", "Rory Garcha", "27/04/1991", "Male", "Unemployed", "Kings Mills", "Derby, Derbyshire", "DE74 2RR", "England", "Vodafone", "Alpha-057964860", "Vfonel7iy!`"#&%:10", "TVOtgX855138352RE88", "GSM", "Siemens UI0", "540206 - 69 - 321695 - 0", "S#SS&@ -!+ - 914406-1", "SMS Value ++", "Master Card Premium Gold", "473", "09/05/2024", "09/05/2026", "30.03", "Thirty Point Zero Three", "Not Applicable"],
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
