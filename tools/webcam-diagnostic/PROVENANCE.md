# Source and dependency scope

This is original, assistant-assisted diagnostic application code for
Connor O'Shea / TheOutlandsDev. It generalizes an unpublished locally authored
camera probe, with new desktop controls, explicit settings, supervised capture,
bounded cancellation, camera-free demonstrations and reviewed metadata reports.
The owner authorized MIT publication. No upstream OpenCV/Tk/NumPy implementation,
third-party diagnostic program, game/mod code, virtual-camera bridge, driver,
actual capture or private event report is copied into this release.

The application, tests, fictional examples and documentation use the included
[MIT license](LICENSE). Private historical source and diagnostic receipts stay
outside the public tree. No earlier private script is relabeled as a tested
public release; device-reset/reinstall/power-control helpers are not bundled.

External software keeps its own applicable terms:

- [OpenCV 4.13 license](https://github.com/opencv/opencv/blob/4.13.0/LICENSE):
  Apache-2.0 for the OpenCV library.
- [OpenCV Python wheel project](https://github.com/opencv/opencv-python): its
  wrapper/packaging and bundled components have separate notices, including
  the third-party notice inventory included in the installed `cv2` package.
  See the wheel project's [licensing description](https://pypi.org/project/opencv-python-headless/4.13.0.92/#licensing).
  Obtain `opencv-python-headless==4.13.0.92` separately from
  [PyPI](https://pypi.org/project/opencv-python-headless/4.13.0.92/).
- [NumPy 2.2.6](https://github.com/numpy/numpy/blob/v2.2.6/LICENSE.txt): BSD-style
  source terms and notices for any components in separately installed wheels.
- Python, Tcl/Tk and the host operating system retain their own licenses. The
  app uses their public interfaces and includes none of their implementations.

No wheel, executable, native codec, Qt component or dependency source is shipped.
If a future distributor bundles dependencies, it must retain the applicable
upstream notices and satisfy their terms; this MIT file does not relicense them.
API documentation was consulted for capture/property behavior. The documentation
does not promise every backend/device implements every property.

Names of camera backends and applications describe interoperability. This is an
independent project without endorsement from camera, OS or library vendors.
