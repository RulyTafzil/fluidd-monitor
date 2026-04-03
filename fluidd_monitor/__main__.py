#!/usr/bin/env python3
"""
fluidd-monitor — terminal print monitor for Fluidd / Moonraker.

Usage:
    fluidd-monitor                        # prompts for host
    fluidd-monitor 192.168.1.100
    fluidd-monitor myprinter.local --port 7125 --interval 2
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ── constants ─────────────────────────────────────────────────────────────────

QUERY_OBJECTS = (
    "print_stats&display_status&virtual_sdcard"
    "&extruder&heater_bed&toolhead&fan&gcode_move"
)

PRINTER_STATES: dict[str, tuple[str, str]] = {
    "printing":  ("bold green",  "▶ PRINTING"),
    "paused":    ("bold yellow", "⏸ PAUSED"),
    "complete":  ("bold cyan",   "✔ COMPLETE"),
    "standby":   ("dim",         "● STANDBY"),
    "error":     ("bold red",    "✖ ERROR"),
    "cancelled": ("red",         "✖ CANCELLED"),
}

console = Console()

# ── API helpers ───────────────────────────────────────────────────────────────


def fetch_json(url: str, timeout: int = 5) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


def get_printer_state(host: str, port: int) -> dict | None:
    url = f"http://{host}:{port}/printer/objects/query?{QUERY_OBJECTS}"
    data = fetch_json(url)
    if data and "result" in data:
        return data["result"].get("status", {})
    return None


def get_server_info(host: str, port: int) -> dict | None:
    url = f"http://{host}:{port}/server/info"
    data = fetch_json(url)
    return data.get("result") if data else None


# ── formatting helpers ────────────────────────────────────────────────────────


def fmt_temp(current: float, target: float) -> str:
    bar_len = 10
    if target > 0:
        return f"{current:.1f}°/{target:.0f}°"
    return f"{current:.1f}° (off)"


def fmt_duration(seconds: float) -> str:
    if seconds < 0:
        return "--:--:--"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def eta_string(seconds_remaining: float) -> str:
    if seconds_remaining < 0:
        return "Unknown"
    return (datetime.now() + timedelta(seconds=seconds_remaining)).strftime("%I:%M %p")


def pct_bar(progress: float, width: int = 40) -> str:
    filled = int(progress * width)
    return "█" * filled + "░" * (width - filled)


# ── UI builders ───────────────────────────────────────────────────────────────


def build_header(host: str, state_str: str, state_color: str) -> Panel:
    title = Text()
    title.append("🖨  FLUIDD MONITOR  ", style="bold white")
    title.append(f"  {host}  ", style="dim white")
    title.append(f"  {state_str}", style=state_color)
    return Panel(title, style="white on #1a1a2e", padding=(0, 2))


def build_progress_panel(
    filename: str,
    progress: float,
    print_duration: float,
    total_duration: float | None,
) -> Panel:
    remaining = (total_duration - print_duration) if total_duration else -1
    pct = progress * 100

    lines = Text()
    lines.append("  File : ", style="dim")
    lines.append(f"{filename or 'No file loaded'}\n", style="bold cyan")
    lines.append(f"  {pct_bar(progress)}  ", style="green")
    lines.append(f"{pct:.1f}%\n\n", style="bold green")
    lines.append("  Elapsed  : ", style="dim")
    lines.append(fmt_duration(print_duration), style="white")
    lines.append("    Remaining : ", style="dim")
    lines.append(fmt_duration(remaining), style="yellow")
    lines.append("    ETA : ", style="dim")
    lines.append(eta_string(remaining) + "\n", style="bold yellow")

    return Panel(
        lines,
        title="[bold]Print Progress[/bold]",
        border_style="green",
        box=box.ROUNDED,
    )


def build_temps_panel(
    extruder_temp: float,
    extruder_target: float,
    bed_temp: float,
    bed_target: float,
    fan_speed: float,
) -> Panel:
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim", width=14)
    t.add_column()

    fan_bar = "█" * int(fan_speed * 10) + "░" * (10 - int(fan_speed * 10))
    t.add_row("🔥 Hotend", fmt_temp(extruder_temp, extruder_target))
    t.add_row("🛏  Bed",   fmt_temp(bed_temp, bed_target))
    t.add_row("💨 Fan",    f"{fan_speed * 100:.0f}%  [{fan_bar}]")

    return Panel(
        t,
        title="[bold]Temperatures[/bold]",
        border_style="red",
        box=box.ROUNDED,
    )


def build_motion_panel(
    speed: float,
    speed_factor: float,
    pos_x: float,
    pos_y: float,
    pos_z: float,
) -> Panel:
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim", width=14)
    t.add_column()

    t.add_row("⚡ Speed",    f"{speed * 60:.0f} mm/min  ({speed_factor * 100:.0f}% factor)")
    t.add_row("📍 Position", f"X:{pos_x:.2f}  Y:{pos_y:.2f}  Z:{pos_z:.3f} mm")

    return Panel(
        t,
        title="[bold]Motion[/bold]",
        border_style="blue",
        box=box.ROUNDED,
    )


def build_error_panel(msg: str) -> Panel:
    return Panel(
        Text(f"  ⚠  {msg}", style="bold red"),
        title="[red]Connection Error[/red]",
        border_style="red",
        box=box.ROUNDED,
    )


def build_layout(host: str, state: dict | None, error: str | None) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=1),
    )
    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right", ratio=2),
    )

    if error or state is None:
        layout["header"].update(build_header(host, "OFFLINE", "bold red"))
        layout["body"].update(build_error_panel(error or "Cannot reach printer"))
        layout["footer"].update(
            Text(
                f"  Last attempt: {datetime.now().strftime('%H:%M:%S')} — retrying…",
                style="dim",
            )
        )
        return layout

    # ── parse state objects ───────────────────────────────────────────────────
    ps  = state.get("print_stats", {})
    ds  = state.get("display_status", {})
    vsd = state.get("virtual_sdcard", {})
    ext = state.get("extruder", {})
    bed = state.get("heater_bed", {})
    gm  = state.get("gcode_move", {})
    fan = state.get("fan", {})

    printer_state = ps.get("state", "standby").lower()
    state_color, state_str = PRINTER_STATES.get(
        printer_state, ("white", printer_state.upper())
    )

    progress       = ds.get("progress") or vsd.get("progress", 0.0)
    print_duration = ps.get("print_duration", 0.0)
    filename       = ps.get("filename", "")

    total_duration: float | None = None
    if progress and progress > 0.01 and print_duration:
        total_duration = print_duration / progress

    ext_temp    = ext.get("temperature", 0.0)
    ext_target  = ext.get("target", 0.0)
    bed_temp    = bed.get("temperature", 0.0)
    bed_target  = bed.get("target", 0.0)
    fan_speed   = fan.get("speed", 0.0)

    speed        = gm.get("speed", 0.0)
    speed_factor = gm.get("speed_factor", 1.0)
    pos          = gm.get("gcode_position", [0.0, 0.0, 0.0, 0.0])

    # ── assemble layout ───────────────────────────────────────────────────────
    layout["header"].update(build_header(host, state_str, state_color))
    layout["right"].update(
        build_progress_panel(filename, progress, print_duration, total_duration)
    )
    layout["left"].split_column(
        Layout(build_temps_panel(ext_temp, ext_target, bed_temp, bed_target, fan_speed)),
        Layout(build_motion_panel(speed, speed_factor, pos[0], pos[1], pos[2])),
    )
    layout["footer"].update(
        Text(
            f"  Refreshed: {datetime.now().strftime('%H:%M:%S')}  |  Ctrl+C to quit",
            style="dim",
        )
    )

    return layout


# ── entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fluidd-monitor",
        description="Terminal print monitor for Fluidd / Moonraker.",
    )
    parser.add_argument(
        "host",
        nargs="?",
        default=None,
        help="Printer hostname or IP (e.g. 192.168.1.100 or myprinter.local)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7125,
        help="Moonraker port (default: 7125)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=3.0,
        help="Refresh interval in seconds (default: 3)",
    )
    args = parser.parse_args()

    host = args.host
    if not host:
        console.print("\n[bold cyan]Fluidd Terminal Monitor[/bold cyan]\n")
        host = console.input(
            "[dim]Printer IP or hostname[/dim] (e.g. 192.168.1.100): "
        ).strip()
        if not host:
            console.print("[red]No host provided. Exiting.[/red]")
            sys.exit(1)

    port     = args.port
    interval = max(0.5, args.interval)

    console.print(f"\n[dim]Connecting to [bold]{host}:{port}[/bold]…[/dim]")

    info = get_server_info(host, port)
    if info:
        kv = info.get("klippy_version", "?")
        sv = info.get("moonraker_version", "?")
        console.print(f"[green]✔ Connected[/green]  Klippy {kv}  ·  Moonraker {sv}\n")
        time.sleep(0.8)
    else:
        console.print(
            f"[yellow]⚠ Could not reach {host}:{port} — will keep retrying…[/yellow]\n"
        )
        time.sleep(1)

    try:
        with Live(console=console, screen=True, refresh_per_second=4) as live:
            while True:
                state = get_printer_state(host, port)
                error = None if state is not None else f"No response from {host}:{port}"
                live.update(build_layout(host, state, error))
                time.sleep(interval)
    except KeyboardInterrupt:
        pass

    console.print("\n[dim]Monitor closed.[/dim]\n")


if __name__ == "__main__":
    main()
