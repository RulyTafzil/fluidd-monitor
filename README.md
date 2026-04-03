# fluidd-monitor

A lightweight terminal print monitor for [Fluidd](https://docs.fluidd.xyz/) / [Moonraker](https://moonraker.readthedocs.io/). Instead of keeping a browser tab open, get a live dashboard in your terminal with none of the browser overhead.

---

## What it shows

| Panel | Info |
|-------|------|
| Header | Printer state — `PRINTING`, `PAUSED`, `STANDBY`, `ERROR` |
| Progress | Filename, progress bar, elapsed / remaining / ETA |
| Temperatures | Hotend & bed with visual fill bars, fan speed |
| Motion | Current speed, speed factor override, XYZ position |

---

## Requirements

- Python 3.10 or newer
- A printer running Fluidd / Moonraker, reachable on your local network
---

## Installation

pipx install git+https://github.com/RulyTafzil/fluidd-monitor.git

OR 

```bash
git clone https://github.com/RulyTafzil/fluidd-monitor.git
cd fluidd-monitor

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python -m fluidd_monitor
```

---

## Usage

Pass your printer's IP address or hostname as an argument:

```bash
fluidd-monitor 192.168.1.100
fluidd-monitor myprinter.local
```

Or run it without arguments and you'll be prompted:

```bash
fluidd-monitor
# → Printer IP or hostname: _
```

Press **Ctrl+C** at any time to exit.

---

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `7125` | Moonraker port, if yours differs from the default |
| `--interval` | `3` | How often to poll and refresh, in seconds |

**Examples:**

```bash
# Non-default Moonraker port
fluidd-monitor 192.168.1.100 --port 7126

# Faster refresh
fluidd-monitor 192.168.1.100 --interval 2

# Slower refresh to reduce network traffic
fluidd-monitor myprinter.local --interval 10
```

---

## How the ETA is calculated

Remaining time is derived from elapsed print time divided by current progress — the same method Fluidd uses internally. The estimate becomes more accurate as the print progresses and is not available until a small amount of progress has been recorded.

---

## Updating

If you installed via pipx:

```bash
pipx upgrade fluidd-monitor
```

---

## Troubleshooting

**"No response from …"**  
Make sure your printer and computer are on the same network and that Moonraker is running. You can verify by opening `http://<your-printer-ip>:7125/server/info` in a browser — you should see a JSON response.

**`fluidd-monitor` command not found after pipx install**  
Run `pipx ensurepath`, then open a new terminal session.

**Wrong port**  
Some setups proxy Moonraker through a non-standard port. Check your Fluidd or router config if the default (`7125`) doesn't connect.

---

## License

MIT
