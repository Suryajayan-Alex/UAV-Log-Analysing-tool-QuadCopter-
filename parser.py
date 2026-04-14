from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable
from datetime import datetime, timezone

import pandas as pd

_MODE_MSG_PATTERN = re.compile(r"\bmode\b(?:\s+changed\s+to|\s+to|\s*[:=])?\s*([A-Za-z0-9_\- ]+)", re.IGNORECASE)
_MODE_NUMBER_TO_NAME = {
    0: "STABILIZE",
    1: "ACRO",
    2: "ALT HOLD",
    3: "AUTO",
    4: "GUIDED",
    5: "LOITER",
    6: "RTL",
    7: "CIRCLE",
    9: "LAND",
    16: "POS HOLD",
    17: "BRAKE",
    21: "SMART RTL",
}

_ARM_MSG_PATTERN = re.compile(r"\b(arming motors|armed)\b", re.IGNORECASE)
_DISARM_MSG_PATTERN = re.compile(r"\b(disarming motors|disarmed)\b", re.IGNORECASE)


def _relative_time(df: pd.DataFrame) -> pd.DataFrame:
    """Add relative time column `t` in seconds from TimeUS/TimeMS if available."""
    if df.empty:
        return df

    if "TimeUS" in df.columns:
        time_col = pd.to_numeric(df["TimeUS"], errors="coerce")
        if time_col.notna().any():
            t0 = float(time_col.dropna().min())
            df["t"] = (time_col - t0) / 1_000_000.0
            return df

    if "TimeMS" in df.columns:
        time_col = pd.to_numeric(df["TimeMS"], errors="coerce")
        if time_col.notna().any():
            t0 = float(time_col.dropna().min())
            df["t"] = (time_col - t0) / 1_000.0
            return df

    return df


def _extract_by_fields(messages: Iterable[object], msg_type: str, fields: dict[str, str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for msg in messages:
        if msg.get_type() != msg_type:
            continue
        row = {out: getattr(msg, attr, None) for out, attr in fields.items()}
        rows.append(row)
    return _relative_time(pd.DataFrame(rows))


def _extract_generic(messages: Iterable[object], msg_type: str) -> pd.DataFrame:
    rows = [msg.to_dict() for msg in messages if msg.get_type() == msg_type]
    return _relative_time(pd.DataFrame(rows))


def _normalize_mode_name(raw: object) -> str | None:
    if raw is None:
        return None

    text = str(raw).strip()
    if not text:
        return None

    text = text.replace("Mode(", "").replace(")", "")
    text = text.split(",", maxsplit=1)[0].strip()
    if not text:
        return None

    number_match = re.fullmatch(r"(?:MODE[\s:_\-]*)?(\d+)", text, flags=re.IGNORECASE)
    if number_match:
        mode_number = int(number_match.group(1))
        return _MODE_NUMBER_TO_NAME.get(mode_number, f"MODE {mode_number}")

    normalized = re.sub(r"[_\-]+", " ", text)
    normalized = re.sub(r"\s+", " ", normalized).strip().upper()

    alias_map = {
        "ALTHOLD": "ALT HOLD",
        "POSHOLD": "POS HOLD",
        "SMARTRTL": "SMART RTL",
    }
    return alias_map.get(normalized, normalized)


def _extract_mode_messages(messages: list[object]) -> pd.DataFrame:
    mode_rows: list[dict[str, object]] = []

    # Preferred source: MODE messages in dataflash logs.
    for msg in messages:
        if msg.get_type() != "MODE":
            continue

        mode_value = getattr(msg, "Mode", None)
        if mode_value is None:
            mode_value = getattr(msg, "ModeNum", None)

        mode_name = _normalize_mode_name(mode_value)
        if mode_name is None:
            continue

        mode_rows.append(
            {
                "TimeUS": getattr(msg, "TimeUS", None),
                "TimeMS": getattr(msg, "TimeMS", None),
                "Mode": mode_name,
            }
        )

    # Fallback source: parse mode change text in MSG records when MODE is absent.
    if not mode_rows:
        for msg in messages:
            if msg.get_type() != "MSG":
                continue

            text = getattr(msg, "Message", "") or getattr(msg, "Msg", "")
            if not isinstance(text, str):
                text = str(text)

            match = _MODE_MSG_PATTERN.search(text)
            if not match:
                continue

            mode_name = _normalize_mode_name(match.group(1))
            if mode_name is None:
                continue

            mode_rows.append(
                {
                    "TimeUS": getattr(msg, "TimeUS", None),
                    "TimeMS": getattr(msg, "TimeMS", None),
                    "Mode": mode_name,
                }
            )

    df_mode = _relative_time(pd.DataFrame(mode_rows))
    if df_mode.empty or "Mode" not in df_mode.columns or "t" not in df_mode.columns:
        return pd.DataFrame(columns=["t", "Mode"])

    df_mode["t"] = pd.to_numeric(df_mode["t"], errors="coerce")
    df_mode["Mode"] = df_mode["Mode"].astype(str).str.strip().str.upper()

    df_mode = (
        df_mode.dropna(subset=["t", "Mode"])
        .sort_values("t")
        .reset_index(drop=True)
    )

    if df_mode.empty:
        return pd.DataFrame(columns=["t", "Mode"])

    # Keep only transitions so consecutive repeated mode rows do not create tiny duplicate segments.
    df_mode = df_mode[df_mode["Mode"].ne(df_mode["Mode"].shift())].reset_index(drop=True)

    return df_mode[["t", "Mode"]]


def _normalize_armed_state(raw: object) -> bool | None:
    if raw is None:
        return None

    if isinstance(raw, bool):
        return raw

    if isinstance(raw, (int, float)):
        if float(raw) in {0.0, 1.0}:
            return bool(int(raw))

    text = str(raw).strip().lower()
    if not text:
        return None

    if text in {"1", "true", "armed", "arm", "yes", "on"}:
        return True
    if text in {"0", "false", "disarmed", "disarm", "no", "off"}:
        return False

    if "disarm" in text:
        return False
    if "arm" in text:
        return True

    return None


def _extract_armed_messages(messages: list[object]) -> pd.DataFrame:
    arm_rows: list[dict[str, object]] = []

    # Preferred source: ARM messages.
    for msg in messages:
        if msg.get_type() != "ARM":
            continue

        armed_state = None
        for field in ("ArmState", "Armed", "Arm", "State", "Status"):
            armed_state = _normalize_armed_state(getattr(msg, field, None))
            if armed_state is not None:
                break

        if armed_state is None:
            continue

        arm_rows.append(
            {
                "TimeUS": getattr(msg, "TimeUS", None),
                "TimeMS": getattr(msg, "TimeMS", None),
                "armed": armed_state,
            }
        )

    # Fallback: detect arming/disarming transitions from MSG records.
    if not arm_rows:
        for msg in messages:
            if msg.get_type() != "MSG":
                continue

            text = getattr(msg, "Message", "") or getattr(msg, "Msg", "")
            if not isinstance(text, str):
                text = str(text)

            lowered = text.strip().lower()
            if not lowered:
                continue

            armed_state = None
            if _DISARM_MSG_PATTERN.search(lowered):
                armed_state = False
            elif _ARM_MSG_PATTERN.search(lowered):
                armed_state = True

            if armed_state is None:
                continue

            arm_rows.append(
                {
                    "TimeUS": getattr(msg, "TimeUS", None),
                    "TimeMS": getattr(msg, "TimeMS", None),
                    "armed": armed_state,
                }
            )

    df_arm = _relative_time(pd.DataFrame(arm_rows))
    if df_arm.empty or "armed" not in df_arm.columns or "t" not in df_arm.columns:
        return pd.DataFrame(columns=["t", "armed"])

    df_arm["t"] = pd.to_numeric(df_arm["t"], errors="coerce")
    df_arm["armed"] = df_arm["armed"].map(_normalize_armed_state)

    df_arm = (
        df_arm.dropna(subset=["t", "armed"])
        .sort_values("t")
        .reset_index(drop=True)
    )

    if df_arm.empty:
        return pd.DataFrame(columns=["t", "armed"])

    df_arm = df_arm[df_arm["armed"].ne(df_arm["armed"].shift())].reset_index(drop=True)
    return df_arm[["t", "armed"]]


def read_log_messages(path: str | Path) -> list[object]:
    """Read all MAVLink/DataFlash messages from a .bin/.log file."""
    try:
        from pymavlink import mavutil
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Missing required dependency 'pymavlink'. Run install_packages.py and retry."
        ) from exc

    connection = mavutil.mavlink_connection(str(path), notimestamps=True)
    messages: list[object] = []
    
    needed_types = [
        "ATT", "GPS", "BARO", "PSC", "PSCE", "PSCN", "BAT", "RCIN", "RCOU", "VIBE",
        "NKF1", "NKF2", "NKF3", "NKF4", "XKF1", "XKF2", "XKF3", "XKF4", "NKF9",
        "PRX", "OA", "MAG", "AHR2", "MODE", "ARM", "MSG", "ERR", "EV", "GPA", "GMT", "CTUN"
    ]

    while True:
        msg = connection.recv_match(type=needed_types)
        if msg is None:
            break
        messages.append(msg)
    try:
        connection.close()
    except Exception:
        pass
    return messages


def extract_frames(messages: list[object]) -> dict[str, pd.DataFrame]:
    """Extract all dataframes needed for the analyzer plots."""
    grouped_msgs: dict[str, list[object]] = {}
    for msg in messages:
        t = msg.get_type()
        if t not in grouped_msgs:
            grouped_msgs[t] = []
        grouped_msgs[t].append(msg)

    df_att = _extract_by_fields(
        grouped_msgs.get("ATT", []),
        "ATT",
        {
            "TimeUS": "TimeUS",
            "Roll": "Roll",
            "Pitch": "Pitch",
            "Yaw": "Yaw",
            "DesRoll": "DesRoll",
            "DesPitch": "DesPitch",
            "DesYaw": "DesYaw",
        },
    )
    if not df_att.empty:
        if "RollDes" in df_att.columns and ("DesRoll" not in df_att or df_att["DesRoll"].isna().all()):
            df_att["DesRoll"] = df_att["RollDes"]
        if "PitchDes" in df_att.columns and ("DesPitch" not in df_att or df_att["DesPitch"].isna().all()):
            df_att["DesPitch"] = df_att["PitchDes"]
        if "YawDes" in df_att.columns and ("DesYaw" not in df_att or df_att["DesYaw"].isna().all()):
            df_att["DesYaw"] = df_att["YawDes"]

    gps_rows: list[dict[str, object]] = []
    for msg in grouped_msgs.get("GPS", []):
        instance = getattr(msg, "I", getattr(msg, "Instance", getattr(msg, "Inst", 0)))
        gps_rows.append(
            {
                "TimeUS": getattr(msg, "TimeUS", None),
                "Lat": getattr(msg, "Lat", None),
                "Lng": getattr(msg, "Lng", None),
                "Alt": getattr(msg, "Alt", None),
                "Spd": getattr(msg, "Spd", None),
                "NSats": getattr(msg, "NSats", None),
                "HDop": getattr(msg, "HDop", None),
                "GWk": getattr(msg, "GWk", None),
                "GMS": getattr(msg, "GMS", None),
                "GCrs": getattr(msg, "GCrs", None),
                "I": 0 if instance is None else instance,
            }
        )
    df_gps = _relative_time(pd.DataFrame(gps_rows))

    df_baro = _extract_by_fields(grouped_msgs.get("BARO", []), "BARO", {"TimeUS": "TimeUS", "Alt": "Alt", "Press": "Press", "Temp": "Temp", "I": "I"})
    df_ctun = _extract_by_fields(grouped_msgs.get("CTUN", []), "CTUN", {"TimeUS": "TimeUS", "ThO": "ThO", "CRt": "CRt", "Alt": "Alt"})
    df_psc = _extract_by_fields(grouped_msgs.get("PSC", []), "PSC", {"TimeUS": "TimeUS", "VX": "VX", "VY": "VY", "VE": "VE", "VN": "VN"})
    df_psce = _extract_by_fields(grouped_msgs.get("PSCE", []), "PSCE", {"TimeUS": "TimeUS", "PE": "PE", "VE": "VE"})
    df_pscn = _extract_by_fields(grouped_msgs.get("PSCN", []), "PSCN", {"TimeUS": "TimeUS", "PN": "PN", "VN": "VN"})
    df_bat = _extract_by_fields(
        grouped_msgs.get("BAT", []),
        "BAT",
        {
            "TimeUS": "TimeUS",
            "Volt": "Volt",
            "Curr": "Curr",
            "EnrgTot": "EnrgTot",
            "CurrTot": "CurrTot",
            "Res": "Res",
        },
    )
    df_rcin = _extract_by_fields(grouped_msgs.get("RCIN", []), "RCIN", {"TimeUS": "TimeUS", "C1": "C1", "C2": "C2", "C3": "C3", "C4": "C4"})

    rcou_rows: list[dict[str, object]] = []
    for msg in grouped_msgs.get("RCOU", []):
        row: dict[str, object] = {"TimeUS": getattr(msg, "TimeUS", None)}
        for channel in range(1, 15):
            row[f"C{channel}"] = getattr(msg, f"C{channel}", None)
        rcou_rows.append(row)
    df_rcou = _relative_time(pd.DataFrame(rcou_rows))

    vibe_rows: list[dict[str, object]] = []
    for msg in grouped_msgs.get("VIBE", []):
        instance = getattr(msg, "IMU", getattr(msg, "I", getattr(msg, "Instance", 0)))
        vibe_rows.append(
            {
                "TimeUS": getattr(msg, "TimeUS", None),
                "VibeX": getattr(msg, "VibeX", None),
                "VibeY": getattr(msg, "VibeY", None),
                "VibeZ": getattr(msg, "VibeZ", None),
                "Clip": getattr(msg, "Clip", None),
                "IMU": 0 if instance is None else instance,
            }
        )
    df_vibe = _relative_time(pd.DataFrame(vibe_rows))

    return {
        "att": df_att,
        "gps": df_gps,
        "baro": df_baro,
        "psc": df_psc,
        "psce": df_psce,
        "pscn": df_pscn,
        "bat": df_bat,
        "ctun": df_ctun,
        "rcin": df_rcin,
        "rcou": df_rcou,
        "vibe": df_vibe,
        "nkf1": _extract_generic(grouped_msgs.get("NKF1", []), "NKF1"),
        "nkf2": _extract_generic(grouped_msgs.get("NKF2", []), "NKF2"),
        "nkf3": _extract_generic(grouped_msgs.get("NKF3", []), "NKF3"),
        "nkf4": _extract_generic(grouped_msgs.get("NKF4", []), "NKF4"),
        "xkf1": _extract_generic(grouped_msgs.get("XKF1", []), "XKF1"),
        "xkf2": _extract_generic(grouped_msgs.get("XKF2", []), "XKF2"),
        "xkf3": _extract_generic(grouped_msgs.get("XKF3", []), "XKF3"),
        "xkf4": _extract_generic(grouped_msgs.get("XKF4", []), "XKF4"),
        "nkf9": _extract_generic(grouped_msgs.get("NKF9", []), "NKF9"),
        "prx": _extract_generic(grouped_msgs.get("PRX", []), "PRX"),
        "oa": _extract_generic(grouped_msgs.get("OA", []), "OA"),
        "mag": _extract_generic(grouped_msgs.get("MAG", []), "MAG"),
        "ahr2": _extract_by_fields(grouped_msgs.get("AHR2", []), "AHR2", {"TimeUS": "TimeUS", "Yaw": "Yaw"}),
        "mode": _extract_mode_messages(grouped_msgs.get("MODE", []) + grouped_msgs.get("MSG", [])),
        "armed": _extract_armed_messages(grouped_msgs.get("ARM", []) + grouped_msgs.get("MSG", [])),
    }


def critical_messages(messages: list[object]) -> list[str]:
    """Filter relevant warning/error operator messages from MSG entries."""
    keys = (
        "ekf",
        "prearm",
        "gps",
        "battery",
        "compass",
        "failsafe",
        "rally",
        "rtl",
        "mode",
        "error",
        "warn",
        "warning",
        "fault",
    )
    out: list[str] = []

    for msg in messages:
        if msg.get_type() != "MSG":
            continue
        text = getattr(msg, "Message", "") or getattr(msg, "Msg", "")
        if not isinstance(text, str):
            text = str(text)

        if not any(key in text.lower() for key in keys):
            continue

        time_us = getattr(msg, "TimeUS", None)
        if time_us is None:
            out.append(text)
            continue

        try:
            time_s = float(time_us) / 1_000_000.0
            out.append(f"[t={time_s:.2f}s] {text}")
        except Exception:
            out.append(text)

    return out

def extract_utc_start_time(messages: list[object]) -> datetime | None:
    """
    Attempt to find the UTC start time of the flight log.
    Tries MSG 'Starting logging at', then GPS time conversion.
    """

    # 1. Look for 'Starting logging at' in MSG records
    for msg in messages:
        if msg.get_type() == "MSG":
            text = getattr(msg, "Message", "") or getattr(msg, "Msg", "")
            if "Starting logging at" in text:
                try:
                    # Format: "Starting logging at Jan 1, 2024 12:00:00" or similar
                    # Often "Starting logging at 2024/01/01 12:00:00"
                    parts = text.split("Starting logging at")[-1].strip()
                    # Common ArduPilot format: "2024/05/20 10:30:15"
                    for fmt in ("%Y/%m/%d %H:%M:%S", "%b %d, %Y %H:%M:%S"):
                        try:
                            return datetime.strptime(parts, fmt).replace(tzinfo=timezone.utc)
                        except ValueError:
                            continue
                except Exception:
                    pass

    # 2. Extract from GPS messages (GWk, GMS)
    gps_msgs = [m for m in messages if m.get_type() == "GPS"]
    if gps_msgs:
        # Sort by TimeUS to find the first one with valid lock
        gps_msgs.sort(key=lambda x: getattr(x, "TimeUS", 0))
        for msg in gps_msgs:
            gwk = getattr(msg, "GWk", None)
            gms = getattr(msg, "GMS", None)
            if gwk is not None and gms is not None and gwk > 0:
                # GPS Epoch: January 6, 1980
                gps_epoch = datetime(1980, 1, 6, tzinfo=timezone.utc)
                # GPS time is UTC + leap_seconds. Leap seconds as of 2024 is 18.
                leap_seconds = 18
                unix_time = (gwk * 7 * 24 * 3600) + (gms / 1000.0) + 315964800 - leap_seconds
                return datetime.fromtimestamp(unix_time, tz=timezone.utc)

    return None
