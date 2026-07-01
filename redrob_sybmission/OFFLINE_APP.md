# WorkDNA offline application

Do not open `web/index.html` directly. Browsers block React module imports and
local API requests from `file://` pages.

## Start on Windows

Double-click:

`START_WORKDNA.bat`

Or run:

```powershell
.\START_WORKDNA.ps1
```

Then use:

```text
http://127.0.0.1:8765
```

The local Python server:

- serves the compiled React frontend;
- loads the supplied 100,000-candidate dataset;
- executes the saved WorkDNA model;
- accepts compatible `.jsonl` and `.json` imports;
- exports the ranked shortlist as CSV;
- makes no hosted AI or ranking API calls.

## Stop

Close the terminal running WorkDNA or press `Ctrl+C`.
