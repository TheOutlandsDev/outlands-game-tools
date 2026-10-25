# Outlands Webcam Diagnostic

A desktop app and command-line tool for checking a webcam's capture behavior.
Choose a camera index and backend, run a timed test, compare reported mode values,
and export a small local JSON report. The code, tests, examples and documentation
are [MIT licensed](LICENSE). No game installation is needed.

The app reads and immediately discards video frames. It does not display or save
images, access audio, upload reports, reset devices, install drivers or change
power settings. Opening a camera may illuminate its indicator and prevent another
app from using it. Close conferencing/camera apps before testing.

## Install and open

Use Python **3.12 or 3.13**, including Tkinter for the desktop window. Download or
clone this repository, then open a terminal in `tools/webcam-diagnostic`. Keep
`webcam_diagnostic.py` and `diagnostic_core.py` together. The folder can also be
copied on its own with its LICENSE, requirements, examples and documentation.
Use the current main branch or its [source ZIP](https://github.com/TheOutlandsDev/outlands-game-tools/archive/refs/heads/main.zip);
the older collection v0.1.0 archive predates this app.

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
.\.venv\Scripts\python.exe webcam_diagnostic.py
```

Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
.venv/bin/python webcam_diagnostic.py
```

Tkinter is supplied with the standard Windows Python installer. On Linux it may
require your distribution's Python/Tk package and a graphical session. A headless
machine can use the CLI. The application uses Tk for its window; the separately
installed headless OpenCV package supplies camera access without Qt windows.
Install just this one OpenCV wheel variant in the virtual environment.

Pinned dependencies: OpenCV headless **4.13.0.92** and NumPy **2.2.6**.
They are downloaded separately and retain their own licenses; see
[dependency and source provenance](PROVENANCE.md). There is no bundled executable,
installer, camera driver, model, virtual-camera bridge or dependency binary.

## Try it without a camera

Open the desktop app and click **Run demo (no camera)**. Select `healthy`,
`read_failed` or `open_failed` to see different fictional outcomes. Every demo is
marked **SIMULATED** in the window and `simulated: true` in the report.
The demo opens no camera and queries no device events. It also works without
installing OpenCV; Python/Tk is sufficient for the desktop demo.

Command-line demos require only Python:

```text
python webcam_diagnostic.py --demo healthy --seconds 2
python webcam_diagnostic.py --demo read_failed --seconds 2
python webcam_diagnostic.py --demo open_failed --seconds 1
```

The first normally exits 0; the two intentional failure examples exit 2.
See [worked examples and fictional reports](examples/README.md).

## Run a real test

1. Set **Camera index**. Index 0 is a starting point, not a device identity. If
   it cannot open, check the camera's availability and try another known index.
   The app does not automatically enumerate/open every connected camera.
2. Choose **Backend**: Windows offers `ANY`, `DSHOW` and `MSMF`; Linux offers
   `ANY` and `V4L2`. `ANY` lets OpenCV choose. macOS `ANY`/`AVFOUNDATION` wiring
   exists, but macOS has not been qualified in this release.
3. Choose a **Duration**, from 1 to 1,800 seconds. **Open timeout** bounds child
   startup, dependency import, camera opening and mode configuration, from 1 to
   60 seconds. A slow system may need a larger startup timeout.
4. Initially leave **Request a mode** unchecked. This makes no property-set calls
   and uses camera defaults. To compare a requested mode, check the box and set
   width, height, FPS and FOURCC. `MJPG` and `YUY2` are common examples, not a
   guarantee of support. FOURCC is applied last because some backends reopen the
   stream when FPS changes.
5. Click **Start camera test**. **Stop** cancels the isolated worker. Closing the
   window while testing requests cancellation and waits for shutdown. A stuck
   native open/read/release is terminated, then killed if needed. One active test
   runs at a time. If an optional event query is running, it can take up to five
   additional seconds to finish.
6. The result table retains the latest 20 reports in memory. Select a row to
   inspect its JSON. Run another backend/mode and compare the rows. **Save selected
   report** creates a new `.json` file; existing files are never replaced.

No report is saved automatically. There is no camera preview, recording, ongoing
background monitoring, automatic reconnection loop or repair action.

CLI examples (use the virtual environment's Python):

```text
python webcam_diagnostic.py --run --index 0 --backend ANY --seconds 10
python webcam_diagnostic.py --run --index 0 --backend DSHOW --seconds 30 --width 640 --height 480 --fps 30 --fourcc MJPG --output webcam-dshow.json
python webcam_diagnostic.py --run --index 0 --backend MSMF --seconds 30 --output webcam-msmf.json
```

The last two commands are Windows examples. On Linux use `V4L2` or `ANY`.
CLI capture requires `--run`; invoking the script without arguments opens the
idle desktop window. `--help` opens neither a camera nor the GUI.
An existing CLI output file is rejected before starting capture; exclusive
creation is checked again when saving. Parent output directories must exist.
The explicit output path may be any writable local location selected by you;
this is not a filesystem containment/race-hardening utility.

### Optional Windows USB removal-event count

Leave **USB VID:PID** blank to skip event-log access. If you know the four-digit
hex vendor and product IDs, supply `VID:PID`. A **fictional syntax example** is
`1234:ABCD`; use your device's actual model IDs for a meaningful filter:

```text
python webcam_diagnostic.py --run --seconds 10 --usb-id 1234:ABCD
```

The optional query counts Kernel-PnP Device Management event 1010 entries in the
test's UTC time window, filtered by that model ID. It returns a count or
`unavailable`; an inaccessible/unsupported query is not treated as zero events.
It exports no messages, instance IDs, serials or selected filter value. A model
ID can match multiple devices and is **not linked to the camera index**. A match
is correlation for further investigation, not proof of which device failed or
whether its cable, power, driver or electronics caused the problem. No other
event channels are scanned and administrator privileges are not requested.

## Interpret a report

| Field/result | Meaning |
| --- | --- |
| `completed` | The worker read frames for the requested window; this alone does not mean the requested mode matched. |
| `open_failed` | The selected index/backend did not open. Availability, permissions, an unsupported backend or other causes remain possible. |
| `read_failed` | A read returned no usable frame. The report retains the number received before the failure. |
| `timed_out` | Startup/configuration or capture/cleanup exceeded its bound; the child was stopped. Partial periodic progress may be available. |
| `cancelled` | Stop/Ctrl+C was requested. |
| `dependency_missing` / `worker_failed` | The dependency could not import or the child did not return a usable result. Raw exception/native logs are deliberately omitted. |
| `mode_observations` | Backend-reported width, height, FPS and FOURCC. Unsupported/nonfinite values become null/unknown. |
| `mode_comparisons` | Requested versus reported values: matches, differs or unknown. Readback is not independent proof of the camera's wire format. |
| `observed_fps` | Delivered frame count divided by measured stream time, affected by the host and capture pipeline. |
| `max_read_seconds` | Longest completed read call; a hung read instead produces the supervisor timeout. |
| `last_frame_shape` | Shape of the last received frame, without its pixels. Compare it with reported dimensions. |
| `worker_stopped` | Whether the supervised process was stopped. No automatic device reset is attempted. |

CLI exit codes: **0** completed without a reported-mode mismatch or matching
removal events; **2** diagnostic finding/failure; **130** cancelled; **1** input or
report-output error. Argparse usage errors can also return 2. Unknown mode values
and unavailable USB events do not become a positive compatibility claim.

OpenCV documents that property behavior depends on the backend, OS, driver and
hardware. See its [VideoCapture documentation](https://docs.opencv.org/4.13.0/d8/dfe/classcv_1_1VideoCapture.html).
A short completed test does not establish long-term stability, compatibility
with Teams/OBS/browser calls, or a hardware diagnosis. Requested settings can
affect camera behavior during capture; the app does not promise driver-level
restoration of persistent mode choices after a crash or forced termination.

## Privacy and testing

Reports contain UTC timestamps, OS family, software versions, camera index,
requested/reported modes and frame/event counts. They intentionally omit images,
audio, host/user names, USB instance IDs, raw logs and arbitrary exception text.
There is no telemetry, upload service, account or API key. Review metadata before
sharing it publicly; the app is not a general-purpose secret-redaction service.

Run the [test suite](tests/test_diagnostic.py) after installing requirements:

```text
python -B -m unittest discover -s tests -v
```

Tests use fictional captures and isolated child processes, never camera hardware
or real event logs. They cover native-call hangs, cancellation, mode readbacks,
privacy, CLI behavior, file protection, the dependency API and the Tk controls.
Without a display, GUI tests skip unless `WEBCAM_REQUIRE_TK=1` is set. CI requires
the GUI tests on Windows and in an Ubuntu virtual display. See
[validation evidence and remaining limits](VALIDATION.md).

## Suggestions and bugs

[Suggest an improvement](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=feature_or_suggestion.yml)
or [report a webcam-app problem](https://github.com/TheOutlandsDev/outlands-game-tools/issues/new?template=webcam_diagnostic.yml).
Testing another camera/backend, improving instructions, accessibility feedback
and small reproducible examples are all welcome. No code contribution is needed.
Include OS/Python/OpenCV versions, backend, whether the run was simulated, the
expected result and a minimal reviewed metadata excerpt. Do not post recordings,
raw Windows logs, serials, private paths, credentials or other people's images.
