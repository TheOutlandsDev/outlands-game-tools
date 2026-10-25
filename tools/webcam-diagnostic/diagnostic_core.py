"""Original webcam diagnostic core. MIT; no frame recording or device repair."""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
import math
import multiprocessing as mp
import os
import platform
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

VERSION = '1.0.0'
BACKENDS = {'ANY': 0, 'DSHOW': 700, 'MSMF': 1400, 'V4L2': 200, 'AVFOUNDATION': 1200}
PLATFORMS = {'Windows': {'ANY', 'DSHOW', 'MSMF'}, 'Linux': {'ANY', 'V4L2'},
             'Darwin': {'ANY', 'AVFOUNDATION'}}
STATUSES = {'completed', 'open_failed', 'read_failed', 'worker_failed',
            'dependency_missing', 'cancelled', 'timed_out'}


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='milliseconds')


@dataclasses.dataclass(frozen=True)
class Settings:
    index: int = 0
    backend: str = 'ANY'
    seconds: float = 10.0
    open_timeout: float = 10.0
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    fourcc: str | None = None
    usb_id: str | None = None

    def validate(self, system=None):
        system = platform.system() if system is None else system
        if type(self.index) is not int or not 0 <= self.index <= 63:
            raise ValueError('Camera index must be an integer from 0 to 63.')
        if not isinstance(self.backend, str) or self.backend not in PLATFORMS.get(system, {'ANY'}):
            raise ValueError('Backend is not supported on this operating system.')
        for label, value, lower, upper in [('Duration', self.seconds, 1, 1800),
                                         ('Open timeout', self.open_timeout, 1, 60)]:
            if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError(f'{label} must be between {lower} and {upper} seconds.')
        if (self.width is None) != (self.height is None):
            raise ValueError('Supply both width and height, or neither.')
        for value in [self.width, self.height]:
            if value is not None and (type(value) is not int or not 16 <= value <= 8192):
                raise ValueError('Requested dimensions must be integers from 16 to 8192.')
        if self.fps is not None and (type(self.fps) not in (int, float) or not math.isfinite(self.fps) or not 1 <= self.fps <= 240):
            raise ValueError('Requested FPS must be between 1 and 240.')
        if self.fourcc is not None and (not isinstance(self.fourcc, str) or not re.fullmatch(r'[A-Z0-9]{4}', self.fourcc)):
            raise ValueError('FOURCC must contain four uppercase letters/digits, such as MJPG.')
        if self.usb_id is not None:
            if system != 'Windows' or not isinstance(self.usb_id, str) or not re.fullmatch(r'[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}', self.usb_id):
                raise ValueError('Optional Windows USB ID must have the form VID:PID (four hex digits each).')
        return self


def finite_number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def fourcc_text(value):
    value = finite_number(value)
    if value is None or not 0 < value <= 0xffffffff:
        return None
    chars = ''.join(chr((int(value) >> (8 * i)) & 255) for i in range(4))
    return chars if all(32 <= ord(c) <= 126 for c in chars) else None


def base_report(settings, simulated):
    request = dataclasses.asdict(settings)
    request.pop('usb_id')
    return {'schema': 'outlands-webcam-diagnostic/1', 'app_version': VERSION,
            'simulated': bool(simulated), 'platform': platform.system(),
            'started_utc': utc_now(), 'request': request,
            'status': 'worker_failed', 'frames': 0, 'read_failures': 0,
            'stream_seconds': 0.0, 'observed_fps': None,
            'mode_observations': {}, 'mode_comparisons': {},
            'usb_events': {'status': 'not_requested', 'matching_removals': None},
            'privacy': {'frames_saved': False, 'audio_accessed': False,
                        'raw_native_logs_included': False, 'device_instance_ids_included': False}}


def capture(settings, cv, send, clock=time.monotonic):
    """Read and immediately discard frames. Caller must isolate native calls."""
    report = {'status': 'worker_failed', 'frames': 0, 'read_failures': 0,
              'stream_seconds': 0.0, 'observed_fps': None,
              'mode_observations': {}, 'mode_comparisons': {}, 'max_read_seconds': 0.0}
    cap = None
    props = {'width': cv.CAP_PROP_FRAME_WIDTH, 'height': cv.CAP_PROP_FRAME_HEIGHT,
             'fps': cv.CAP_PROP_FPS, 'fourcc': cv.CAP_PROP_FOURCC}
    started = None
    try:
        send({'stage': 'opening'})
        cap = cv.VideoCapture(settings.index, BACKENDS[settings.backend])
        if not cap.isOpened():
            report['status'] = 'open_failed'
            return report
        report['opencv_version'] = str(cv.__version__)[:40]
        try:
            name = cap.getBackendName()
            report['actual_backend'] = name if re.fullmatch(r'[A-Za-z0-9_ .-]{1,40}', name) else 'unknown'
        except Exception:
            report['actual_backend'] = 'unknown'
        report['set_results'] = {}
        # FPS may reopen a DirectShow stream: always apply FOURCC last.
        for name in ['width', 'height', 'fps', 'fourcc']:
            value = getattr(settings, name)
            if value is not None:
                actual = cv.VideoWriter_fourcc(*value) if name == 'fourcc' else value
                report['set_results'][name] = bool(cap.set(props[name], actual))
        for name, prop in props.items():
            value = finite_number(cap.get(prop))
            report['mode_observations'][name] = fourcc_text(value) if name == 'fourcc' else value
            requested = getattr(settings, name)
            if requested is not None:
                observed = report['mode_observations'][name]
                # Zero from get() can also mean unsupported, not a negotiated mode.
                if observed is None or (name != 'fourcc' and observed <= 0):
                    comparison = 'unknown'
                elif name == 'fourcc':
                    comparison = 'matches' if observed == requested else 'differs'
                else:
                    comparison = 'matches' if abs(observed - requested) <= (0.5 if name == 'fps' else 0.01) else 'differs'
                report['mode_comparisons'][name] = comparison
        send({'stage': 'configured', 'observations': report['mode_observations']})
        started = clock()
        last_progress = started
        report['status'] = 'completed'
        while clock() - started < settings.seconds:
            read_start = clock()
            ok, frame = cap.read()
            report['max_read_seconds'] = round(max(report['max_read_seconds'], clock() - read_start), 3)
            if not ok or frame is None or getattr(frame, 'size', 0) == 0:
                report['read_failures'] += 1
                report['status'] = 'read_failed'
                break
            report['frames'] += 1
            shape = getattr(frame, 'shape', ())
            if len(shape) in (2, 3):
                report['last_frame_shape'] = [int(x) for x in shape]
            del frame
            now = clock()
            if now - last_progress >= 1:
                send({'stage': 'streaming', 'frames': report['frames'], 'elapsed': round(now - started, 3)})
                last_progress = now
        report['stream_seconds'] = round(max(0, clock() - started), 3)
        if report['stream_seconds'] > 0:
            report['observed_fps'] = round(report['frames'] / report['stream_seconds'], 3)
        if report['frames'] == 0 and report['status'] == 'completed':
            report['status'] = 'read_failed'
        return report
    except Exception:
        # Exception text/native paths can contain personal details; omit them.
        report['status'] = 'worker_failed'
        return report
    finally:
        if cap is not None:
            cap.release()


class DemoCV:
    """Fictional frame metadata, without an image or camera dependency."""
    __version__ = 'simulated'
    CAP_PROP_FRAME_WIDTH, CAP_PROP_FRAME_HEIGHT, CAP_PROP_FPS, CAP_PROP_FOURCC = range(4)

    def __init__(self, scenario):
        self.scenario = scenario

    @staticmethod
    def VideoWriter_fourcc(*letters):
        return sum(ord(c) << (8 * i) for i, c in enumerate(letters))

    def VideoCapture(self, index, backend):
        return DemoCapture(self.scenario)


class DemoCapture:
    def __init__(self, scenario):
        self.scenario = scenario
        self.values = {0: 640., 1: 480., 2: 30., 3: DemoCV.VideoWriter_fourcc(*'MJPG')}
        self.frames = 0

    def isOpened(self):
        return self.scenario != 'open_failed'

    def getBackendName(self):
        return 'SIMULATED'

    def get(self, prop):
        return self.values[prop]

    def set(self, prop, value):
        self.values[prop] = value
        return True

    def read(self):
        time.sleep(1 / self.values[2])
        self.frames += 1
        if self.scenario == 'read_failed' and self.frames > 5:
            return False, None
        width, height = int(self.values[0]), int(self.values[1])
        return True, type('Frame', (), {'shape': (height, width, 3), 'size': width * height * 3})()

    def release(self):
        pass


def _worker(settings, scenario, connection):
    # Silence native diagnostic streams in the child. Only structured metadata
    # travels through the private pipe; no raw logs or frames are retained.
    try:
        with open(os.devnull, 'w') as null:
            os.dup2(null.fileno(), 1)
            os.dup2(null.fileno(), 2)
        if scenario:
            cv = DemoCV(scenario)
        else:
            try:
                import cv2 as cv
            except ImportError:
                connection.send({'stage': 'finished', 'result': {'status': 'dependency_missing'}})
                return
        result = capture(settings, cv, connection.send)
        connection.send({'stage': 'finished', 'result': result})
    except Exception:
        try:
            connection.send({'stage': 'finished', 'result': {'status': 'worker_failed'}})
        except (BrokenPipeError, OSError):
            pass
    finally:
        connection.close()


def stop_process(process):
    if process.is_alive():
        process.terminate()
        process.join(1)
    if process.is_alive():
        process.kill()
        process.join(1)
    return not process.is_alive()


def query_usb_events(usb_id, started, ended, runner=subprocess.run, system=None):
    system = platform.system() if system is None else system
    if not usb_id:
        return {'status': 'not_requested', 'matching_removals': None}
    if system != 'Windows':
        return {'status': 'unsupported', 'matching_removals': None}
    if not re.fullmatch(r'[0-9a-fA-F]{4}:[0-9a-fA-F]{4}', usb_id):
        raise ValueError('Invalid USB ID')
    for value in [started, ended]:
        if not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}\+00:00', value):
            raise ValueError('Invalid event-window timestamp')
    vid, pid = usb_id.upper().split(':')
    script = """$ErrorActionPreference='Stop'; try {
$events=@(Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Kernel-PnP/Device Management';Id=1010;StartTime=[DateTimeOffset]::Parse('__START_TIME__').LocalDateTime;EndTime=[DateTimeOffset]::Parse('__END_TIME__').LocalDateTime} | Where-Object {$_.Message -match 'VID___USB_VENDOR__&PID___USB_PRODUCT__'});
@{status='ok';matching_removals=$events.Count}|ConvertTo-Json -Compress
} catch { if ($_.FullyQualifiedErrorId -like 'NoMatchingEventsFound*') { @{status='ok';matching_removals=0}|ConvertTo-Json -Compress } else { @{status='unavailable';matching_removals=$null}|ConvertTo-Json -Compress } }"""
    script = script.replace('__START_TIME__', started).replace('__END_TIME__', ended).replace('__USB_VENDOR__', vid).replace('__USB_PRODUCT__', pid)
    try:
        result = runner(['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', script],
                        capture_output=True, timeout=5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode != 0 or len(result.stdout) > 4096:
            raise ValueError('Query did not return bounded metadata')
        value = json.loads(result.stdout.decode('utf-8-sig'))
        count = value.get('matching_removals')
        if value.get('status') == 'ok' and type(count) is int and 0 <= count <= 1000000:
            return {'status': 'ok', 'matching_removals': count}
    except (OSError, ValueError, subprocess.TimeoutExpired, UnicodeError):
        pass
    return {'status': 'unavailable', 'matching_removals': None}


def run_probe(settings, scenario=None, cancel=None, progress=None, target=_worker):
    settings.validate()
    if scenario not in (None, 'healthy', 'read_failed', 'open_failed'):
        raise ValueError('Unknown demo scenario')
    cancel = threading.Event() if cancel is None else cancel
    progress = (lambda value: None) if progress is None else progress
    report = base_report(settings, scenario is not None)
    if cancel.is_set():
        report.update(status='cancelled', ended_utc=utc_now(), worker_stopped=True)
        report['assessment'] = assessment(report)
        return report
    context = mp.get_context('spawn')
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=target, args=(settings, scenario, send), daemon=True)
    configured = False
    deadline = time.monotonic() + settings.open_timeout
    final = None
    try:
        process.start()
        send.close()
        while True:
            if cancel.is_set():
                report['status'] = 'cancelled'
                break
            now = time.monotonic()
            if now >= deadline:
                report['status'] = 'timed_out'
                report['timeout_stage'] = 'capture_or_cleanup' if configured else 'open_or_import'
                break
            if receive.poll(min(.05, deadline - now)):
                try:
                    value = receive.recv()
                except EOFError:
                    break
                if value.get('stage') == 'configured' and not configured:
                    configured = True
                    report['mode_observations'] = value['observations']
                    deadline = time.monotonic() + settings.seconds + 3
                if value.get('stage') == 'finished':
                    final = value['result']
                    break
                # All messages originate from this application's own child.
                progress(value)
                if value.get('stage') == 'streaming':
                    report.update(frames=value['frames'], stream_seconds=value['elapsed'])
            elif not process.is_alive():
                break
        if final is not None:
            report.update(final)
        process.join(.1)
    except KeyboardInterrupt:
        cancel.set()
        report['status'] = 'cancelled'
    except (OSError, RuntimeError):
        report['status'] = 'worker_failed'
    finally:
        # A stuck native open/read/release must not leave a camera worker behind.
        try:
            stopped = stop_process(process) if process.pid is not None else True
        finally:
            receive.close()
            send.close()
        report['worker_stopped'] = stopped
        if stopped and process.pid is not None:
            process.close()
        if not stopped:
            report['status'] = 'worker_failed'
        report['ended_utc'] = utc_now()
    if report['status'] not in STATUSES:
        report['status'] = 'worker_failed'
    if settings.usb_id and not scenario and not cancel.is_set():
        report['usb_events'] = query_usb_events(settings.usb_id, report['started_utc'], report['ended_utc'])
    report['assessment'] = assessment(report)
    return report


def assessment(report):
    if report['status'] != 'completed':
        return 'Test did not complete. This result does not identify the hardware or software cause.'
    if 'differs' in report.get('mode_comparisons', {}).values():
        return 'Frames arrived for the test window, but at least one requested mode value differs.'
    if report.get('usb_events', {}).get('matching_removals'):
        return 'Frames arrived, but removal events matched the optional USB filter. The filter is not tied to the camera index and does not prove a cause.'
    return 'Frames arrived for this test window. Long-term stability and other applications remain untested.'


def save_report(destination, report):
    """Create one new local JSON file; never replace an existing report."""
    destination = Path(destination)
    if destination.suffix.lower() != '.json':
        raise ValueError('Choose a new .json file.')
    text = json.dumps(report, indent=2, allow_nan=False) + '\n'
    if len(text.encode('utf-8')) > 65536:
        raise ValueError('Report exceeds the 64 KiB limit.')
    # No implicit directories, inherited logs, path expansion or overwrite.
    with destination.open('x', encoding='utf-8', newline='\n') as output:
        output.write(text)


def exit_code(report):
    if report['status'] == 'cancelled':
        return 130
    return 0 if (report['status'] == 'completed' and 'differs' not in report.get('mode_comparisons', {}).values()
                 and not report.get('usb_events', {}).get('matching_removals')) else 2
