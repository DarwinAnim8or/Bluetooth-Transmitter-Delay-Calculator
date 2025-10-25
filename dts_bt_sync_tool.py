#!/usr/bin/env python3
"""
DTS / Bluetooth Sync Helper
---------------------------
A tiny GUI to line up a visual flash with an audible beep. Adjust the delay (in frames)
until the beep and the on-screen flash feel simultaneous. Negative delays are allowed,
which means the first item you choose to delay (audio or visual) will happen *after*
the other event.

New: Optional 3-2-1 countdown mode before each test.
Hotkeys: ←/→ = ±0.25 frame, ↑/↓ = ±1 frame, Space = Test
"""

import sys
import time
import threading
import math
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except Exception as e:
    print("Tkinter is required to run the GUI.", e)
    sys.exit(1)

# --- Audio backends: Windows (winsound) or cross-platform (simpleaudio+numpy) ---
USE_WINSOUND = False
try:
    import winsound  # Only exists on Windows
    USE_WINSOUND = True
except Exception:
    USE_WINSOUND = False

# Try simpleaudio+numpy as a fallback if not on Windows
SIMPLEAUDIO_AVAILABLE = False
if not USE_WINSOUND:
    try:
        import numpy as np
        import simpleaudio as sa
        SIMPLEAUDIO_AVAILABLE = True
    except Exception:
        SIMPLEAUDIO_AVAILABLE = False


def play_beep(freq=1000, duration_ms=150, volume=0.2):
    """Play a short beep without blocking the UI."""
    if USE_WINSOUND:
        threading.Thread(target=lambda: winsound.Beep(int(freq), int(duration_ms)), daemon=True).start()
        return True
    elif SIMPLEAUDIO_AVAILABLE:
        sample_rate = 44100
        t = np.linspace(0, duration_ms/1000.0, int(sample_rate * (duration_ms/1000.0)), False)
        tone = float(volume) * np.sin(freq * 2 * np.pi * t)
        audio = (tone * 32767).astype(np.int16)
        try:
            sa.play_buffer(audio, 1, 2, sample_rate)
            return True
        except Exception:
            return False
    else:
        return False


class SyncApp:
    def __init__(self, root):
        self.root = root
        root.title("DTS / Bluetooth Sync Helper")
        root.minsize(600, 520)

        self.flash_bg_normal = "#111111"
        self.flash_bg_active = "#33cc33"

        # --- State variables ---
        self.fps_var = tk.DoubleVar(value=24.0)
        self.base_frames_var = tk.DoubleVar(value=20.25)
        self.rounded_frames_var = tk.IntVar(value=21)

        # Allow negative and positive delays
        self.audio_delay_frames_var = tk.DoubleVar(value=0.0)

        self.delay_target_var = tk.StringVar(value="Audio")  # "Audio" or "Visual"

        self.tone_freq_var = tk.IntVar(value=1000)
        self.tone_ms_var = tk.IntVar(value=150)
        self.flash_ms_var = tk.IntVar(value=150)

        self.repeat_var = tk.BooleanVar(value=False)
        self.repeat_interval_ms_var = tk.IntVar(value=1000)

        # Countdown options
        self.countdown_var = tk.BooleanVar(value=False)
        self.countdown_step_ms_var = tk.IntVar(value=700)  # time per number
        self.countdown_beeps_var = tk.BooleanVar(value=True)

        # --- Top controls ---
        top = ttk.Frame(root, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="FPS").grid(row=0, column=0, sticky="w")
        self.fps_entry = ttk.Combobox(top, textvariable=self.fps_var, width=6, values=[23.976, 24, 25, 29.97, 30, 48, 50, 59.94, 60])
        self.fps_entry.grid(row=0, column=1, padx=(4, 12), sticky="w")

        ttk.Label(top, text="Base (head→gate) frames").grid(row=0, column=2, sticky="w")
        ttk.Entry(top, textvariable=self.base_frames_var, width=8).grid(row=0, column=3, padx=(4, 12), sticky="w")

        ttk.Label(top, text="Rounded").grid(row=0, column=4, sticky="w")
        ttk.Entry(top, textvariable=self.rounded_frames_var, width=6).grid(row=0, column=5, padx=(4, 12), sticky="w")

        ttk.Label(top, text="Delay target").grid(row=1, column=0, sticky="w", pady=(8,0))
        self.delay_target_combo = ttk.Combobox(top, textvariable=self.delay_target_var, width=8, values=["Audio", "Visual"], state="readonly")
        self.delay_target_combo.grid(row=1, column=1, sticky="w", pady=(8,0), padx=(4,12))

        ttk.Label(top, text="Delay (frames)").grid(row=1, column=2, sticky="w", pady=(8,0))
        # New slider allows negative to positive
        self.delay_scale = ttk.Scale(top, from_=-80.0, to=80.0, orient="horizontal",
                                     variable=self.audio_delay_frames_var, command=self._update_labels)
        self.delay_scale.grid(row=1, column=3, columnspan=2, sticky="we", pady=(8,0))
        top.columnconfigure(4, weight=1)

        self.delay_label = ttk.Label(top, text="0.00 frames → 0 ms (Audio lags/Visual lags)")
        self.delay_label.grid(row=1, column=5, sticky="e", padx=(8,0))

        # Tone controls
        tone = ttk.Frame(root, padding=(10,6,10,10))
        tone.pack(fill=tk.X)
        ttk.Label(tone, text="Tone (Hz)").grid(row=0, column=0, sticky="w")
        ttk.Entry(tone, textvariable=self.tone_freq_var, width=8).grid(row=0, column=1, padx=(4,12))
        ttk.Label(tone, text="Tone length (ms)").grid(row=0, column=2, sticky="w")
        ttk.Entry(tone, textvariable=self.tone_ms_var, width=8).grid(row=0, column=3, padx=(4,12))
        ttk.Label(tone, text="Flash length (ms)").grid(row=0, column=4, sticky="w")
        ttk.Entry(tone, textvariable=self.flash_ms_var, width=8).grid(row=0, column=5, padx=(4,12))

        # Countdown controls
        cd = ttk.Frame(root, padding=(10,0,10,10))
        cd.pack(fill=tk.X)
        ttk.Checkbutton(cd, text="Countdown 3-2-1 before test", variable=self.countdown_var).grid(row=0, column=0, sticky="w")
        ttk.Label(cd, text="Step (ms)").grid(row=0, column=1, padx=(12,4), sticky="w")
        ttk.Entry(cd, textvariable=self.countdown_step_ms_var, width=8).grid(row=0, column=2, sticky="w")
        ttk.Checkbutton(cd, text="Beep on each count", variable=self.countdown_beeps_var).grid(row=0, column=3, padx=(12,0), sticky="w")

        # Repeat controls
        repeat = ttk.Frame(root, padding=(10,0,10,10))
        repeat.pack(fill=tk.X)
        ttk.Checkbutton(repeat, text="Repeat test", variable=self.repeat_var, command=self._toggle_repeat).grid(row=0, column=0, sticky="w")
        ttk.Label(repeat, text="Interval (ms)").grid(row=0, column=1, padx=(12,4), sticky="w")
        ttk.Entry(repeat, textvariable=self.repeat_interval_ms_var, width=8).grid(row=0, column=2, sticky="w")
        self.next_label = ttk.Label(repeat, text="")
        self.next_label.grid(row=0, column=3, padx=(12,0), sticky="w")

        # --- Big flash area ---
        self.flash = tk.Canvas(root, bg=self.flash_bg_normal, highlightthickness=0)
        self.flash.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.text_id = self.flash.create_text(10, 10, anchor="nw", fill="#dddddd", font=("Segoe UI", 12), text="")
        self.center_id = self.flash.create_text(0, 0, anchor="center", fill="#ffffff", font=("Segoe UI", 36, "bold"), text="Ready")
        self._center_text()

        # --- Bottom buttons ---
        bottom = ttk.Frame(root, padding=10)
        bottom.pack(fill=tk.X)
        self.test_btn = ttk.Button(bottom, text="Test (Space)", command=self.run_test)
        self.test_btn.pack(side=tk.LEFT)
        ttk.Button(bottom, text="Quit", command=root.destroy).pack(side=tk.RIGHT)

        # Key bindings
        root.bind("<space>", lambda e: self.run_test())
        root.bind("<Left>", lambda e: self.nudge_delay(-0.25))
        root.bind("<Right>", lambda e: self.nudge_delay(+0.25))
        root.bind("<Up>", lambda e: self.nudge_delay(+1.0))
        root.bind("<Down>", lambda e: self.nudge_delay(-1.0))

        self._update_labels()
        self._update_info_text()

        # Check audio backend status
        if not USE_WINSOUND and not SIMPLEAUDIO_AVAILABLE:
            messagebox.showwarning(
                "Audio backend not found",
                "No audio backend found.\n\nOn Windows this works out of the box.\n"
                "On macOS/Linux, please install:\n\n    pip install simpleaudio numpy\n"
                "Then run this app again."
            )

        self._repeat_timer = None
        self._running_repeat = False

        # Handle resizing for center text
        root.bind("<Configure>", lambda e: self._center_text())

    def _center_text(self):
        w = self.flash.winfo_width()
        h = self.flash.winfo_height()
        try:
            self.flash.coords(self.center_id, w/2, h/2)
        except Exception:
            pass

    def frames_to_ms(self, frames):
        fps = max(self.fps_var.get(), 1e-6)
        return 1000.0 * (frames / fps)

    def _update_labels(self, *_):
        frames = self.audio_delay_frames_var.get()
        ms = self.frames_to_ms(frames)
        lead_lag = "Audio delayed" if self.delay_target_var.get() == "Audio" else "Visual delayed"
        sign_text = " (target leads)" if frames < 0 else (" (target lags)" if frames > 0 else "")
        self.delay_label.config(text=f"{frames:+.2f} frames → {ms:+.0f} ms  [{lead_lag}{sign_text}]")
        self._update_info_text()

    def _update_info_text(self):
        fps = self.fps_var.get()
        base = self.base_frames_var.get()
        rounded = self.rounded_frames_var.get()
        adjust = self.audio_delay_frames_var.get()
        target = self.delay_target_var.get()

        if target == "Audio":
            suggested = base - adjust
            direction = "base − delay"
        else:
            suggested = base + adjust
            direction = "base + delay"

        latency_ms = self.frames_to_ms(abs(adjust))

        lines = [
            f"FPS: {fps:.3f}",
            f"Physical head→gate: {base:.2f} frames (rounded: {rounded})",
            f"Delay target: {target}   |   Set delay: {adjust:+.2f} frames ≈ {self.frames_to_ms(adjust):+.0f} ms",
            f"Suggest DTS setting ≈ {direction} = {suggested:.2f} frames",
            f"(Guide: |adjust| ≈ {latency_ms:.0f} ms at {fps:.3f} fps)",
            "",
            "Hotkeys: ←/→ = ±0.25 frame, ↑/↓ = ±1 frame, Space = Test"
        ]
        self.flash.itemconfig(self.text_id, text="\n".join(lines))

    def nudge_delay(self, delta_frames):
        self.audio_delay_frames_var.set(self.audio_delay_frames_var.get() + delta_frames)
        self._update_labels()

    def _flash_on(self):
        self.flash.configure(bg=self.flash_bg_active)
        self.flash.itemconfig(self.center_id, text="FLASH")
        self.root.after(self.flash_ms_var.get(), self._flash_off)

    def _flash_off(self):
        self.flash.configure(bg=self.flash_bg_normal)
        self.flash.itemconfig(self.center_id, text="")

    def _do_beep(self, freq=None, dur=None, vol=0.2):
        if freq is None:
            freq = max(50, int(self.tone_freq_var.get()))
        if dur is None:
            dur = max(20, int(self.tone_ms_var.get()))
        ok = play_beep(freq=freq, duration_ms=dur, volume=vol)
        if not ok:
            try:
                from tkinter import messagebox
                messagebox.showwarning("Audio backend not found",
                                        "Couldn't play audio.\n\nOn macOS/Linux, install:\n\n    pip install simpleaudio numpy")
            except Exception:
                pass

    def _perform_test_events(self):
        """Run the actual flash/beep pair based on delay target and sign."""
        frames = self.audio_delay_frames_var.get()
        delay_ms = int(round(self.frames_to_ms(abs(frames))))
        target = self.delay_target_var.get()

        if target == "Audio":
            if frames >= 0:
                # Flash first, then delay beep
                self._flash_on()
                threading.Timer(delay_ms/1000.0, self._do_beep).start() if delay_ms > 0 else self._do_beep()
            else:
                # Beep first, then delay flash
                self._do_beep()
                self.root.after(abs(delay_ms), self._flash_on)
        else:  # target == "Visual"
            if frames >= 0:
                # Beep first, then delay flash
                self._do_beep()
                self.root.after(delay_ms, self._flash_on) if delay_ms > 0 else self._flash_on()
            else:
                # Flash first, then delay beep
                self._flash_on()
                threading.Timer(delay_ms/1000.0, self._do_beep).start() if delay_ms > 0 else self._do_beep()

    def _run_with_countdown(self):
        """Show 3-2-1 countdown, optional soft beeps, then perform the test."""
        step = max(200, int(self.countdown_step_ms_var.get()))
        seq = ["3", "2", "1"]
        freqs = [600, 700, 800]  # gentle ascending cue

        def show_step(i):
            if i >= len(seq):
                # Clear and run the actual test
                self.flash.itemconfig(self.center_id, text="")
                self._perform_test_events()
                return
            self.flash.configure(bg=self.flash_bg_normal)
            self.flash.itemconfig(self.center_id, text=seq[i])
            if self.countdown_beeps_var.get():
                self._do_beep(freq=freqs[i], dur=90, vol=0.15)
            self.root.after(step, lambda: show_step(i+1))

        show_step(0)

    def run_test(self):
        if self.countdown_var.get():
            self._run_with_countdown()
        else:
            self._perform_test_events()

    def _toggle_repeat(self):
        if self.repeat_var.get():
            self._running_repeat = True
            self._schedule_next_repeat()
        else:
            self._running_repeat = False
            if hasattr(self, "_repeat_timer") and self._repeat_timer:
                self._repeat_timer.cancel()
                self._repeat_timer = None
            self.next_label.config(text="")

    def _schedule_next_repeat(self):
        if not getattr(self, "_running_repeat", False):
            return
        interval = max(200, int(self.repeat_interval_ms_var.get()))
        self.next_label.config(text=f"Next in {interval} ms")
        self._repeat_timer = threading.Timer(interval/1000.0, self._repeat_tick)
        self._repeat_timer.daemon = True
        self._repeat_timer.start()

    def _repeat_tick(self):
        if not getattr(self, "_running_repeat", False):
            return
        try:
            self.run_test()
        finally:
            self._schedule_next_repeat()


def main():
    root = tk.Tk()
    # Native theming when available
    try:
        style = ttk.Style()
        if sys.platform == "darwin":
            style.theme_use("aqua")
        elif sys.platform.startswith("win"):
            style.theme_use("winnative")
        else:
            style.theme_use("clam")
    except Exception:
        pass

    app = SyncApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
