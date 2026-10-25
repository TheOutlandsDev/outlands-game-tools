"""Synthetic camera, supervisor, report and optional UI tests. MIT."""
import dataclasses
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import diagnostic_core as core
import webcam_diagnostic as app


class Clock:
    def __init__(self):
        self.value = 0

    def __call__(self):
        return self.value


class Frame:
    shape = (480, 640, 3)
    size = 921600


class Capture:
    def __init__(self, clock, opened=True, fail_after=None, ignore=False, error=None):
        self.clock = clock
        self.opened = opened
        self.fail_after = fail_after
        self.ignore = ignore
        self.error = error
        self.frames = 0
        self.released = False
        self.set_calls = []
        self.values = {0: 640., 1: 480., 2: 30., 3: core.DemoCV.VideoWriter_fourcc(*'MJPG')}

    def isOpened(self):
        return self.opened

    def getBackendName(self):
        return 'SYNTHETIC'

    def set(self, prop, value):
        self.set_calls.append(prop)
        if not self.ignore:
            self.values[prop] = value
        return not self.ignore

    def get(self, prop):
        return self.values[prop]

    def read(self):
        self.clock.value += .1
        if self.error:
            raise RuntimeError(self.error)
        self.frames += 1
        if self.fail_after is not None and self.frames > self.fail_after:
            return False, None
        return True, Frame()

    def release(self):
        self.released = True


class CV(core.DemoCV):
    def __init__(self, capture):
        self.cap = capture

    def VideoCapture(self, index, backend):
        self.open_args = (index, backend)
        return self.cap


def hang_open(settings, scenario, connection):
    connection.send({'stage': 'opening'})
    time.sleep(30)


def crash_worker(settings, scenario, connection):
    connection.close()


def hang_configured(settings, scenario, connection):
    connection.send({'stage': 'configured', 'observations': {'width': 640}})
    connection.send({'stage': 'streaming', 'frames': 7, 'elapsed': .5})
    time.sleep(30)


class SettingsTests(unittest.TestCase):
    def test_valid_platform_backends(self):
        for system, backends in core.PLATFORMS.items():
            for backend in backends:
                core.Settings(backend=backend).validate(system)

    def test_platform_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            core.Settings(backend='DSHOW').validate('Linux')

    def test_invalid_scalar_inputs(self):
        for changes in [dict(index=-1), dict(index=64), dict(index=True), dict(seconds=0),
                        dict(seconds=float('nan')), dict(seconds=float('inf')), dict(seconds=True),
                        dict(open_timeout=61), dict(width=640), dict(width=1, height=480),
                        dict(width=640, height=True), dict(fps=0), dict(fps=float('inf')),
                        dict(fourcc='bad!'), dict(fourcc=4), dict(backend=[]), dict(usb_id='wrong')]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                core.Settings(**changes).validate('Windows')

    def test_usb_input_is_hex_and_windows_only(self):
        core.Settings(usb_id='1234:ABcd').validate('Windows')
        for value in ['1234:ABCD;Write-Output x', '123:ABCD', '1234:ABCDE', True]:
            with self.assertRaises(ValueError):
                core.Settings(usb_id=value).validate('Windows')
        with self.assertRaises(ValueError):
            core.Settings(usb_id='1234:ABCD').validate('Linux')

    def test_fourcc_and_nonfinite_values(self):
        encoded = core.DemoCV.VideoWriter_fourcc(*'MJPG')
        self.assertEqual(core.fourcc_text(encoded), 'MJPG')
        for value in [None, 0, -1, float('nan'), float('inf'), 0xffffffff, 'no']:
            self.assertIsNone(core.fourcc_text(value))
        self.assertIsNone(core.finite_number(float('nan')))


class CaptureTests(unittest.TestCase):
    def perform(self, settings=None, **kwargs):
        clock = Clock()
        cap = Capture(clock, **kwargs)
        cv = CV(cap)
        messages = []
        result = core.capture(settings or core.Settings(seconds=1), cv, messages.append, clock)
        return result, cap, cv, messages

    def test_native_defaults_do_not_set_any_properties(self):
        result, cap, cv, messages = self.perform()
        self.assertEqual(cap.set_calls, [])
        self.assertEqual(result['status'], 'completed')
        self.assertGreater(result['frames'], 0)
        self.assertTrue(cap.released)
        self.assertEqual(messages[0]['stage'], 'opening')
        self.assertEqual(result['max_read_seconds'], .1)

    def test_requested_mode_order_and_readback(self):
        result, cap, cv, messages = self.perform(core.Settings(index=3, width=1280, height=720, fps=15, fourcc='YUY2', seconds=1))
        self.assertEqual(cap.set_calls, [0, 1, 2, 3])
        self.assertEqual(cv.open_args[0], 3)
        self.assertEqual(set(result['mode_comparisons'].values()), {'matches'})
        self.assertEqual(result['mode_observations']['fourcc'], 'YUY2')

    def test_mode_mismatch_does_not_claim_exact_mode(self):
        result, cap, cv, messages = self.perform(core.Settings(width=1280, height=720, seconds=1), ignore=True)
        self.assertEqual(result['mode_comparisons']['width'], 'differs')
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(core.exit_code(result), 2)
        self.assertIn('differs', core.assessment(result))

    def test_unknown_property_is_not_a_mode_match(self):
        clock = Clock(); cap = Capture(clock); cap.values[2] = float('nan'); cap.ignore = True
        result = core.capture(core.Settings(fps=30, seconds=1), CV(cap), lambda _: None, clock)
        self.assertEqual(result['mode_comparisons']['fps'], 'unknown')
        self.assertIsNone(result['mode_observations']['fps'])
        json.dumps(result, allow_nan=False)

    def test_failed_open_is_released(self):
        result, cap, cv, messages = self.perform(opened=False)
        self.assertEqual(result['status'], 'open_failed')
        self.assertEqual(result['frames'], 0)
        self.assertTrue(cap.released)

    def test_read_failure_retains_partial_frame_count(self):
        result, cap, cv, messages = self.perform(fail_after=3)
        self.assertEqual((result['status'], result['frames'], result['read_failures']), ('read_failed', 3, 1))
        self.assertTrue(cap.released)

    def test_native_exception_text_is_not_retained(self):
        result, cap, cv, messages = self.perform(error='private-example-path-and-sensitive-content')
        self.assertEqual(result['status'], 'worker_failed')
        self.assertNotIn('sensitive-content', json.dumps(result))
        self.assertTrue(cap.released)

    def test_report_contains_metadata_not_pixels(self):
        result, cap, cv, messages = self.perform()
        self.assertEqual(result['last_frame_shape'], [480, 640, 3])
        self.assertNotIn('image', result)
        self.assertNotIn('frame', result)
        self.assertLess(len(json.dumps(result)), 4096)


class SupervisorTests(unittest.TestCase):
    def test_spawned_demo_healthy(self):
        result = core.run_probe(core.Settings(seconds=1, open_timeout=15), 'healthy')
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(result['simulated'])
        self.assertTrue(result['worker_stopped'])
        self.assertGreater(result['frames'], 0)
        self.assertEqual(core.exit_code(result), 0)

    def test_spawned_demo_failure(self):
        for scenario in ['open_failed', 'read_failed']:
            result = core.run_probe(core.Settings(seconds=1, open_timeout=15), scenario)
            self.assertEqual(result['status'], scenario)
            self.assertTrue(result['worker_stopped'])
            self.assertEqual(core.exit_code(result), 2)

    def test_hung_open_is_terminated_within_bound(self):
        start = time.monotonic()
        result = core.run_probe(core.Settings(seconds=1, open_timeout=1), target=hang_open)
        self.assertEqual(result['status'], 'timed_out')
        self.assertEqual(result['timeout_stage'], 'open_or_import')
        self.assertTrue(result['worker_stopped'])
        self.assertLess(time.monotonic() - start, 6)

    def test_cancellation_stops_child(self):
        cancel = threading.Event()
        timer = threading.Timer(.5, cancel.set)
        timer.start()
        try:
            result = core.run_probe(core.Settings(seconds=10), cancel=cancel, target=hang_open)
        finally:
            timer.cancel()
        self.assertEqual(result['status'], 'cancelled')
        self.assertTrue(result['worker_stopped'])
        self.assertEqual(core.exit_code(result), 130)

    def test_hung_read_or_cleanup_retains_progress(self):
        started = time.monotonic()
        result = core.run_probe(core.Settings(seconds=1), target=hang_configured)
        self.assertEqual(result['status'], 'timed_out')
        self.assertEqual(result['timeout_stage'], 'capture_or_cleanup')
        self.assertEqual(result['frames'], 7)
        self.assertEqual(result['mode_observations']['width'], 640)
        self.assertTrue(result['worker_stopped'])
        self.assertLess(time.monotonic() - started, 9)

    def test_cancel_before_start_never_spawns(self):
        cancel = threading.Event(); cancel.set()
        with patch('diagnostic_core.mp.get_context', side_effect=AssertionError('must not start')):
            result = core.run_probe(core.Settings(), cancel=cancel)
        self.assertEqual(result['status'], 'cancelled')

    def test_child_without_result_is_failed(self):
        result = core.run_probe(core.Settings(seconds=1), target=crash_worker)
        self.assertEqual(result['status'], 'worker_failed')
        self.assertTrue(result['worker_stopped'])

    def test_demo_cannot_query_events(self):
        # run_probe suppresses event access for all simulated workers.
        settings = core.Settings(seconds=1, usb_id='1234:ABCD' if sys.platform == 'win32' else None)
        with patch('diagnostic_core.query_usb_events', side_effect=AssertionError('unexpected OS query')):
            report = core.run_probe(settings, 'open_failed')
        self.assertEqual(report['usb_events']['status'], 'not_requested')
        self.assertNotIn('usb_id', report['request'])


class EventTests(unittest.TestCase):
    start = '2026-01-01T00:00:00.000+00:00'
    end = '2026-01-01T00:00:10.000+00:00'

    def test_no_filter_does_not_run_powershell(self):
        result = core.query_usb_events(None, self.start, self.end, runner=lambda *a, **k: self.fail('not requested'))
        self.assertEqual(result['status'], 'not_requested')

    def test_only_event_count_is_returned(self):
        calls = []
        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args, 0, b'{"status":"ok","matching_removals":2,"Message":"private"}', b'private stderr')
        result = core.query_usb_events('1234:ABCD', self.start, self.end, runner=runner, system='Windows')
        self.assertEqual(result, {'status': 'ok', 'matching_removals': 2})
        self.assertNotIn('private', json.dumps(result))
        self.assertIn('VID_1234&PID_ABCD', calls[0][0][-1])
        self.assertEqual(calls[0][1]['timeout'], 5)

    def test_query_failures_are_unavailable_not_zero(self):
        outputs = [b'bad-json', b'{"status":"ok","matching_removals":true}', b'{"status":"unavailable","matching_removals":null}', b'x' * 4097]
        for output in outputs:
            result = core.query_usb_events('1234:ABCD', self.start, self.end, runner=lambda *a, **k: subprocess.CompletedProcess([], 0, output, b''), system='Windows')
            self.assertEqual(result, {'status': 'unavailable', 'matching_removals': None})
        def timeout(*a, **k):
            raise subprocess.TimeoutExpired('powershell', 5)
        self.assertEqual(core.query_usb_events('1234:ABCD', self.start, self.end, runner=timeout, system='Windows')['status'], 'unavailable')

    def test_query_input_cannot_inject_shell_code(self):
        for identity, start in [('1234:ABCD;exit', self.start), ('1234:ABCD', "';exit")]:
            with self.assertRaises(ValueError):
                core.query_usb_events(identity, start, self.end, system='Windows')


class OutputAndCLITests(unittest.TestCase):
    def test_reports_are_exclusive_and_strict_json(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'report.json'
            report = core.base_report(core.Settings(), True)
            core.save_report(p, report)
            self.assertEqual(json.loads(p.read_text()), report)
            with self.assertRaises(FileExistsError):
                core.save_report(p, report)
            with self.assertRaises(ValueError):
                core.save_report(Path(directory) / 'bad.txt', report)
            with self.assertRaises(ValueError):
                core.save_report(Path(directory) / 'nan.json', {'value': float('nan')})
            self.assertFalse((Path(directory) / 'nan.json').exists())

    def test_report_size_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                core.save_report(Path(directory) / 'large.json', {'x': 'a' * 65536})

    def test_existing_output_refused_before_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'report.json'; p.write_text('keep')
            with patch('webcam_diagnostic.run_probe', side_effect=AssertionError('must not open camera')):
                with self.assertRaises(SystemExit) as error:
                    app.main(['--run', '--output', str(p)])
            self.assertEqual(error.exception.code, 1)
            self.assertEqual(p.read_text(), 'keep')

    def test_explicit_run_or_demo_is_required_for_cli_settings(self):
        with self.assertRaises(SystemExit) as error:
            app.main(['--index', '2'])
        self.assertEqual(error.exception.code, 2)

    def test_cli_demo_json_and_exit_codes(self):
        script = Path(app.__file__)
        for scenario, expected in [('healthy', 0), ('read_failed', 2)]:
            result = subprocess.run([sys.executable, '-B', str(script), '--demo', scenario, '--seconds', '1'], capture_output=True, timeout=20)
            self.assertEqual(result.returncode, expected, result.stderr)
            value = json.loads(result.stdout)
            self.assertTrue(value['simulated'])
            self.assertFalse(value['privacy']['frames_saved'])
            self.assertNotIn('usb_id', value['request'])


class UITests(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception as exc:
            if os.environ.get('WEBCAM_REQUIRE_TK') == '1':
                raise AssertionError('The required Tk display could not be initialized') from exc
            self.skipTest('Tk display unavailable: ' + type(exc).__name__)
        self.ui = app.DiagnosticApp(self.root)

    def tearDown(self):
        if hasattr(self, 'root'):
            self.root.destroy()

    def test_startup_is_idle_and_mode_requests_disabled(self):
        self.assertFalse(self.ui.busy)
        self.assertIn('No camera', self.ui.status.get())
        self.assertEqual(str(self.ui.mode_fields[0]['state']), 'disabled')

    def test_settings_validation_and_report_selection(self):
        self.ui.request_mode.set(True)
        self.ui.mode_state()
        self.ui.width.set('1280'); self.ui.height.set('720')
        self.assertEqual(self.ui.settings().width, 1280)
        self.ui.seconds.set('nan')
        with self.assertRaises(ValueError):
            self.ui.settings()
        report = core.base_report(core.Settings(), True)
        report.update(status='completed', assessment='Synthetic GUI test')
        self.ui.add_report(report)
        self.assertIs(self.ui.report, report)
        self.assertIn('Synthetic GUI test', self.ui.text.get('1.0', 'end'))

    def test_start_stop_and_result_controls_without_camera(self):
        entered = threading.Event()
        def controlled(settings, scenario, cancel, progress):
            entered.set()
            cancel.wait(3)
            report = core.base_report(settings, False)
            report.update(status='cancelled', assessment='Synthetic cancellation', worker_stopped=True)
            return report
        with patch('webcam_diagnostic.run_probe', side_effect=controlled):
            self.ui.start()
            self.assertTrue(entered.wait(1))
            self.assertTrue(self.ui.busy)
            self.assertEqual(str(self.ui.start_button['state']), 'disabled')
            self.ui.stop()
            deadline = time.monotonic() + 3
            while self.ui.busy and time.monotonic() < deadline:
                self.root.update()
                time.sleep(.02)
            self.assertFalse(self.ui.busy)
            self.assertEqual(self.ui.report['status'], 'cancelled')
            self.assertEqual(str(self.ui.save_button['state']), 'normal')


class DependencyTests(unittest.TestCase):
    def test_reviewed_libraries_and_backend_constants_without_camera(self):
        import cv2
        import numpy
        self.assertEqual(cv2.__version__, '4.13.0')
        self.assertEqual(numpy.__version__, '2.2.6')
        for name, value in core.BACKENDS.items():
            self.assertEqual(getattr(cv2, 'CAP_' + name), value)
        self.assertEqual(core.fourcc_text(cv2.VideoWriter_fourcc(*'MJPG')), 'MJPG')


if __name__ == '__main__':
    unittest.main()
