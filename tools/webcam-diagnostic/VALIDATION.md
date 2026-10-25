# Webcam Diagnostic validation

Prepared on Windows with Python 3.12, OpenCV headless 4.13.0.92, NumPy 2.2.6 and
Tk 8.6. This distinguishes application checks from successful physical capture.

## Local checks

- **34 automated tests passed**. They use synthetic capture objects, spawned
  fictional workers, controlled hangs and mock event queries. No test opens a
  physical camera or reads real event logs.
- Coverage includes requested-versus-reported modes, property-set ordering,
  unknown/nonfinite properties, open/read failures, partial counts, native
  exception privacy, hung startup/read/cleanup, cancellation, child shutdown,
  bounded event-query metadata, injection-resistant filters, CLI exit behavior,
  exclusive/strict-JSON report creation and report-size limits.
- Three Tk tests cover idle startup, disabled mode controls, settings validation,
  report selection and the Start/Stop/result lifecycle without camera access.
  One dependency check loads the actual installed libraries and verifies the
  backend constants without opening a device.
- The desktop window was also visually inspected. The camera-free healthy demo
  was started through the window and completed, displaying SIMULATED status,
  a history row and metadata. No camera images were displayed or saved.
- One explicit five-second live test was attempted with camera index 0 and ANY.
  The device **did not open**; the app returned `open_failed`, zero frames and
  `worker_stopped: true`. The private receipt is not published. This checks that
  real failure handling is usable; it is not a successful camera capture test.

## Configured CI

The collection's source-check workflow installs the exact reviewed requirements
and runs this same suite on Windows/Ubuntu with Python 3.12/3.13. Tk tests are
required on Windows and in an Ubuntu virtual display. Native-library import is
checked, but CI opens no camera and reads no real device-event channel.
Current results are available in the repository Actions tab. Configuring a job
does not by itself establish that a particular workflow revision passed.

The repository's source gate checks the SHA-256 inventory, text-only content,
private-path/credential indicators, declared file types and local Markdown links.
It checks the publication tree, not arbitrary user-saved reports or dependencies.

## Remaining limitations

- Successful capture has not been demonstrated on a physical webcam in this
  release's local qualification. Camera/backend combinations, high-resolution
  modes, long sessions, hot unplugging and multi-camera systems need additional
  owner-driven hardware testing.
- macOS backend wiring is unqualified. Linux camera hardware is untested even
  when Linux synthetic/native-import tests pass.
- OpenCV property readback is backend-provided, not independent verification of
  physical camera settings. Delivered FPS also reflects host scheduling/pipeline
  behavior. The app does not identify a hardware or driver fault's root cause.
- USB event counts use an optional vendor/product filter, not a unique device
  instance. Unavailable query results remain unknown, not zero. No real event
  correlation has been qualified by the mock-query tests.
- The app does not change OS privacy/security/power settings or perform device
  repairs. A killed worker cannot promise restoration of driver-persistent mode
  choices. Reports intentionally exclude raw error details, which limits deeper
  native debugging.

Public camera/backend observations, reproducible failures, accessibility feedback
and suggestions are welcome through the linked issue forms in the README.
