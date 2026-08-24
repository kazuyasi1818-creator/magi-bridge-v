#!/usr/bin/env python3
"""
KEIBA JV-Link realtime capture collector v1.

Runtime target:
- Windows
- JRA-VAN Data Lab JV-Link 5.0.0 (64-bit preferred) or matching-bitness installation
- Python 3.14 + pywin32 (current official Python path)

Plumbing/timing infrastructure only. Does not evaluate models or open VALIDATION/OOS.
"""
from __future__ import annotations
import argparse, hashlib, json, os, platform, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
BUFFER_SIZE = 150000
SUPPORTED_RECORD_IDS = {"WH", "WE", "AV", "JC", "TC", "CC"}

def now_pair():
    utc = datetime.now(timezone.utc)
    return utc.astimezone(JST), utc

def iso(x: datetime) -> str:
    return x.isoformat(timespec="milliseconds")

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def bfield(raw: bytes, pos1: int, n: int) -> bytes:
    return raw[pos1 - 1: pos1 - 1 + n]

def afield(raw: bytes, pos1: int, n: int) -> str:
    return bfield(raw, pos1, n).decode("ascii", errors="replace").strip()

def cpfield(raw: bytes, pos1: int, n: int) -> str:
    return bfield(raw, pos1, n).decode("cp932", errors="replace").strip()

def parse_announce(race_year: str, mmddhhmm: str) -> str | None:
    s = (mmddhhmm or "").strip()
    if len(race_year) != 4 or len(s) != 8 or not (race_year + s).isdigit():
        return None
    try:
        d = datetime(int(race_year), int(s[0:2]), int(s[2:4]), int(s[4:6]), int(s[6:8]), tzinfo=JST)
        return iso(d)
    except ValueError:
        return None

def common_key(raw: bytes):
    return {
        "year": afield(raw, 12, 4),
        "month_day": afield(raw, 16, 4),
        "venue_code": afield(raw, 20, 2),
        "meeting_no": afield(raw, 22, 2),
        "meeting_day": afield(raw, 24, 2),
    }

def race_id_from_parts(k: dict, race_no: str) -> str | None:
    vals = [k.get("year", ""), k.get("month_day", ""), k.get("venue_code", ""), k.get("meeting_no", ""), k.get("meeting_day", ""), race_no]
    if all(vals) and all(v.isdigit() for v in vals):
        return "".join(vals)
    return None

def parse_record(raw: bytes) -> dict:
    rid = raw[:2].decode("ascii", errors="replace")
    out = {"record_id": rid, "raw_length": len(raw)}
    if rid not in SUPPORTED_RECORD_IDS:
        out["supported_parser"] = False
        return out
    out["supported_parser"] = True
    k = common_key(raw)
    out.update(k)

    if rid == "WH":
        race_no = afield(raw, 26, 2)
        announce = afield(raw, 28, 8)
        out["race_no"] = race_no
        out["race_id"] = race_id_from_parts(k, race_no)
        out["source_announcement_time_jst"] = parse_announce(k["year"], announce)
        horses = []
        base = 36
        for idx in range(18):
            p = base + idx * 45
            horse_no = afield(raw, p, 2)
            if not horse_no or horse_no == "00":
                continue
            weight_s = afield(raw, p + 38, 3)
            sign = cpfield(raw, p + 41, 1)
            diff_s = afield(raw, p + 42, 3)
            weight = int(weight_s) if weight_s.isdigit() and weight_s not in {"000", "999"} else None
            diff = int(diff_s) if diff_s.isdigit() and diff_s not in {"000", "999"} else None
            if diff is not None and sign in {"-", "－"}:
                diff = -diff
            horses.append({
                "horse_no": horse_no,
                "horse_name": cpfield(raw, p + 2, 36),
                "body_weight_kg": weight,
                "body_weight_change_kg": diff,
                "raw_weight_code": weight_s,
                "raw_change_sign": sign,
                "raw_change_code": diff_s,
            })
        out["horses"] = horses
        return out

    if rid == "WE":
        announce = afield(raw, 26, 8)
        out["scope_key"] = "".join([k["year"], k["month_day"], k["venue_code"], k["meeting_no"], k["meeting_day"]])
        out["source_announcement_time_jst"] = parse_announce(k["year"], announce)
        out["change_type"] = afield(raw, 34, 1)
        out["weather_code"] = afield(raw, 35, 1)
        out["track_turf_code"] = afield(raw, 36, 1)
        out["track_dirt_code"] = afield(raw, 37, 1)
        return out

    race_no = afield(raw, 26, 2)
    out["race_no"] = race_no
    out["race_id"] = race_id_from_parts(k, race_no)
    announce = afield(raw, 28, 8)
    out["source_announcement_time_jst"] = parse_announce(k["year"], announce)

    if rid == "AV":
        out["horse_no"] = afield(raw, 36, 2)
        out["horse_name"] = cpfield(raw, 38, 36)
        out["abnormal_code"] = afield(raw, 3, 1)
        out["reason_code"] = afield(raw, 74, 3)
    elif rid == "JC":
        out["horse_no"] = afield(raw, 36, 2)
        out["horse_name"] = cpfield(raw, 38, 36)
        out["current_carried_weight_x10"] = afield(raw, 74, 3)
        out["current_jockey_code"] = afield(raw, 77, 5)
        out["current_jockey_name"] = cpfield(raw, 82, 34)
        out["previous_carried_weight_x10"] = afield(raw, 117, 3)
        out["previous_jockey_code"] = afield(raw, 120, 5)
        out["previous_jockey_name"] = cpfield(raw, 125, 34)
    elif rid == "TC":
        out["current_post_time_hhmm"] = afield(raw, 36, 4)
        out["previous_post_time_hhmm"] = afield(raw, 40, 4)
    elif rid == "CC":
        out["parser_scope"] = "header_and_announcement_only"
    return out

def read_realtime(jv, dataspec: str, key: str):
    rc = int(jv.JVRTOpen(dataspec, key))
    if rc != 0:
        return {"open_code": rc, "records": [], "read_error": None}
    records = []
    read_error = None
    try:
        buff = bytearray()
        fname = bytearray()
        while True:
            return_code, memview, fname = jv.JVGets(buff, BUFFER_SIZE, fname)
            return_code = int(return_code)
            if return_code > 0:
                records.append(memview.tobytes())
            elif return_code == 0:
                break
            elif return_code == -1:
                continue
            else:
                read_error = return_code
                break
    finally:
        try:
            jv.JVClose()
        except Exception:
            pass
    return {"open_code": rc, "records": records, "read_error": read_error}

def write_capture(root: Path, dataspec: str, key: str, result: dict):
    start_jst, start_utc = now_pair()
    capture_id = f"{start_utc.strftime('%Y%m%dT%H%M%S.%fZ')}_{dataspec}_{uuid.uuid4().hex[:8]}"
    raw_dir = root / "RAW_APPEND_ONLY" / start_jst.strftime("%Y%m%d")
    ledger_dir = root / "PROVENANCE_LEDGER"
    log_dir = root / "LOG"
    raw_dir.mkdir(parents=True, exist_ok=True)
    ledger_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    raw_path = raw_dir / f"{capture_id}.jvraw"
    raw_bytes = b"".join(result["records"])
    raw_path.write_bytes(raw_bytes)
    raw_sha = sha256_file(raw_path)
    finalized_jst, finalized_utc = now_pair()

    parsed = []
    offset = 0
    for seq, raw in enumerate(result["records"], start=1):
        item = parse_record(raw)
        item.update({
            "capture_id": capture_id,
            "dataspec": dataspec,
            "request_key": key,
            "record_sequence": seq,
            "raw_offset": offset,
            "raw_record_sha256": sha256_bytes(raw),
            "source_file": str(raw_path),
            "source_file_sha256": raw_sha,
            "source_capture_time_jst": iso(finalized_jst),
            "source_capture_time_utc": iso(finalized_utc),
        })
        offset += len(raw)
        parsed.append(item)

    meta = {
        "capture_id": capture_id,
        "dataspec": dataspec,
        "request_key": key,
        "started_at_jst": iso(start_jst),
        "started_at_utc": iso(start_utc),
        "source_capture_time_jst": iso(finalized_jst),
        "source_capture_time_utc": iso(finalized_utc),
        "raw_file": str(raw_path),
        "raw_file_sha256": raw_sha,
        "raw_bytes": len(raw_bytes),
        "record_count": len(result["records"]),
        "open_code": result["open_code"],
        "read_error": result["read_error"],
        "records": parsed,
    }
    meta_path = raw_path.with_suffix(".json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    with (ledger_dir / "capture_index.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "capture_id": capture_id,
            "dataspec": dataspec,
            "request_key": key,
            "source_capture_time_jst": iso(finalized_jst),
            "raw_file": str(raw_path),
            "raw_file_sha256": raw_sha,
            "record_count": len(result["records"]),
            "open_code": result["open_code"],
            "read_error": result["read_error"],
            "meta_file": str(meta_path),
        }, ensure_ascii=False) + "\n")
    return meta

def connect_jvlink(sid: str):
    if os.name != "nt":
        raise RuntimeError("JV-Link collector requires Windows.")
    try:
        import pythoncom
        import win32com.client
    except Exception as e:
        raise RuntimeError("pywin32 is required in the Python used for JV-Link.") from e
    pythoncom.CoInitialize()
    try:
        jv = win32com.client.Dispatch("JVDTLab.JVLink")
        rc = int(jv.JVInit(sid))
        if rc != 0:
            raise RuntimeError(f"JVInit failed: {rc}")
        return pythoncom, jv
    except Exception:
        pythoncom.CoUninitialize()
        raise

def one_cycle(jv, root: Path, date_key: str):
    results = []
    for dataspec in ("0B11", "0B14"):
        result = read_realtime(jv, dataspec, date_key)
        results.append(write_capture(root, dataspec, date_key, result))
    return results

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(JST).strftime("%Y%m%d"), help="YYYYMMDD request key")
    ap.add_argument("--root", default=r"C:\MAGI\KEIBA\REALTIME")
    ap.add_argument("--sid", default="UNKNOWN")
    ap.add_argument("--interval-seconds", type=int, default=60)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--self-test-parser", action="store_true")
    args = ap.parse_args()
    if args.self_test_parser:
        print(json.dumps({"status":"READY_FOR_SYNTHETIC_TESTS","python":sys.version,"platform":platform.platform(),"note":"COM/JV-Link not exercised by parser self-test."}, ensure_ascii=False, indent=2))
        return 0
    if len(args.date) != 8 or not args.date.isdigit():
        raise SystemExit("--date must be YYYYMMDD")
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    pythoncom = None
    jv = None
    try:
        pythoncom, jv = connect_jvlink(args.sid)
        while True:
            cycle_started = time.monotonic()
            metas = one_cycle(jv, root, args.date)
            print(json.dumps({"status":"CAPTURED","date":args.date,"captures":[{"capture_id":m["capture_id"],"dataspec":m["dataspec"],"records":m["record_count"],"open_code":m["open_code"],"read_error":m["read_error"],"sha256":m["raw_file_sha256"]} for m in metas]}, ensure_ascii=False))
            if args.once:
                break
            elapsed = time.monotonic() - cycle_started
            time.sleep(max(1.0, args.interval_seconds - elapsed))
    finally:
        if jv is not None:
            try: jv.JVClose()
            except Exception: pass
        if pythoncom is not None:
            try: pythoncom.CoUninitialize()
            except Exception: pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
