# OCR Data Entry Automation

This Windows project converts an incoming form screenshot to an HD PNG, stores
that conversion for audit, extracts 31 fields with Tesseract OCR, and generates
an AutoHotkey v2 script. Pressing **F6** types the current scanned record into
the form window that is active when F6 is pressed.

## What each computer needs

- Windows 10 or Windows 11
- Python 3.11 or newer, available as `python`
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) for Windows
- AutoHotkey v2, required only for F6 data entry
- Git, to clone the repository

If Tesseract is not installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`,
set its executable path before starting the project:

```powershell
$env:TESSERACT_CMD = 'D:\Apps\Tesseract-OCR\tesseract.exe'
```

## First-time setup

Open PowerShell in the cloned project folder and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
```

The setup script creates `.venv`, installs the required Python packages, makes
the runtime folders, and checks the two Windows applications.

## Run the automation

Start the watcher:

```powershell
.\scripts\start-watcher.ps1
```

Place a screenshot in `images\inbox\`.

The workflow is:

```text
Screenshot → HD conversion → images\archive\hd\ → OCR → JSON → data_entry.ahk → F6
```

The HD PNG and its JSON checksum sidecar are stored in `images\archive\hd\`.
The generated script is `output\data_entry.ahk`.

To use F6, open the target data-entry form, click its first field, and press
F6. F6 enters one 31-field record and moves to the next record for the next F6
press.

## Sharing safely with Git

Do **not** publish this current working repository: it already contains form
screenshots, output JSON, and database history. Instead create a new clean copy:

```powershell
.\scripts\create-shareable-copy.ps1
cd ..\OCR-Shareable
git init
git add .
git commit -m "Initial portable OCR automation"
git branch -M main
git remote add origin <YOUR-GIT-REPOSITORY-URL>
git push -u origin main
```

Your friend can then run:

```powershell
git clone <YOUR-GIT-REPOSITORY-URL>
cd OCR-Shareable
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\start-watcher.ps1
```

The clean-copy script intentionally excludes screenshots, OCR output, databases,
logs, AutoHotkey output, Python caches, and nested duplicate projects.
