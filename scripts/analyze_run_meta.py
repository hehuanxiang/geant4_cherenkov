#!/usr/bin/env python3
"""
Quick helper to inspect *.run_meta.json produced by RunAction.

Usage:
  python3 scripts/analyze_run_meta.py                # auto-detect latest run_meta in output/
  python3 scripts/analyze_run_meta.py path/to/meta.json
"""

import json
import sys
from pathlib import Path
from datetime import datetime


def find_latest_meta(project_root: Path) -> Path | None:
  """Find the most recently modified *.run_meta.json under '<project_root>/output/'."""
  output_dir = project_root / "output"
  if not output_dir.is_dir():
    return None

  metas = list(output_dir.glob("*.run_meta.json"))
  if not metas:
    return None

  metas.sort(key=lambda p: p.stat().st_mtime, reverse=True)
  return metas[0]


def format_seconds(s: int) -> str:
  h = s // 3600
  m = (s % 3600) // 60
  sec = s % 60
  return f"{h:02d} h {m:02d} m {sec:02d} s"


def main(argv: list[str]) -> int:
  script_dir = Path(__file__).resolve().parent
  project_root = script_dir.parent

  if len(argv) >= 2:
    meta_path = Path(argv[1])
  else:
    meta_path = find_latest_meta(project_root)
    if meta_path is None:
      print("No *.run_meta.json found under output/. Run a simulation first.")
      return 1

  if not meta_path.is_file():
    print(f"Meta file not found: {meta_path}")
    return 1

  with meta_path.open("r", encoding="utf-8") as f:
    meta = json.load(f)

  print(f"=== Run Metadata ===")
  print(f"File:        {meta_path}")
  ts = meta.get("timestamp", "")
  if ts:
    try:
      dt = datetime.fromisoformat(ts)
      print(f"Timestamp:   {dt} (local)")
    except Exception:
      print(f"Timestamp:   {ts}")
  else:
    print("Timestamp:   (not set)")

  print()
  print(f"Output base: {meta.get('output_base_path', '')}")
  print(f"Format:      {meta.get('output_format', '')}")
  print(f"PHSP file:   {meta.get('phsp_file_path', '')}")

  print()
  cfg_thr = meta.get("num_threads_config", 0)
  eff_thr = meta.get("num_threads_effective", 0)
  print(f"Threads (config / effective): {cfg_thr} / {eff_thr}")

  events = int(meta.get("events", 0))
  photons = int(meta.get("total_photons", 0))
  print(f"Events:      {events}")
  print(f"Photons:     {photons}")
  if events > 0:
    print(f"Photons / event: {photons / events:.1f}")

  wall = int(meta.get("wall_time_seconds", 0))
  cpu = int(meta.get("cpu_time_seconds", 0))
  print()
  print(f"Wall time:   {format_seconds(wall)}  ({wall} s)")
  print(f"CPU time:    {format_seconds(cpu)}  ({cpu} s)")
  if wall > 0:
    print(f"Speedup (CPU/Wall): {cpu / wall:.1f}x")
    print(f"Events / second:    {events / wall:.1f}")

  return 0


if __name__ == "__main__":
  raise SystemExit(main(sys.argv))

