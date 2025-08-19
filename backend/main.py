from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
CONFIG_DIR = PROJECT_ROOT / "config"
STREAMS_FILE = CONFIG_DIR / "streams.yaml"
DEVICES_FILE = CONFIG_DIR / "devices.yaml"
WIFI_FILE = CONFIG_DIR / "wifi.yaml"
EXPORTS_DIR = PROJECT_ROOT / "exports"

app = FastAPI(title="RTSP Smart IDE API", version="0.1.0")

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StreamCreate(BaseModel):
    name: str
    url: str
    protocol: str = "rtsp"  # or rtsmp/rtmp in future
    enabled: bool = True
    username: Optional[str] = None
    password: Optional[str] = None
    meta: Dict[str, Any] = {}


class Stream(StreamCreate):
    id: str


class Device(BaseModel):
    id: str
    type: str = "camera"  # camera / rpi / other
    ip: str
    meta: Dict[str, Any] = {}


class WifiNetwork(BaseModel):
    ssid: str
    rssi: Optional[int] = None
    security: Optional[str] = None
    connected: bool = False


# --- YAML helpers -----------------------------------------------------------------

def _ensure_files():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    for f, default in [
        (STREAMS_FILE, []),
        (DEVICES_FILE, []),
        (WIFI_FILE, []),
    ]:
        if not f.exists():
            with f.open("w", encoding="utf-8") as fp:
                yaml.safe_dump(default, fp, allow_unicode=True, sort_keys=False)


def _read_yaml(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or default
    return data


def _write_yaml(path: Path, data):
    with path.open("w", encoding="utf-8") as fp:
        yaml.safe_dump(data, fp, allow_unicode=True, sort_keys=False)


@app.on_event("startup")
async def on_startup():
    _ensure_files()


# --- Basic endpoints ---------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "time": datetime.utcnow().isoformat() + "Z",
        "project_root": str(PROJECT_ROOT),
    }


# --- Streams CRUD -----------------------------------------------------------------

@app.get("/api/streams", response_model=List[Stream])
async def list_streams():
    items = _read_yaml(STREAMS_FILE, [])
    return items


@app.post("/api/streams", response_model=Stream, status_code=201)
async def create_stream(payload: StreamCreate):
    items: List[dict] = _read_yaml(STREAMS_FILE, [])
    new_id = f"s-{int(datetime.utcnow().timestamp()*1000)}"
    item = {"id": new_id, **payload.model_dump()}
    items.append(item)
    _write_yaml(STREAMS_FILE, items)
    return item


@app.put("/api/streams/{stream_id}", response_model=Stream)
async def update_stream(stream_id: str, payload: StreamCreate):
    items: List[dict] = _read_yaml(STREAMS_FILE, [])
    for i, s in enumerate(items):
        if s.get("id") == stream_id:
            items[i] = {"id": stream_id, **payload.model_dump()}
            _write_yaml(STREAMS_FILE, items)
            return items[i]
    raise HTTPException(status_code=404, detail="Stream not found")


@app.delete("/api/streams/{stream_id}", status_code=204)
async def delete_stream(stream_id: str):
    items: List[dict] = _read_yaml(STREAMS_FILE, [])
    new_items = [s for s in items if s.get("id") != stream_id]
    if len(new_items) == len(items):
        raise HTTPException(status_code=404, detail="Stream not found")
    _write_yaml(STREAMS_FILE, new_items)
    return


# --- Devices (skeleton) -----------------------------------------------------------

@app.get("/api/devices", response_model=List[Device])
async def list_devices():
    return _read_yaml(DEVICES_FILE, [])


# --- Monitoring -------------------------------------------------------------------

@app.get("/api/monitor/ping")
async def ping(host: str = Query(..., description="Host to ping, e.g. 8.8.8.8")):
    # Uses system ping for simplicity; may require permissions on some OS
    try:
        proc = subprocess.run(
            ["ping", "-c", "1", "-W", "1", host],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        ok = proc.returncode == 0
        rtt_ms = None
        if ok:
            # Try to parse 'time=XX ms'
            for line in proc.stdout.splitlines():
                if "time=" in line:
                    try:
                        rtt_ms = float(line.split("time=")[-1].split()[0])
                    except Exception:
                        rtt_ms = None
                    break
        return {"ok": ok, "rtt_ms": rtt_ms}
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="'ping' command not available")


@app.get("/api/monitor/http")
async def http_check(url: str = Query(..., description="URL to check")):
    timeout = httpx.Timeout(3.0, connect=3.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
            return {
                "ok": resp.status_code < 400,
                "status_code": resp.status_code,
                "elapsed_ms": resp.elapsed.total_seconds() * 1000.0,
            }
    except httpx.HTTPError as e:
        return {"ok": False, "error": str(e)}


# --- Export project ----------------------------------------------------------------

@app.post("/api/export")
async def export_project():
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    project_name = "rtsp-smart-ide"
    zip_name = f"{project_name}-{timestamp}.zip"
    zip_path = EXPORTS_DIR / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        include_paths = [
            (PROJECT_ROOT / "backend"),
            (PROJECT_ROOT / "config"),
            (PROJECT_ROOT / "frontend"),
            (PROJECT_ROOT / "scripts"),
            (PROJECT_ROOT / "README.md"),
            (PROJECT_ROOT / "LICENSE") if (PROJECT_ROOT / "LICENSE").exists() else None,
        ]
        for p in include_paths:
            if p is None:
                continue
            if p.is_file():
                zf.write(p, arcname=str(p.relative_to(PROJECT_ROOT)))
            elif p.is_dir():
                for root, _, files in os.walk(p):
                    for fn in files:
                        full = Path(root) / fn
                        zf.write(full, arcname=str(full.relative_to(PROJECT_ROOT)))

    return {"zip": str(zip_path), "size_bytes": zip_path.stat().st_size}


# --- Placeholder RTSP controls (not implemented) ----------------------------------

@app.post("/api/streams/{stream_id}/start")
async def start_stream(stream_id: str):
    # Placeholder hook for future ffmpeg/gstreamer launching
    items: List[dict] = _read_yaml(STREAMS_FILE, [])
    if not any(s.get("id") == stream_id for s in items):
        raise HTTPException(status_code=404, detail="Stream not found")
    return {"status": "not_implemented", "detail": "RTSP start coming soon"}


@app.post("/api/streams/{stream_id}/stop")
async def stop_stream(stream_id: str):
    items: List[dict] = _read_yaml(STREAMS_FILE, [])
    if not any(s.get("id") == stream_id for s in items):
        raise HTTPException(status_code=404, detail="Stream not found")
    return {"status": "not_implemented", "detail": "RTSP stop coming soon"}
