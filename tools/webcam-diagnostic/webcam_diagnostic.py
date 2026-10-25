#!/usr/bin/env python3
"""Outlands Webcam Diagnostic: desktop app and explicit camera-test CLI. MIT."""
from __future__ import annotations

import argparse
import json
import multiprocessing
import platform
import queue
import sys
import threading

from diagnostic_core import PLATFORMS, Settings, base_report, exit_code, run_probe, save_report


class DiagnosticApp:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk
        from tkinter.scrolledtext import ScrolledText
        self.root = root
        self.root.title('Outlands Webcam Diagnostic')
        self.root.geometry('970x760')
        self.root.minsize(820, 680)
        self.messages = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.closing = False
        self.report = None
        self.reports = {}
        self.sequence = 0
        self.index = tk.StringVar(value='0')
        self.backend = tk.StringVar(value='ANY')
        self.seconds = tk.StringVar(value='10')
        self.open_timeout = tk.StringVar(value='10')
        self.request_mode = tk.BooleanVar(value=False)
        self.width = tk.StringVar(value='640')
        self.height = tk.StringVar(value='480')
        self.fps = tk.StringVar(value='30')
        self.fourcc = tk.StringVar(value='MJPG')
        self.usb_id = tk.StringVar(value='')
        self.demo = tk.StringVar(value='healthy')
        self.status = tk.StringVar(value='Ready. No camera has been opened.')
        self.fields = []
        outer = ttk.Frame(root, padding=16)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='Webcam Diagnostic', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='Measure capture behavior. Compare backends and requested modes. Save a local report.').pack(anchor='w', pady=(2, 8))
        ttk.Label(outer, text='Frames are read and discarded; no images, audio or raw device logs are saved.').pack(anchor='w', pady=(0, 12))
        form = ttk.LabelFrame(outer, text='Camera test settings', padding=10)
        form.pack(fill='x')

        def entry(label, variable, row, column, width=10, values=None):
            ttk.Label(form, text=label).grid(row=row, column=column, sticky='w', padx=(0, 8), pady=4)
            widget = (ttk.Combobox(form, textvariable=variable, values=values, state='readonly', width=width)
                      if values else ttk.Entry(form, textvariable=variable, width=width))
            widget.grid(row=row, column=column + 1, sticky='w', padx=(0, 20), pady=4)
            self.fields.append((widget, 'readonly' if values else 'normal'))
            return widget

        entry('Camera index', self.index, 0, 0)
        entry('Backend', self.backend, 0, 2, 16, sorted(PLATFORMS.get(platform.system(), {'ANY'})))
        entry('Duration (s)', self.seconds, 1, 0)
        entry('Open timeout (s)', self.open_timeout, 1, 2)
        self.mode_check = ttk.Checkbutton(form, text='Request a mode (unchecked keeps camera defaults)', variable=self.request_mode, command=self.mode_state)
        self.mode_check.grid(row=2, column=0, columnspan=4, sticky='w', pady=(8, 4))
        self.mode_fields = [entry('Width', self.width, 3, 0), entry('Height', self.height, 3, 2),
                            entry('FPS', self.fps, 4, 0), entry('FOURCC', self.fourcc, 4, 2)]
        self.usb_field = entry('USB VID:PID (optional)', self.usb_id, 5, 0, 16)
        ttk.Label(form, text='Windows removal-event count only; leave blank to skip.').grid(row=5, column=2, columnspan=2, sticky='w')
        actions = ttk.Frame(outer)
        actions.pack(fill='x', pady=12)
        self.start_button = ttk.Button(actions, text='Start camera test', command=self.start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(actions, text='Stop', command=self.stop, state='disabled')
        self.stop_button.pack(side='left', padx=8)
        self.demo_choice = ttk.Combobox(actions, textvariable=self.demo, values=['healthy', 'read_failed', 'open_failed'], state='readonly', width=14)
        self.demo_choice.pack(side='left', padx=(12, 4))
        self.demo_button = ttk.Button(actions, text='Run demo (no camera)', command=lambda: self.start(True))
        self.demo_button.pack(side='left')
        self.save_button = ttk.Button(actions, text='Save selected report', command=self.save, state='disabled')
        self.save_button.pack(side='right')
        ttk.Label(outer, textvariable=self.status, wraplength=890).pack(anchor='w', pady=(0, 8))
        self.history = ttk.Treeview(outer, columns=('kind', 'backend', 'status', 'frames', 'fps'), show='headings', height=5)
        for name, width in [('kind', 95), ('backend', 130), ('status', 150), ('frames', 90), ('fps', 100)]:
            self.history.heading(name, text={'kind': 'Test', 'backend': 'Actual backend', 'status': 'Result', 'frames': 'Frames', 'fps': 'Observed FPS'}[name])
            self.history.column(name, width=width, stretch=True)
        self.history.pack(fill='x')
        self.history.bind('<<TreeviewSelect>>', self.select_report)
        self.text = ScrolledText(outer, height=10, wrap='word', font=('Consolas', 10))
        self.text.pack(fill='both', expand=True, pady=(8, 0))
        self.text.insert('1.0', 'Choose Start camera test, or try the camera-free demo.\n\nA completed test covers only the measured window. It does not prove long-term stability or diagnose a cable, driver or camera fault.')
        self.text.configure(state='disabled')
        self.mode_state()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(75, self.pump)

    def mode_state(self):
        for widget in self.mode_fields:
            widget.configure(state='normal' if self.request_mode.get() and not self.busy else 'disabled')
        self.usb_field.configure(state='normal' if platform.system() == 'Windows' and not self.busy else 'disabled')

    def settings(self):
        requested = self.request_mode.get()
        return Settings(index=int(self.index.get()), backend=self.backend.get(), seconds=float(self.seconds.get()),
                        open_timeout=float(self.open_timeout.get()), width=int(self.width.get()) if requested else None,
                        height=int(self.height.get()) if requested else None, fps=float(self.fps.get()) if requested else None,
                        fourcc=self.fourcc.get().upper() if requested else None,
                        usb_id=self.usb_id.get().strip() or None).validate()

    def start(self, demo=False):
        from tkinter import messagebox
        if self.busy:
            return
        try:
            settings = Settings(seconds=1) if demo else self.settings()
            scenario = self.demo.get() if demo else None
        except ValueError as exc:
            messagebox.showerror('Check test settings', str(exc), parent=self.root)
            return
        self.busy = True
        self.cancel = threading.Event()
        for widget, _ in self.fields:
            widget.configure(state='disabled')
        for widget in [self.start_button, self.demo_button, self.demo_choice, self.mode_check]:
            widget.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.save_button.configure(state='disabled')
        self.status.set('SIMULATED test starting; no camera access.' if demo else 'Opening the selected camera in an isolated worker…')
        def work():
            try:
                report = run_probe(settings, scenario, self.cancel, lambda value: self.messages.put(('progress', value)))
                self.messages.put(('result', report))
            except Exception:
                report = base_report(settings, demo)
                report['assessment'] = 'The supervisor could not complete the test. No raw exception details were retained.'
                self.messages.put(('result', report))
        threading.Thread(target=work, daemon=True).start()

    def stop(self):
        self.cancel.set()
        self.stop_button.configure(state='disabled')
        self.status.set('Stopping the worker… an in-progress optional event query may take up to 5 seconds.')

    def add_report(self, report):
        self.sequence += 1
        key = str(self.sequence)
        self.reports[key] = report
        if len(self.reports) > 20:
            old = next(iter(self.reports))
            del self.reports[old]
            self.history.delete(old)
        self.history.insert('', 'end', iid=key, values=('Demo' if report['simulated'] else 'Camera', report.get('actual_backend', '—'),
                            report['status'], report['frames'], report.get('observed_fps') or '—'))
        self.history.selection_set(key)
        self.history.see(key)
        self.select_report()

    def select_report(self, event=None):
        selection = self.history.selection()
        if not selection:
            return
        self.report = self.reports[selection[0]]
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', self.report.get('assessment', '') + '\n\n' + json.dumps(self.report, indent=2, allow_nan=False))
        self.text.configure(state='disabled')
        self.save_button.configure(state='disabled' if self.busy else 'normal')

    def pump(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == 'progress' and not self.cancel.is_set():
                    self.status.set(f"{value['stage'].capitalize()} — {value.get('frames', 0)} frames received. No frames saved.")
                elif kind == 'result':
                    self.busy = False
                    for widget, state in self.fields:
                        widget.configure(state=state)
                    for widget in [self.start_button, self.demo_button, self.mode_check]:
                        widget.configure(state='normal')
                    self.demo_choice.configure(state='readonly')
                    self.stop_button.configure(state='disabled')
                    self.mode_state()
                    self.add_report(value)
                    self.status.set(('SIMULATED — ' if value['simulated'] else '') + value.get('assessment', value['status']))
        except queue.Empty:
            pass
        if self.closing and not self.busy:
            self.root.destroy()
        else:
            self.root.after(75, self.pump)

    def save(self):
        from tkinter import filedialog, messagebox
        if self.report is None or self.busy:
            return
        filename = filedialog.asksaveasfilename(parent=self.root, title='Create a new diagnostic report',
                                               defaultextension='.json', initialfile='webcam-report.json',
                                               filetypes=[('JSON report', '*.json')])
        if filename:
            try:
                save_report(filename, self.report)
                self.status.set('Report saved locally. Review it before posting it publicly.')
            except (OSError, ValueError):
                messagebox.showerror('Report was not saved', 'Choose a writable directory and a new .json filename. Existing files are never replaced.', parent=self.root)

    def close(self):
        if self.busy:
            self.closing = True
            self.stop()
        else:
            self.root.destroy()


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    action = result.add_mutually_exclusive_group()
    action.add_argument('--run', action='store_true', help='Explicitly open the selected camera; print a metadata report')
    action.add_argument('--demo', choices=['healthy', 'read_failed', 'open_failed'], help='Run a fictional test with no camera or OpenCV')
    result.add_argument('--index', type=int, default=0, help='Local camera index, 0–63')
    result.add_argument('--backend', choices=['ANY', 'DSHOW', 'MSMF', 'V4L2', 'AVFOUNDATION'], default='ANY')
    result.add_argument('--seconds', type=float, default=10, help='Capture duration, 1–1800 seconds')
    result.add_argument('--open-timeout', type=float, default=10, help='Worker startup/open timeout, 1–60 seconds')
    result.add_argument('--width', type=int)
    result.add_argument('--height', type=int)
    result.add_argument('--fps', type=float)
    result.add_argument('--fourcc', help='Optional mode request, for example MJPG')
    result.add_argument('--usb-id', help='Optional Windows event-count filter VID:PID; instance IDs are not exported')
    result.add_argument('--output', help='Also create one new .json report; no overwrite')
    return result


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    arguments = parser()
    args = arguments.parse_args(argv)
    if not args.run and not args.demo:
        if any(value is not None for value in [args.output, args.width, args.height, args.fps, args.fourcc, args.usb_id]) or argv:
            arguments.error('Use --run or --demo with command-line test settings, or no arguments to open the desktop app.')
        import tkinter as tk
        root = tk.Tk()
        DiagnosticApp(root)
        root.mainloop()
        return 0
    settings = Settings(args.index, args.backend, args.seconds, args.open_timeout,
                        args.width, args.height, args.fps, args.fourcc, args.usb_id)
    try:
        settings.validate()
        if args.demo and args.usb_id:
            raise ValueError('Demo mode does not query Windows device events.')
        # Refuse an existing destination before opening a camera, then use exclusive
        # creation after completion as well (another process could create it).
        if args.output:
            from pathlib import Path
            destination = Path(args.output)
            if destination.suffix.lower() != '.json' or destination.exists() or destination.is_symlink() or not destination.parent.is_dir():
                raise ValueError('Output must be a new .json file in an existing directory.')
        report = run_probe(settings, args.demo)
        if args.output:
            save_report(args.output, report)
        print(json.dumps(report, indent=2, allow_nan=False))
        return exit_code(report)
    except (OSError, ValueError) as exc:
        arguments.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    multiprocessing.freeze_support()
    raise SystemExit(main())
