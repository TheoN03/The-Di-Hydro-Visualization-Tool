
import os, re, json, ast, subprocess, threading, queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import cv2

# Keep RTSP attempts short so a missing camera does not freeze the GUI.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|stimeout;3000000|timeout;3000000")

# ==== CAMERA CONFIG (same RTSP connection style as ar_display.py) ====
CAM_IP = "192.168.1.30"
USERNAME = "admin"
PASSWORD = "ERFQRH"
CHANNEL_MAIN = "102"
CHANNEL_SUB = "102"
ENABLE_PTZ = False

def build_rtsp_url(channel):
    return f"rtsp://{USERNAME}:{PASSWORD}@{CAM_IP}:554/Streaming/Channels/{channel}"

# ---------------------- Theme ----------------------
DARK_BG = "#1e293b"
PANEL_BG = "#0f172a"
CARD_BG = "#111827"
TEXT = "#e5e7eb"
SUBTLE = "#94a3b8"
OK_GREEN = "#10b981"
WARN_YELLOW = "#f59e0b"
ALERT_RED = "#ef4444"
GRID_ACCENT = "#334155"
GRAPH_FACE = "#0b1220"

class Theme:
    def __init__(self):
        self.dark_bg = DARK_BG
        self.panel_bg = PANEL_BG
        self.card_bg = CARD_BG
        self.text = TEXT
        self.subtle = SUBTLE
        self.ok = OK_GREEN
        self.warn = WARN_YELLOW
        self.alert = ALERT_RED
        self.grid = GRID_ACCENT
        self.graph_face = GRAPH_FACE
        self.graph_line = OK_GREEN

THEME = Theme()


# ---------------------- Semi-transparent guided help overlay ----------------------
def show_guided_help_overlay(owner, title, subtitle, annotations):
    """Draw a semi-transparent tutorial overlay over `owner` with arrows to widgets.

    annotations: list of tuples (widget, text, side), where side is 'left' or 'right'.
    """
    try:
        owner.update_idletasks()
    except Exception:
        pass

    root = owner.winfo_toplevel()
    try:
        root.update_idletasks()
    except Exception:
        pass

    try:
        x = owner.winfo_rootx()
        y = owner.winfo_rooty()
        w = max(900, owner.winfo_width())
        h = max(620, owner.winfo_height())
    except Exception:
        x = root.winfo_rootx(); y = root.winfo_rooty(); w = 1100; h = 720

    overlay = tk.Toplevel(root)
    overlay.overrideredirect(True)
    overlay.geometry(f"{w}x{h}+{x}+{y}")
    try:
        overlay.attributes("-topmost", True)
        overlay.attributes("-alpha", 0.90)
    except Exception:
        pass

    canvas = tk.Canvas(overlay, bg="#020617", highlightthickness=0, bd=0)
    canvas.pack(fill=tk.BOTH, expand=True)
    canvas.create_rectangle(0, 0, w, h, fill="#020617", outline="")

    def close(_evt=None):
        try:
            overlay.destroy()
        except Exception:
            pass

    overlay.bind("<Escape>", close)
    canvas.bind("<Button-3>", close)

    # Header
    canvas.create_text(w//2, 30, text=title, fill="#e5e7eb", font=("Segoe UI", 17, "bold"))
    canvas.create_text(w//2, 60, text=subtitle, fill="#cbd5e1", font=("Segoe UI", 10), width=w-220)
    canvas.create_text(w//2, h-22, text="Left click outside the controls or press Esc to close", fill="#94a3b8", font=("Segoe UI", 9))

    def widget_box(widget):
        try:
            widget.update_idletasks()
            wx = widget.winfo_rootx() - x
            wy = widget.winfo_rooty() - y
            ww = max(1, widget.winfo_width())
            wh = max(1, widget.winfo_height())
            if wx + ww < 0 or wy + wh < 0 or wx > w or wy > h:
                return None
            return wx, wy, ww, wh
        except Exception:
            return None

    left_i = 0
    right_i = 0

    def annotate(widget, text, side="left"):
        nonlocal left_i, right_i
        box = widget_box(widget)
        if box is None:
            return
        wx, wy, ww, wh = box
        cx, cy = wx + ww/2, wy + wh/2

        pad = 6
        canvas.create_rectangle(wx-pad, wy-pad, wx+ww+pad, wy+wh+pad, outline="#f97316", width=3)
        canvas.create_rectangle(wx-pad, wy-pad, wx+ww+pad, wy+wh+pad, outline="#38bdf8", width=1)

        box_w = 310
        box_h = 92
        if side == "left":
            idx = left_i; left_i += 1
            tx = max(24, min(w - box_w - 24, cx - 410))
        else:
            idx = right_i; right_i += 1
            tx = max(24, min(w - box_w - 24, cx + 110))
        ty = max(92, min(h - box_h - 70, 96 + idx * 116))

        canvas.create_rectangle(tx, ty, tx+box_w, ty+box_h, fill="#111827", outline="#38bdf8", width=2)
        canvas.create_text(tx+14, ty+12, anchor="nw", text=text, fill="#e5e7eb", font=("Segoe UI", 10), width=box_w-28)

        start_x = tx + box_w if side == "left" else tx
        start_y = ty + box_h/2
        canvas.create_line(start_x, start_y, cx, cy, fill="#38bdf8", width=2, arrow="last")

    for item in annotations:
        try:
            widget, text, side = item
        except Exception:
            continue
        if widget is not None:
            annotate(widget, text, side)

    close_btn = tk.Button(overlay, text="Close help", command=close, bg="#0f172a", fg="white", relief="flat", padx=16, pady=7, font=("Segoe UI", 10, "bold"))
    canvas.create_window(w-95, h-44, window=close_btn)

    def close_on_background(evt):
        pass
    canvas.bind("<Button-1>", close_on_background)
    try:
        overlay.lift()
        overlay.focus_force()
    except Exception:
        pass
    return overlay


# ---------------------- Tab 2 AR sizing
AR_CARD_SCALE = 3.0
AR_GRAPH_SCALE = 3.0
AR_CARD_W_FRAC = 0.33
AR_CARD_W_MAX = 420
AR_HUD_TITLE_FS = 12
AR_HUD_VALUE_FS = 12

CALLOUT_POSITIONS = [
    {"relx":0.18, "rely":0.22},
    {"relx":0.52, "rely":0.38},
    {"relx":0.78, "rely":0.20},
]

# ---------------------- JSON & Config ----------------------
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR_DEFAULT = os.path.join(os.path.dirname(ROOT_DIR), "config")
os.makedirs(CONFIG_DIR_DEFAULT, exist_ok=True)

NAME_MAP_PATH = os.path.join(CONFIG_DIR_DEFAULT, "param_name_map.json")
UNIT_CODES_PATH = os.path.join(CONFIG_DIR_DEFAULT, "unit_param_codes.json")
THRESHOLDS_PATH = os.path.join(CONFIG_DIR_DEFAULT, "thresholds.json")
RTSP_CONFIG_PATH = os.path.join(CONFIG_DIR_DEFAULT, "rtsp_camera_config.json")
MQTT_CONFIG_PATH = os.path.join(CONFIG_DIR_DEFAULT, "mqtt_partner_config.json")

def load_json_or_empty(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_json_safely(path, data:dict):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception as e:
        messagebox.showerror("Save error", f"Failed to save config:\n{e}")

PARAM_NAME_MAP = load_json_or_empty(NAME_MAP_PATH)
UNIT_PARAM_CODES = load_json_or_empty(UNIT_CODES_PATH)
THRESHOLDS = load_json_or_empty(THRESHOLDS_PATH)
RTSP_CAMERA_CONFIG = load_json_or_empty(RTSP_CONFIG_PATH)
MQTT_PARTNER_CONFIG = load_json_or_empty(MQTT_CONFIG_PATH)

CAM_IP = RTSP_CAMERA_CONFIG.get("ip", CAM_IP)
USERNAME = RTSP_CAMERA_CONFIG.get("username", USERNAME)
PASSWORD = RTSP_CAMERA_CONFIG.get("password", PASSWORD)
CHANNEL_MAIN = str(RTSP_CAMERA_CONFIG.get("channel_main", CHANNEL_MAIN))
CHANNEL_SUB = str(RTSP_CAMERA_CONFIG.get("channel_sub", CHANNEL_SUB))
RTSP_PORT = str(RTSP_CAMERA_CONFIG.get("port", "554"))

def build_rtsp_url(channel):
    return f"rtsp://{USERNAME}:{PASSWORD}@{CAM_IP}:{RTSP_PORT}/Streaming/Channels/{channel}"

# ---------------------- Utils ----------------------
CODE_REGEX = re.compile(r"\(([A-Za-z0-9_\-]+):")
CODE_TAG_REGEX = re.compile(r"\(([A-Za-z0-9_\-]+):([^\)\s]+)\)")

def extract_code(col_name: str):
    if not col_name:
        return None
    m = CODE_REGEX.search(str(col_name))
    if m: return m.group(1).upper()
    m2 = re.search(r"([0-9A-Z]{6,})", str(col_name), flags=re.I)
    return m2.group(1).upper() if m2 else None

def friendly_name_for(col_name: str):
    code = extract_code(col_name)
    if code and code in PARAM_NAME_MAP: 
        return PARAM_NAME_MAP[code]
    return str(col_name)

def extract_code_and_tag(col_name: str):
    if not col_name:
        return (None, None)
    m = CODE_TAG_REGEX.search(str(col_name))
    if m:
        return (m.group(1).upper(), m.group(2))
    code = extract_code(col_name)
    return (code, None)

def extract_unit(name: str):
    """Pull the last (...) group as unit, e.g., (Hz), (MW), (°C)."""
    if not name: return ""
    m = re.findall(r"\(([^)]+)\)", str(name))
    return m[-1] if m else ""


def _coerce_jsonish(value):
    """Accept real JSON values or NGSI-LD values exported as Python-dict strings."""
    if isinstance(value, str):
        txt = value.strip()
        if (txt.startswith("{") and txt.endswith("}")) or (txt.startswith("[") and txt.endswith("]")):
            try:
                return ast.literal_eval(txt)
            except Exception:
                try:
                    return json.loads(txt)
                except Exception:
                    return value
    return value

def _extract_prop_value(value, default=None):
    value = _coerce_jsonish(value)
    if isinstance(value, dict) and "value" in value:
        return value.get("value", default)
    return value if value not in (None, "") else default

def _parse_parameter_json_obj(obj, source_name=""):
    """Return name, category, timestamp, value, unit from partner JSON rows."""
    name = _extract_prop_value(obj.get("name"), source_name or "JSON Parameter")
    category = _extract_prop_value(obj.get("category"), "JSON")
    date_modified = _extract_prop_value(obj.get("dateModified"), None)
    created = _coerce_jsonish(obj.get("measurement_timerelsystem_CreatedAt") or obj.get("name_timerelsystem_CreatedAt"))
    if isinstance(created, list) and created:
        created = created[0]
    ts = date_modified or created or obj.get("timestamp") or obj.get("time") or obj.get("date") or ""
    measurement = _coerce_jsonish(obj.get("measurement"))
    unit = ""
    val = None
    if isinstance(measurement, dict):
        val = measurement.get("value")
        mu = measurement.get("measurementUnit")
        unit = _extract_prop_value(mu, "") if mu is not None else ""
    else:
        val = measurement
    try:
        val = float(val)
    except Exception:
        val = np.nan
    return {
        "name": str(name),
        "category": str(category),
        "timestamp": str(ts),
        "value": val,
        "unit": str(unit or ""),
        "source": source_name,
    }

def _read_partner_json_records(path):
    """Read one JSON file. Supports a single object, list of objects, or dict containing records/items/data."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        for key in ("records", "items", "data", "observations"):
            if isinstance(raw.get(key), list):
                items = raw[key]
                break
        else:
            items = [raw]
    else:
        items = []
    return [_parse_parameter_json_obj(x, os.path.basename(path)) for x in items if isinstance(x, dict)]

def _load_partner_json_folder(path):
    """Load every JSON in a file/folder and convert to category -> dataframe."""
    paths = []
    if os.path.isdir(path):
        for root, _dirs, files in os.walk(path):
            for fn in files:
                if fn.lower().endswith(".json"):
                    paths.append(os.path.join(root, fn))
    elif os.path.isfile(path) and path.lower().endswith(".json"):
        paths = [path]
    rows = []
    for jp in sorted(paths):
        try:
            rows.extend(_read_partner_json_records(jp))
        except Exception as e:
            print("Failed to read JSON", jp, e)
    by_cat = {}
    for r in rows:
        if pd.isna(r.get("value")):
            continue
        cat = r.get("category") or "JSON"
        by_cat.setdefault(cat, []).append(r)
    frames = {}
    for cat, recs in by_cat.items():
        times = sorted(set(r["timestamp"] for r in recs)) or [""]
        df = pd.DataFrame({"Timestamp": pd.to_datetime(times, errors="coerce")})
        if df["Timestamp"].isna().all():
            df["Timestamp"] = times
        for name in sorted(set(r["name"] for r in recs)):
            vals_by_t = {r["timestamp"]: r for r in recs if r["name"] == name}
            unit = next((r.get("unit", "") for r in recs if r["name"] == name and r.get("unit")), "")
            col = f"{name} ({unit})" if unit else name
            df[col] = [vals_by_t.get(t, {}).get("value", np.nan) for t in times]
        frames[str(cat)] = df
    return frames

def _json_param_base_name(col_name: str) -> str:
    """Return the visible parameter name without unit suffix."""
    txt = str(col_name or "").strip()
    return re.sub(r"\s*\([^)]*\)\s*$", "", txt).strip()

def _json_param_priority(col_name: str, category: str = "") -> int:
    """Lower number = more important for the 3 AR slots.

    Priority is tuned for AE/IMU monitoring:
    1) acceleration/accelerometer
    2) gyroscope/angular velocity
    3) magnetometer/magnetic field
    then orientation, temperature, pressure, humidity, analog voltage.
    """
    txt = f"{col_name} {category}".lower()
    rules = [
        (0, ("acceleration", "accelerometer", "accel")),
        (10, ("gyroscope", "gyro", "angularvelocity", "angular velocity")),
        (20, ("magnetometer", "magneticfield", "magnetic field", "magnet")),
        (30, ("orientation", "roll", "pitch", "yaw")),
        (40, ("temperature", "tempc", "degc")),
        (50, ("pressure", "barometric", "hpa")),
        (60, ("humidity", "%rh")),
        (70, ("analog", "voltage", "input")),
    ]
    for score, keys in rules:
        if any(k in txt for k in keys):
            axis_bonus = 0
            base = _json_param_base_name(col_name).lower()
            if re.search(r"\bx\b", base):
                axis_bonus = 0
            elif re.search(r"\by\b", base):
                axis_bonus = 1
            elif re.search(r"\bz\b", base):
                axis_bonus = 2
            return score + axis_bonus
    return 999

def _collect_json_parameter_series(frames: dict):
    """Collect numeric JSON parameter series across ALL categories.

    Returns:
      unique_cols: prioritized visible column labels
      series_map: col -> numeric values
      times_map:  col -> timestamp strings
      category_map: col -> source JSON category
    """
    items = []
    seen_base = set()
    for category, df in (frames or {}).items():
        if df is None or getattr(df, "empty", True):
            continue
        ts_col = "Timestamp" if "Timestamp" in df.columns else df.columns[0]
        try:
            parsed_ts = pd.to_datetime(df[ts_col], errors="coerce")
            if parsed_ts.notna().any():
                df = df.assign(_parsed_ts=parsed_ts).sort_values("_parsed_ts").drop(columns=["_parsed_ts"])
        except Exception:
            pass
        for col in df.columns:
            if col == ts_col:
                continue
            s_num = pd.to_numeric(df[col], errors="coerce")
            valid = s_num.notna()
            if valid.sum() <= 0:
                continue
            col_name = str(col)
            base = _json_param_base_name(col_name).lower()
            if base in seen_base:
                continue
            seen_base.add(base)
            try:
                times = df.loc[valid, ts_col].astype(str).tolist()
            except Exception:
                times = []
            items.append({
                "name": col_name,
                "category": str(category),
                "priority": _json_param_priority(col_name, str(category)),
                "count": int(valid.sum()),
                "series": s_num[valid].astype(float).tolist(),
                "times": times,
            })

    items.sort(key=lambda x: (x["priority"], -x["count"], x["name"].lower()))
    unique_cols = [x["name"] for x in items]
    series_map = {x["name"]: x["series"] for x in items}
    times_map = {x["name"]: x["times"] for x in items}
    category_map = {x["name"]: x["category"] for x in items}
    return unique_cols, series_map, times_map, category_map

def _build_wide_df_from_json_frames(frames: dict):
    """Build one wide DataFrame from all JSON categories for Tab 1 JSON loading."""
    cols, series_map, times_map, cat_map = _collect_json_parameter_series(frames)
    max_len = max((len(series_map.get(c, [])) for c in cols), default=0)
    if max_len <= 0:
        return pd.DataFrame()
    timestamps = []
    for i in range(max_len):
        t = ""
        for c in cols:
            tm = times_map.get(c, [])
            if i < len(tm) and tm[i]:
                t = tm[i]
                break
        timestamps.append(t or str(i))
    df = pd.DataFrame({"Timestamp": pd.to_datetime(timestamps, errors="coerce")})
    if df["Timestamp"].isna().all():
        df["Timestamp"] = timestamps
    for c in cols:
        vals = list(series_map.get(c, []))
        if len(vals) < max_len:
            vals = vals + [np.nan] * (max_len - len(vals))
        df[c] = vals[:max_len]
    return df

# ---------------------- Single Circle Light ----------------------
class SingleBlinkLight(tk.Canvas):
    def __init__(self, parent, color, diameter=16):
        super().__init__(parent, width=diameter+4, height=diameter+4, bg=THEME.card_bg, highlightthickness=0)
        self.color = color
        self.circle = self.create_oval(2,2,2+diameter,2+diameter, fill=color, outline="")
        self._after_id = None
        self.off()

    def on(self, blink=False):
        self.itemconfig(self.circle, state="normal", fill=self.color)
        if self._after_id:
            self.after_cancel(self._after_id); self._after_id=None
        if blink:
            self._blink()

    def _blink(self):
        state = self.itemcget(self.circle, "state")
        self.itemconfig(self.circle, state=("hidden" if state=="normal" else "normal"))
        self._after_id = self.after(450, self._blink)

    def off(self):
        if self._after_id:
            self.after_cancel(self._after_id); self._after_id=None
        self.itemconfig(self.circle, state="hidden")

# ---------------------- Graph ----------------------
class MiniGraph(tk.Frame):
    WINDOW = 20  

    def __init__(self, parent):
        super().__init__(parent, bg=THEME.card_bg)
        self.fig, self.ax = plt.subplots(figsize=(3.6, 1.9), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        self._x_vals = []
        self._y_vals = []
        self._line = None
        self._scatter = None

        self.tip = tk.Toplevel(self)
        self.tip.withdraw()
        self.tip.overrideredirect(True)
        try:
            self.tip.attributes("-topmost", True)
        except Exception:
            pass
        self.tip_lbl = tk.Label(self.tip, text="", bg="#0f172a", fg=THEME.text, bd=1, relief="solid", padx=10, pady=6, font=("Segoe UI", 12))
        self.tip_lbl.pack()

        self.canvas.mpl_connect("motion_notify_event", self._on_hover)
        self.canvas.mpl_connect("axes_leave_event", self._on_leave)
        self.bind("<Destroy>", self._on_destroy)

        self._style_axes_and_annotation()

    def _on_destroy(self, event):
        try:
            if getattr(self, "tip", None) is not None:
                self.tip.destroy()
        except Exception:
            pass

    def _style_axes_and_annotation(self):
        self.fig.patch.set_facecolor(THEME.graph_face)
        self.ax.set_facecolor(THEME.graph_face)
        self.ax.clear()
        for s in ("bottom","top","left","right"):
            self.ax.spines[s].set_color(THEME.grid)
        self.ax.tick_params(axis="x", colors=THEME.subtle, labelsize=7)
        self.ax.tick_params(axis="y", colors=THEME.subtle, labelsize=7)
        
    def _on_leave(self, event):
        try:
            self.tip.withdraw()
        except Exception:
            pass
        self.canvas.draw_idle()

    def _nearest_index(self, xdata):
        if not self._y_vals:
            return 0
        idx = int(round(xdata))
        return max(0, min(idx, len(self._y_vals)-1))

    def _on_hover(self, event):
        if event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            try: self.tip.withdraw()
            except Exception: pass
            self.canvas.draw_idle()
            return
        idx = self._nearest_index(event.xdata)
        ts = self._x_vals[idx] if self._x_vals else idx
        val = self._y_vals[idx] if self._y_vals else 0.0
        try:
            x_root = int(getattr(event, "guiEvent").x_root) + 12
            y_root = int(getattr(event, "guiEvent").y_root) + 12
        except Exception:
            widget = self.canvas.get_tk_widget()
            x_root = widget.winfo_rootx() + int(event.x) + 12 if hasattr(event, "x") else widget.winfo_rootx()+20
            y_root = widget.winfo_rooty() + int(event.y) + 12 if hasattr(event, "y") else widget.winfo_rooty()+20
        self.tip_lbl.config(text=f"{val:.3f}\n{ts}")
        self.tip.geometry(f"+{x_root}+{y_root}")
        try:
            self.tip.deiconify()
            self.tip.lift()
            self.tip.attributes("-topmost", True)
        except Exception:
            pass
        self.canvas.draw_idle()

    def set_values(self, y_values, pre=None, alert=None, x_values=None):
        arr = pd.to_numeric(pd.Series(y_values), errors="coerce").dropna().tolist()
        if not arr: arr = [0.0]
        xs = x_values if x_values is not None else list(range(len(arr)))
        arr = arr[-self.WINDOW:]
        xs  = xs[-self.WINDOW:]
        self._x_vals = xs
        self._y_vals = arr

        self._style_axes_and_annotation()

        x = list(range(len(arr)))
        last = arr[-1]
        if (alert is not None) and (last > alert):
            line_color = THEME.alert
        elif (pre is not None) and (last > pre):
            line_color = THEME.warn
        else:
            line_color = THEME.ok

        self._line, = self.ax.plot(x, arr, lw=2, zorder=2, color=line_color)

        colors = []
        for v in arr:
            if (alert is not None) and (v > alert):
                colors.append(THEME.alert)
            elif (pre is not None) and (v > pre):
                colors.append(THEME.warn)
            else:
                colors.append(THEME.ok)
        self._scatter = self.ax.scatter(x, arr, s=30, marker='o', c=colors, zorder=3, edgecolors='none')

        try:
            self.ax.fill_between(x, arr, min(arr), alpha=0.22, color=line_color, zorder=1)
        except Exception:
            pass

        # ---- Hard center the Y-axis around the *last* value ----
        must_include = list(arr)
        if pre is not None:   must_include.append(pre)
        if alert is not None: must_include.append(alert)

        max_dev = max(abs(v - last) for v in must_include) if must_include else 1.0
        pad = max(1e-3, max_dev * 0.15)
        half = max_dev + pad

        min_half = 1.0 if last == 0 else abs(last) * 0.1
        half = max(half, min_half)

        self.ax.set_ylim(last - half, last + half)

        if pre is not None:   self.ax.axhline(y=pre, color=THEME.warn, linestyle=":", linewidth=2, zorder=4)
        if alert is not None: self.ax.axhline(y=alert, color=THEME.alert, linestyle=":", linewidth=2, zorder=4)

        self.canvas.draw_idle()

# ---------------------- Card ----------------------
class ValueCard(tk.Frame):
    def __init__(self, parent, title="Param"):
        super().__init__(parent, bg=THEME.card_bg, padx=8, pady=8)
        self.code_key = None  

        header = tk.Frame(self, bg=THEME.card_bg)
        header.pack(fill=tk.X)
        self.title_lbl = tk.Label(header, text=title, bg=THEME.card_bg, fg=THEME.text, font=("Segoe UI", 16, "bold"), wraplength=360, justify="left")
        self.title_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor="w")
        self.clear_btn = tk.Button(header, text="CLEAR", bg="#334155", fg="white", relief="flat", font=("Segoe UI",14,"bold"), padx=12, pady=6, command=self.acknowledge)
        self.clear_btn.pack(side=tk.RIGHT)

        row = tk.Frame(self, bg=THEME.card_bg)
        row.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(row, bg=THEME.card_bg)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0,8))

        tk.Label(left, text="Current",  bg=THEME.card_bg, fg=THEME.subtle, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        row_curr = tk.Frame(left, bg=THEME.card_bg); row_curr.pack(anchor="w", pady=(0,8), fill=tk.X)
        self.light_current = SingleBlinkLight(row_curr, THEME.ok); self.light_current.pack(side=tk.LEFT)
        self.curr_val_lbl = tk.Label(row_curr, text="--", bg=THEME.card_bg, fg=THEME.text, font=("Segoe UI", 11))
        self.curr_val_lbl.pack(side=tk.LEFT, padx=8)

        tk.Label(left, text="Pre-Alert", bg=THEME.card_bg, fg=THEME.warn, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        row_pre = tk.Frame(left, bg=THEME.card_bg); row_pre.pack(anchor="w", pady=(0,8), fill=tk.X)
        self.light_pre = SingleBlinkLight(row_pre, THEME.warn); self.light_pre.pack(side=tk.LEFT)
        self.pre_lbl = tk.Label(row_pre, text="", bg=THEME.card_bg, fg=THEME.warn, font=("Segoe UI", 9, "bold"), cursor="hand2")
        self.pre_lbl.pack(side=tk.LEFT, padx=8)

        tk.Label(left, text="Alert",    bg=THEME.card_bg, fg=THEME.alert, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        row_alert = tk.Frame(left, bg=THEME.card_bg); row_alert.pack(anchor="w", fill=tk.X)
        self.light_alert = SingleBlinkLight(row_alert, THEME.alert); self.light_alert.pack(side=tk.LEFT)
        self.alert_lbl = tk.Label(row_alert, text="", bg=THEME.card_bg, fg=THEME.alert, font=("Segoe UI", 9, "bold"), cursor="hand2")
        self.alert_lbl.pack(side=tk.LEFT, padx=8)

        self.pre_lbl.bind("<Button-1>", lambda e: self._edit_threshold("pre"))
        self.alert_lbl.bind("<Button-1>", lambda e: self._edit_threshold("alert"))

        right = tk.Frame(row, bg=THEME.card_bg)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        top_row = tk.Frame(right, bg=THEME.card_bg)
        top_row.pack(fill=tk.X)
        self.current_lbl = tk.Label(top_row, text="--", bg=THEME.card_bg, fg=THEME.text, font=("Segoe UI Semibold", 24))
        self.current_lbl.pack(side=tk.LEFT, expand=True)
        self.unit_lbl = tk.Label(top_row, text="", bg=THEME.card_bg, fg=THEME.subtle, font=("Segoe UI", 14, "bold"))
        self.unit_lbl.pack(side=tk.RIGHT)

        self.graph = MiniGraph(right); self.graph.pack(fill=tk.BOTH, expand=True, pady=(6,0))

        self.pre_band = None
        self.alert_band = None
        self.history = []
        self.history_times = []
        self.ack_index = -1
        
    def set_code_key(self, code_key: str|None):
        self.code_key = code_key

    def set_title(self, t):
        self.title_lbl.config(text=t)
        friendly = t.split(" - Param")[0]
        unit = extract_unit(friendly)
        if hasattr(self, "unit_lbl"):
            self.unit_lbl.config(text=unit)

    def set_thresholds(self, pre=None, alert=None):
        self.pre_band, self.alert_band = pre, alert
        self.pre_lbl.config(text=(f"{pre:.3f}" if pre is not None else ""))
        self.alert_lbl.config(text=(f"{alert:.3f}" if alert is not None else ""))

    def reset(self):
        self.history = []
        self.history_times = []
        self.ack_index = -1
        
        self.current_lbl.config(text="--")
        self.curr_val_lbl.config(text="--")
        self.light_current.off(); self.light_pre.off(); self.light_alert.off()
        self.graph.set_values([], pre=self.pre_band, alert=self.alert_band, x_values=[])

    def acknowledge(self):
        self.ack_index = len(self.history) - 1
        self.light_pre.off(); self.light_alert.off()

    def push_value(self, v, t=None):
        try: val = float(v)
        except Exception: return
        self.history.append(val)
        self.history_times.append(t if t is not None else len(self.history))
        self.current_lbl.config(text=f"{val:.3f}")
        self.curr_val_lbl.config(text=f"{val:.3f}")

        idx = len(self.history) - 1
        active_after_ack = (idx > self.ack_index)
        if active_after_ack and (self.alert_band is not None) and (val > self.alert_band):
            self.light_alert.on(blink=True); self.light_pre.off(); self.light_current.off()
        elif active_after_ack and (self.pre_band is not None) and (val > self.pre_band):
            self.light_pre.on(blink=True);   self.light_alert.off(); self.light_current.off()
        else:
            self.light_current.on(blink=False); self.light_pre.off(); self.light_alert.off()

        last_vals = self.history[-MiniGraph.WINDOW:]
        last_times = self.history_times[-MiniGraph.WINDOW:]
        self.graph.set_values(last_vals, pre=self.pre_band, alert=self.alert_band, x_values=last_times)

    # ---- Inline popup editor for thresholds ----
    def _edit_threshold(self, which: str):
        if which not in ("pre","alert"):
            return
        current = self.pre_band if which=="pre" else self.alert_band
        title = f"Set {which.capitalize()} Threshold"
        prompt = f"Enter {which} value (number) for\n{self.title_lbl.cget('text')}"
        value = simpledialog.askstring(title, prompt, initialvalue=(f"{current:.3f}" if isinstance(current,(int,float)) else ""))
        if value is None:
            return
        try:
            new_val = float(value)
        except Exception:
            messagebox.showerror("Invalid input", "Please enter a numeric value."); return

        if which=="pre":
            self.pre_band = new_val
            self.pre_lbl.config(text=f"{new_val:.3f}")
        else:
            self.alert_band = new_val
            self.alert_lbl.config(text=f"{new_val:.3f}")

        key = self.code_key or self.title_lbl.cget("text")
        if key:
            THRESHOLDS.setdefault(key, {})
            THRESHOLDS[key][which] = new_val
            save_json_safely(THRESHOLDS_PATH, THRESHOLDS)

# ---------------------- Main Tab (Realtime) ----------------------
class TurbineCSVTab(tk.Frame):
    UNIT_PARAMS = {
        "GENERATOR COOLING & ELECTRICAL": [
            "01MEU10OVG","01MKA10CE104","01MEU50FG","01MKA10CE105","01MKA10CE106",
            "01MKA51CT523T","01MKA12CM501","01MKA12CM502","01MEU52CF505T"
        ],
        "GENERATOR MECHANICAL": [
            "01MEU10OVG","01MKA10CE204","01MEU50FG","01MKA10CE205","01MKA10CE206",
            "01MKA51CT523T","01MKA22CM501","01MKA22CM502","01MEU52CF505T"
        ],
        "GENERATOR THERMAL": [
            "01MEU10OVG","01MKA10CE304","01MEU50FG","01MKA10CE305","01MKA10CE306",
            "01MKA51CT523T","01MKA32CM501","01MKA32CM502","01MEU52CF505T"
        ],
        "TURBINE MECHANICAL & PERFORMANCE": [
            "01MEU10OVG","01MKA10CE404","01MEU50FG","01MKA10CE405","01MKA10CE406",
            "01MKA51CT523T","01MKA42CM501","01MKA42CM502","01MEU52CF505T"
        ],
    }

    def __init__(self, parent):
        super().__init__(parent, bg=THEME.dark_bg)
        self.selected_unit = list(self.UNIT_PARAMS.keys())[0]
        self.data_by_unit = {}
        self.cards = []
        self.sim_after_id = None
        self.sim_index = 0
        self._build_ui()

    def _build_ui(self):
        header = tk.Frame(self, bg=THEME.panel_bg); header.pack(side=tk.TOP, fill=tk.X)
        tk.Label(header, text="PPC PARAMETERS UNIT 1", bg=THEME.panel_bg, fg=THEME.text, font=("Segoe UI", 18, "bold")).pack(side=tk.LEFT, padx=12, pady=10)
        self.btn_info_tab1 = tk.Button(header, text="Info", bg="#475569", fg="white", relief="flat",
                                       font=("Segoe UI", 10, "bold"), padx=12, pady=5,
                                       command=self._show_tab1_info)
        self.btn_info_tab1.pack(side=tk.RIGHT, padx=12, pady=8)

        sidebar = tk.Frame(self, bg=THEME.dark_bg); sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        tk.Label(sidebar, text="Select Component", bg=THEME.dark_bg, fg=THEME.text, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0,6))
        self.unit_buttons = {}
        for i, name in enumerate(self.UNIT_PARAMS.keys()):
            b = tk.Button(sidebar, text=name, width=34, relief="flat",
                          bg=(THEME.ok if i==0 else ALERT_RED), fg="white",
                          activebackground=THEME.ok, activeforeground="white", font=("Segoe UI", 12, "bold"),
                          padx=14, pady=10,
                          command=lambda n=name: self._select_unit(n))
            b.pack(pady=4, anchor="w")
            self.unit_buttons[name] = b

        controls = tk.Frame(self, bg=THEME.dark_bg); controls.pack(side=tk.TOP, fill=tk.X, padx=10)
        default_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        self.btn_load_all = tk.Button(controls, text="Load CSV/XLS for Tab 1", bg=THEME.ok, fg="white", relief="flat", padx=12, pady=6,
                                      font=("Segoe UI", 8, "bold"),
                                      command=lambda: self._choose_and_load(default_dir))
        self.btn_load_all.pack(side=tk.LEFT, padx=(0,8))
        self.btn_load_json_tab1 = tk.Button(controls, text="Load JSON Folder for Tab 1", bg="#0ea5e9", fg="white", relief="flat", padx=12, pady=6,
                                           font=("Segoe UI", 8, "bold"),
                                           command=self._choose_and_load_json_folder)
        self.btn_load_json_tab1.pack(side=tk.LEFT, padx=(0,8))
        self.btn_start = tk.Button(controls, text="Start ▶", bg="#0ea5e9", fg="white", relief="flat", padx=10, command=self._start_sim, state="disabled"); self.btn_start.pack(side=tk.LEFT, padx=4)
        self.btn_stop  = tk.Button(controls, text="Stop ⏸", bg="#64748b", fg="white", relief="flat", padx=10, command=self._stop_sim, state="disabled"); self.btn_stop.pack(side=tk.LEFT, padx=4)
        tk.Label(controls, text=" ", bg=THEME.dark_bg, fg=THEME.subtle, font=("Segoe UI", 12)).pack(side=tk.LEFT, padx=12)

        grid = tk.Frame(self, bg=THEME.dark_bg); grid.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        for r in range(3): grid.grid_rowconfigure(r, weight=1, uniform="row")
        for c in range(3): grid.grid_columnconfigure(c, weight=1, uniform="col")

        self.cards = []
        for i in range(9):
            card = ValueCard(grid, title=f"Param {i+1}")
            card.grid(row=i//3, column=i%3, padx=8, pady=8, sticky="nsew")
            self.cards.append(card)

        self.instruction = tk.Label(self, text='No file loaded. Click "Load file for selected units".', bg=THEME.dark_bg, fg=THEME.subtle, font=("Segoe UI", 12))
        self.instruction.place(relx=0.5, rely=0.08, anchor="n")

    def _show_tab1_info(self):
        anns = []
        anns.append((getattr(self, "btn_info_tab1", None), "Info overlay for this tab. It explains only the PPC / Tab 1 dashboard.", "right"))
        anns.append((getattr(self, "btn_load_all", None), "Load CSV/XLS for Tab 1. This is the preferred file type here and affects only Tab 1.", "right"))
        anns.append((getattr(self, "btn_load_json_tab1", None), "Load a folder of JSON snapshots for Tab 1. JSON plays in sequence, the same logic as Tab 2.", "right"))
        anns.append((getattr(self, "btn_start", None), "Start sequential playback from first value to last value, one sample per second.", "right"))
        anns.append((getattr(self, "btn_stop", None), "Stop the playback without closing the loaded dataset.", "right"))
        try:
            first_unit_btn = next(iter(self.unit_buttons.values()))
        except Exception:
            first_unit_btn = None
        anns.append((first_unit_btn, "Component selector. Each button switches the 9-card dashboard to that subsystem.", "left"))
        if getattr(self, "cards", None):
            anns.append((self.cards[0], "Parameter card: title/name, current value, unit, warning lights, CLEAR acknowledgement, thresholds, and the 20-value graph.", "right"))
            if len(self.cards) > 4:
                anns.append((self.cards[4], "Graph area: hover over points to see value and timestamp. Pre-alert/alert levels are shown as dotted lines.", "left"))
        show_guided_help_overlay(
            self,
            "Quick Guide - Tab 1 PPC / JSON Realtime Parameters",
            "CSV/Excel is preferred here, but JSON folders are also supported. Loading in this tab is isolated from the AR display.",
            anns,
        )

    def _select_unit(self, name):
        self.selected_unit = name
        for n,b in self.unit_buttons.items():
            b.config(bg=(THEME.ok if n==name else ALERT_RED))
        self._prepare_and_reset()

    # --------------- File IO ---------------
    def _choose_and_load(self, initialdir):
        fname = filedialog.askopenfilename(title="Select CSV, Excel, or JSON file for Tab 1 only",
            filetypes=[("CSV/Excel/JSON files","*.csv;*.xlsx;*.xls;*.json"),("CSV files","*.csv"),("Excel files","*.xlsx;*.xls"),("JSON files","*.json"),("All files","*.*")],
            initialdir=initialdir)
        if not fname: return
        try:
            if fname.lower().endswith(".json"):
                frames = _load_partner_json_folder(fname)
                if not frames:
                    messagebox.showerror("JSON load error", "No valid JSON parameter records found in this file."); return
                unit_names = list(self.UNIT_PARAMS.keys())
                cat_names = list(frames.keys())
                for idx, unit_name in enumerate(unit_names):
                    match = next((c for c in cat_names if c.lower() in unit_name.lower() or unit_name.lower() in c.lower()), None)
                    key = match or cat_names[min(idx, len(cat_names)-1)]
                    self.data_by_unit[unit_name] = frames[key].copy()
            elif fname.lower().endswith((".xls",".xlsx")):
                try:
                    sheets = pd.read_excel(fname, sheet_name=None, engine=None)
                except Exception:
                    sheets = pd.read_excel(fname, sheet_name=None, engine=None)
                if not sheets:
                    messagebox.showerror("Load error", "Excel file has no readable sheets."); return
                unit_names = list(self.UNIT_PARAMS.keys())
                for idx, unit_name in enumerate(unit_names):
                    sheet_key = list(sheets.keys())[min(idx, len(sheets)-1)]
                    df = sheets[sheet_key]
                    df = self._fix_headers_if_needed(df, fname)
                    ts_col = self._detect_timestamp(df)
                    if ts_col is None:
                        self.data_by_unit[unit_name] = pd.DataFrame()
                    else:
                        df = df.dropna(subset=[ts_col])
                        self.data_by_unit[unit_name] = df if not df.empty else pd.DataFrame()
            else:
                df = pd.read_csv(fname, low_memory=False)
                df = self._fix_headers_if_needed(df, fname)
                ts_col = self._detect_timestamp(df)
                if ts_col is None:
                    messagebox.showerror("Time detection", "No valid timestamps found."); return
                df = df.dropna(subset=[ts_col])
                if df.empty:
                    messagebox.showerror("Time detection", "File contains no valid timestamped rows."); return
                for unit_name in self.UNIT_PARAMS.keys():
                    self.data_by_unit[unit_name] = df.copy()
        except Exception as e:
            messagebox.showerror("Load error", f"Failed to load file:\n{e}"); return

        self._prepare_all_units_cache()
        self._prepare_and_reset()

    def _choose_and_load_json_folder(self):
        folder = filedialog.askdirectory(title="Select folder with partner JSON files")
        if not folder:
            return
        try:
            frames = _load_partner_json_folder(folder)
            if not frames:
                messagebox.showerror("JSON load error", "No valid JSON parameter records found in this folder."); return
            cat_names = list(frames.keys())
            combined_df = _build_wide_df_from_json_frames(frames)
            if combined_df.empty:
                messagebox.showerror("JSON load error", "No numeric JSON parameter values found in this folder."); return
            for unit_name in self.UNIT_PARAMS.keys():
                self.data_by_unit[unit_name] = combined_df.copy()
            self.sim_index = 0
            self._prepare_all_units_cache()
            self._prepare_and_reset()
            shown_cols = [c for c in combined_df.columns if c != "Timestamp"][:9]
            messagebox.showinfo("JSON loaded", f"Loaded JSON categories: {', '.join(cat_names)}\nDisplaying prioritized parameters: {', '.join(shown_cols)}")
        except Exception as e:
            messagebox.showerror("JSON load error", f"Failed to load JSON folder:\n{e}")

    def _fix_headers_if_needed(self, df, fname):
        try:
            first_col_name = df.columns[0] if df.shape[1] > 0 else None
            first_cell = df.iloc[0,0] if df.shape[0]>0 and df.shape[1]>0 else None
            is_bad = False
            try:
                parsed_name = pd.to_datetime(first_col_name, errors="coerce")
                if not pd.isna(parsed_name): is_bad = True
            except Exception: pass
            if not is_bad and isinstance(first_col_name, str) and (first_col_name.strip()=="" or first_col_name.lower().startswith("unnamed")):
                try:
                    parsed_cell = pd.to_datetime(first_cell, errors="coerce")
                    if not pd.isna(parsed_cell): is_bad = True
                except Exception: pass
            if is_bad:
                if fname.lower().endswith((".xls",".xlsx")):
                    df = pd.read_excel(fname, engine=None, header=None)
                else:
                    df = pd.read_csv(fname, low_memory=False, header=None)
                df.columns = [f"col{i}" for i in range(df.shape[1])]
        except Exception: pass
        return df

    def _detect_timestamp(self, df):
        for c in df.columns:
            if any(k in str(c).lower() for k in ("time","date","timestamp")):
                try:
                    df[c] = pd.to_datetime(df[c], errors="coerce")
                    if df[c].notna().any(): return c
                except Exception: pass
        for c in df.columns:
            try:
                parsed = pd.to_datetime(df[c], errors="coerce")
                if parsed.notna().sum() > 0.6*len(parsed):
                    df[c] = parsed; return c
            except Exception: pass
        if len(df.columns)>0:
            c = df.columns[0]
            try:
                num = pd.to_numeric(df[c], errors="coerce")
                parsed = pd.to_datetime(num, unit="d", origin="1899-12-30", errors="coerce")
                if parsed.notna().sum() > 0.6*len(parsed):
                    df[c] = parsed; return c
            except Exception: pass
        return None

    def _prepare_all_units_cache(self):
        self.cache_by_unit = {}
        global_times = None
        for unit_name, df in self.data_by_unit.items():
            if df is None or df.empty: 
                continue
            ts_col = None
            for c in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[c]): ts_col=c; break
            if ts_col is None:
                for c in df.columns:
                    if any(k in str(c).lower() for k in ("time","date","timestamp")): ts_col=c; break
            if ts_col is None:
                ts_col = df.columns[0]; df[ts_col]=pd.to_datetime(df[ts_col], errors="coerce")
            df_sorted = df.sort_values(by=ts_col)
            if global_times is None:
                global_times = df_sorted[ts_col].astype(str).tolist()
            desired = UNIT_PARAM_CODES.get(unit_name) or self.UNIT_PARAMS[unit_name]
            picked = self._match_columns(df_sorted, desired, ts_col)

            sim_values = []
            codes = []
            titles = []
            pre_bands = []
            alr_bands = []
            for i in range(9):
                if i < len(picked):
                    col = picked[i]
                    s_num = pd.to_numeric(df_sorted[col], errors="coerce")
                    full = s_num.dropna().tolist()
                    sim_values.append(full if len(full) else [0.0])

                    friendly = friendly_name_for(col)
                    code_only, tag = extract_code_and_tag(str(col))
                    codes.append(code_only)
                    suffix = f" ({code_only}:{tag})" if (code_only and tag) else (f" ({code_only})" if code_only else "")
                    titles.append(f"{friendly} - Param{suffix}")

                    saved = THRESHOLDS.get(code_only or titles[-1], {})
                    if "pre" in saved or "alert" in saved:
                        pre_bands.append(saved.get("pre"))
                        alr_bands.append(saved.get("alert"))
                    else:
                        mean_val = float(s_num.dropna().mean()) if s_num.notna().any() else None
                        pre_bands.append(mean_val * 1.15 if mean_val is not None else None)
                        alr_bands.append(mean_val * 1.30 if mean_val is not None else None)
                else:
                    sim_values.append([0.0])
                    codes.append(None)
                    titles.append(f"Param {i+1}")
                    pre_bands.append(None)
                    alr_bands.append(None)

            self.cache_by_unit[unit_name] = dict(
                times = global_times if global_times else (df_sorted[ts_col].astype(str).tolist() if ts_col else []),
                values = sim_values,
                codes  = codes,
                titles = titles,
                pre    = pre_bands,
                alert  = alr_bands
            )

        if not hasattr(self, "sim_index") or self.sim_index is None:
            self.sim_index = 0

    # --------------- Prepare + Realtime ---------------
    def _prepare_and_reset(self):
        df = self.data_by_unit.get(self.selected_unit)
        if df is None or df.empty:
            self._clear_cards(); return
        self.instruction.place_forget()

        c = getattr(self, "cache_by_unit", {}).get(self.selected_unit)
        if not c:
            self._prepare_all_units_cache()
            c = self.cache_by_unit.get(self.selected_unit)

        for i in range(9):
            card = self.cards[i]
            card.set_title(c["titles"][i])
            card.set_code_key(c["codes"][i])
            card.set_thresholds(pre=c["pre"][i], alert=c["alert"][i])
            upto = min(self.sim_index, len(c["values"][i])-1) if c["values"][i] else 0
            history = c["values"][i][:upto+1] if c["values"][i] else []
            times   = c["times"][:upto+1] if c["times"] else []
            card.history = list(history)
            card.history_times = list(times)
            if history:
                val = history[-1]
                card.current_lbl.config(text=f"{val:.3f}")
                card.curr_val_lbl.config(text=f"{val:.3f}")
            card.graph.set_values(card.history[-MiniGraph.WINDOW:], pre=card.pre_band, alert=card.alert_band, x_values=card.history_times[-MiniGraph.WINDOW:])

        if self.sim_after_id is None:
            self.btn_start.config(state="normal")
        self.btn_stop.config(state=("normal" if self.sim_after_id else "disabled"))

        if self.sim_after_id is None and self.sim_index == 0:
            self._start_sim()

    def _start_sim(self):
        if self.sim_after_id is not None: return
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self._tick()

    def _stop_sim(self):
        if self.sim_after_id is not None:
            try: self.after_cancel(self.sim_after_id)
            except Exception: pass
            self.sim_after_id = None
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")

    def _tick(self):
        if not getattr(self, '_alive', True):
            return
        if not hasattr(self, "cache_by_unit") or not self.cache_by_unit:
            self._stop_sim(); return
        max_len = 0
        for unit_name, c in self.cache_by_unit.items():
            for s in c["values"]:
                max_len = max(max_len, len(s))

        if self.sim_index >= max_len:
            self._stop_sim(); return

        c = self.cache_by_unit.get(self.selected_unit)
        if c:
            for i in range(9):
                s = c["values"][i]
                if not s: 
                    continue
                idx = min(self.sim_index, len(s)-1)
                t = c["times"][min(self.sim_index, len(c["times"])-1)] if c["times"] else ""
                self.cards[i].push_value(s[idx], t)

        self.sim_index += 1
        if getattr(self, '_alive', True):
            self.sim_after_id = self.after(1000, self._tick)

    def _match_columns(self, df_sorted, desired_patterns, ts_col):
        picked, seen = [], set()
        for pat in desired_patterns:
            if len(picked) >= 9: break
            for col in df_sorted.columns:
                if col == ts_col or col in seen: continue
                try:
                    if pat.lower() in str(col).lower():
                        picked.append(col); seen.add(col); break
                except Exception: continue
        if len(picked) < 9:
            for col in df_sorted.columns:
                if col == ts_col or col in seen: continue
                s = pd.to_numeric(df_sorted[col], errors="coerce")
                if s.notna().sum() > 0:
                    picked.append(col); seen.add(col)
                if len(picked) >= 9: break
        return picked

    def _clear_cards(self):
        self.instruction.place(relx=0.5, rely=0.08, anchor="n")
        for i, card in enumerate(self.cards):
            card.set_title(f"Param {i+1}")
            card.set_code_key(None)
            card.set_thresholds(pre=None, alert=None)
            card.reset()

    def prepare_to_quit(self):
        """Ensure all timers are cancelled before app exit."""
        try:
            self._alive = False
        except Exception:
            pass
        try:
            self._stop_sim()
        except Exception:
            pass


# ===================== TAB 2 - AR three-right stacked panels =====================
from PIL import Image, ImageTk
import cv2
import random

FALLBACK_GROUPS = {
    "GENERATOR COOLING & ELECTRICAL": [
        "01MEU10OVG","01MKA10CE104","01MEU50FG","01MKA10CE105","01MKA10CE106",
        "01MKA51CT523T","01MKA12CM501","01MKA12CM502","01MEU52CF505T"
    ],
    "GENERATOR MECHANICAL": [
        "01MEU10OVG","01MKA10CE204","01MEU50FG","01MKA10CE205","01MKA10CE206",
        "01MKA51CT523T","01MKA22CM501","01MKA22CM502","01MEU52CF505T"
    ],
    "GENERATOR THERMAL": [
        "01MEU10OVG","01MKA10CE304","01MEU50FG","01MKA10CE305","01MKA10CE306",
        "01MKA51CT523T","01MKA32CM501","01MKA32CM502","01MEU52CF505T"
    ],
    "TURBINE MECHANICAL & PERFORMANCE": [
        "01MEU10OVG","01MKA10CE404","01MEU50FG","01MKA10CE405","01MKA10CE406",
        "01MKA51CT523T","01MKA42CM501","01MKA42CM502","01MEU52CF505T"
    ],
}

ALL_GROUPS = UNIT_PARAM_CODES if UNIT_PARAM_CODES else FALLBACK_GROUPS
GENERATOR_GROUPS = {k:v for k,v in ALL_GROUPS.items() if k.upper().startswith("GENERATOR")}
TURBINE_GROUPS   = {k:v for k,v in ALL_GROUPS.items() if "TURBINE" in k.upper()}
if not GENERATOR_GROUPS:
    GENERATOR_GROUPS = {k:v for i,(k,v) in enumerate(ALL_GROUPS.items()) if i<3}
if not TURBINE_GROUPS:
    TURBINE_GROUPS = {list(ALL_GROUPS.keys())[-1]: list(ALL_GROUPS.values())[-1]}

def _friendly_name(code: str):
    if code and code in PARAM_NAME_MAP:
        return PARAM_NAME_MAP[code]
    return code or "Parameter"

def _extract_unit_from_name(name: str):
    if not name: return ""
    import re
    m = re.findall(r"\(([^)]+)\)", str(name))
    return m[-1] if m else ""


class WarningOverlay(tk.Frame):
    """
    In-widget animated warning overlay (reliable across platforms).
    Two distinct animation styles:
      - PRE-ALERT (kind=1): orange pulse “beacon”
      - ALERT     (kind=2): red flash + shake “siren”

    It is placed inside the Matplotlib canvas Tk widget (top-right).
    """

    def __init__(self, master_widget: tk.Widget, kind: int, title: str, value: str,
                 pre=None, alert=None, on_close=None):
        super().__init__(master_widget, bg=THEME.panel_bg, bd=0, highlightthickness=0)
        self.master_widget = master_widget
        self.kind = int(kind)
        self.on_close = on_close
        self._pre = pre
        self._alert = alert
        self._title = title or ""
        self._value = value or "--"

        self._anim_after = None
        self._shake_phase = 0
        self._pulse_phase = 0
        self._flash_on = True

        self._w = 320 if self.kind >= 2 else 300
        self._h = 120 if self.kind >= 2 else 105

        self.canvas = tk.Canvas(
            self, width=self._w, height=self._h,
            bg=THEME.panel_bg, highlightthickness=0, bd=0
        )
        self.canvas.pack(fill="both", expand=True)

        self._base_x = -10
        self._base_y = 10
        self.place(relx=0.5, x=self._base_x, y=self._base_y, anchor="ne")
        try:
            self.lift()
        except Exception:
            pass

        self._draw_static()
        self._start()

        self.canvas.tag_bind("close", "<Button-1>", self._close_clicked)

    def _close_clicked(self, _evt=None):
        self.close()

    def close(self):
        self._stop()
        try:
            self.place_forget()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        if callable(self.on_close):
            try:
                self.on_close(self.kind)
            except Exception:
                pass

    def set_kind(self, kind: int):
        kind = int(kind)
        if kind == self.kind:
            return
        self.kind = kind
        self._w = 320 if self.kind >= 2 else 300
        self._h = 120 if self.kind >= 2 else 105
        try:
            self.canvas.configure(width=self._w, height=self._h)
        except Exception:
            pass
        self._draw_static()

    def set_text(self, title: str = None, value: str = None, pre=None, alert=None):
        if title is not None:
            self._title = str(title)
        if value is not None:
            self._value = str(value)
        self._pre = pre
        self._alert = alert
        try:
            self.canvas.itemconfigure("title", text=self._title)
            self.canvas.itemconfigure("value", text=self._value)
            self.canvas.itemconfigure("kind", text=("ALERT" if self.kind >= 2 else "PRE-ALERT"))
        except Exception:
            pass

    def _draw_static(self):
        self.canvas.delete("all")

        col = THEME.alert if self.kind >= 2 else THEME.warn
        label = "ALERT" if self.kind >= 2 else "PRE-ALERT"

        self.canvas.create_rectangle(6, 6, self._w-4, self._h-4, outline="", fill="#000000", stipple="gray25")
        self.border = self.canvas.create_rectangle(4, 4, self._w-6, self._h-6, outline=col, width=2, tags=("border",))

        self.canvas.create_text(self._w-18, 16, text="×", fill=THEME.text,
                                font=("Segoe UI", 14, "bold"), tags=("close",))

        cx, cy = 38, self._h//2
        if self.kind >= 2:
            r = 18
            pts = []
            import math as _math
            for k in range(8):
                ang = _math.radians(22.5 + k*45.0)
                pts.extend([cx + r*_math.cos(ang), cy + r*_math.sin(ang)])
            self.icon = self.canvas.create_polygon(*pts, fill=col, outline=col, width=2, tags=("icon",))
            self.canvas.create_text(cx, cy, text="!", fill=THEME.panel_bg,
                                    font=("Segoe UI", 18, "bold"), tags=("icon",))
        else:
            self.icon = self.canvas.create_polygon(cx, cy-20, cx-18, cy+16, cx+18, cy+16,
                                                   fill=col, outline=col, width=2, tags=("icon",))
            self.canvas.create_text(cx, cy+6, text="!", fill=THEME.panel_bg,
                                    font=("Segoe UI", 16, "bold"), tags=("icon",))

        self.ring = self.canvas.create_oval(cx-24, cy-24, cx+24, cy+24,
                                            outline=col, width=2, tags=("ring",))

        self.canvas.create_text(86, 22, anchor="w", text=label, fill=col,
                                font=("Segoe UI", 12, "bold"), tags=("kind",))
        self.canvas.create_text(86, 48, anchor="w", text=self._title, fill=THEME.text,
                                font=("Segoe UI", 8, "bold"), tags=("title",))
        self.canvas.create_text(86, 72, anchor="w", text=self._value, fill=THEME.text,
                                font=("Segoe UI", 10), tags=("value",))

        thr_txt = ""
        try:
            if self.kind >= 2 and self._alert is not None:
                thr_txt = f"Threshold: {float(self._alert):.3g}"
            elif self.kind == 1 and self._pre is not None:
                thr_txt = f"Threshold: {float(self._pre):.3g}"
        except Exception:
            thr_txt = ""
        if thr_txt:
            self.canvas.create_text(86, 94, anchor="w", text=thr_txt, fill=THEME.subtle,
                                    font=("Segoe UI", 8), tags=("thr",))

    def _start(self):
        self._stop()
        try:
            self.place_configure(relx=1.0, x=self._base_x, y=self._base_y, anchor="ne")
            self.lift()
        except Exception:
            pass
        self._animate()

    def _stop(self):
        if self._anim_after is not None:
            try:
                self.after_cancel(self._anim_after)
            except Exception:
                pass
        self._anim_after = None

    def _animate(self):
        col = THEME.alert if self.kind >= 2 else THEME.warn

        if self.kind >= 2:
            self._flash_on = not self._flash_on
            bcol = col if self._flash_on else THEME.panel_bg
            try:
                self.canvas.itemconfigure(self.border, outline=bcol)
                self.canvas.itemconfigure("ring", outline=bcol)
            except Exception:
                pass

            dx = 0
            if self._shake_phase % 4 == 0:
                dx = 7
            elif self._shake_phase % 4 == 1:
                dx = -7
            elif self._shake_phase % 4 == 2:
                dx = 5
            else:
                dx = -5
            self._shake_phase += 1
            try:
                self.place_configure(x=self._base_x + dx)
            except Exception:
                pass

            self._anim_after = self.after(90, self._animate)
            return

        self._pulse_phase = (self._pulse_phase + 1) % 30
        import math as _math
        t = self._pulse_phase / 29.0
        amp = 0.5 - 0.5 * _math.cos(2 * _math.pi * t)  
        r = 22 + amp * 14
        cx, cy = 38, self._h//2
        try:
            self.canvas.coords(self.ring, cx-r, cy-r, cx+r, cy+r)
            self.canvas.itemconfigure(self.border, outline=col)
            self.place_configure(x=self._base_x)
        except Exception:
            pass

        self._anim_after = self.after(55, self._animate)

class ARMiniGraph(tk.Frame):
    """Tab 2 AR graph: interactive 3D (rotate + zoom + hover tooltip).

    Controls:
      - Left mouse drag: rotate
      - Mouse wheel: zoom
      - Hover over points: popup with (t, value)
    """

    WINDOW = 300

    def __init__(self, parent):
        try:
            bg = parent.cget("bg")
        except Exception:
            bg = getattr(THEME, "dark_bg", "#0b1220")

        super().__init__(parent, bg=bg, highlightthickness=0, bd=0)

        self._bg = bg
        self._pre = None
        self._alert = None
        self._x, self._y = [], []

        self._elev = 18.0
        self._azim = 235.0
        self._zoom = 1.0

        self._ylim_frozen = None
        self._floor_y = None
        self._base_xlim = (0.0, 1.0)
        self._base_ylim = (-1.0, 1.0)
        self._base_zlim = (0.0, 1.0)

        self._dragging = False
        self._press_xy = (0, 0)
        self._press_view = (self._elev, self._azim)

        self._hud_title = ""
        self._hud_value = "--"

        self._warn_level = 0  
        self._warn_popup = None
        self._warn_popup_dismissed = 0

        self.fig = plt.figure(figsize=(7.4, 3.2), dpi=110, facecolor=bg)
        try:
            self.fig.patch.set_facecolor(bg)
            self.fig.patch.set_edgecolor(bg)
        except Exception:
            pass

        self.ax = self.fig.add_subplot(111, projection="3d")

        try:
            self.fig.subplots_adjust(left=0.0, right=1.0, bottom=0.0, top=1.0)
        except Exception:
            pass
        try:
            self.ax.set_position([0.0, 0.0, 1.0, 1.0])
        except Exception:
            pass

        try:
            self.ax.set_box_aspect((6.0, 1.25, 1.0))
        except Exception:
            pass

        try:
            self.ax.grid(False)
        except Exception:
            pass
        try:
            self.ax.set_axis_off()
        except Exception:
            pass

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        try:
            self.canvas.get_tk_widget().configure(bg=bg, highlightthickness=0, bd=0)
        except Exception:
            pass

        try:
            self.canvas.get_tk_widget().configure(highlightthickness=2, highlightbackground=bg, highlightcolor=bg)
        except Exception:
            pass

        self._tip = tk.Toplevel(self)
        self._tip.withdraw()
        self._tip.overrideredirect(True)
        try:
            self._tip.attributes("-topmost", True)
        except Exception:
            pass
        self._tip_lbl = tk.Label(
            self._tip,
            text="",
            bg="#0b1220",
            fg="#e5e7eb",
            font=("Segoe UI", 8),
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=5,
        )
        self._tip_lbl.pack()

        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)

        self._line_coll = None
        self._shade = None
        self._scatter = None
        self._pre_line = None
        self._alert_line = None

        self._redraw()

    # ----------------------------
    # Public API used by Tab 2 tiles
    # ----------------------------
    def set_thresholds(self, pre=None, alert=None):
        self._pre = None if pre is None else float(pre)
        self._alert = None if alert is None else float(alert)
        self._ylim_frozen = None
        self._compute_limits()
        self._set_warn_level(self._compute_warn_level())
        self._redraw()

    def set_hud(self, title=None, value=None):
        if title is not None:
            self._hud_title = str(title)
        if value is not None:
            self._hud_value = str(value)
        try:
            self.canvas.draw_idle()
        except Exception:
            pass

    def set_values(self, values):
        try:
            vals = [float(v) for v in values if v is not None]
        except Exception:
            return
        if len(vals) > self.WINDOW:
            vals = vals[-self.WINDOW:]
        self._y = vals
        self._x = list(range(len(vals)))
        self._compute_limits()
        self._set_warn_level(self._compute_warn_level())
        self._redraw()

    # ----------------------------
    # Internals
    # ----------------------------
    def _bg_rgba(self):
        """Return RGBA tuple for current background, using Tk color resolution."""
        try:
            r, g, b = self.winfo_rgb(self._bg)
            return (r / 65535.0, g / 65535.0, b / 65535.0, 1.0)
        except Exception:
            c = str(self._bg)
            if c.startswith("#") and len(c) == 7:
                try:
                    r = int(c[1:3], 16) / 255.0
                    g = int(c[3:5], 16) / 255.0
                    b = int(c[5:7], 16) / 255.0
                    return (r, g, b, 1.0)
                except Exception:
                    pass
            return (0.0, 0.0, 0.0, 1.0)

    def _status_color(self, yv: float) -> str:
        """Green / Orange / Red based on thresholds (kept consistent with the AR spec)."""
        pre = self._pre
        alert = self._alert
        green = "#22c55e"
        orange = "#f59e0b"
        red = "#ef4444"

        try:
            yv = float(yv)
        except Exception:
            return green

        if pre is None and alert is None:
            return green
        if pre is None and alert is not None:
            return green if yv < alert else red
        if pre is not None and alert is None:
            return green if yv < pre else orange
        if yv < pre:
            return green
        if yv < alert:
            return orange
        return red


    def _compute_warn_level(self) -> int:
        """Return 0=OK, 1=PRE-ALERT, 2=ALERT based on latest value."""
        if not self._y:
            return 0
        try:
            v = float(self._y[-1])
        except Exception:
            return 0
        pre = self._pre
        alert = self._alert

        if pre is None and alert is None:
            return 0
        if pre is None and alert is not None:
            return 2 if v >= float(alert) else 0
        if pre is not None and alert is None:
            return 1 if v >= float(pre) else 0

        if v >= float(alert):
            return 2
        if v >= float(pre):
            return 1
        return 0

    def _set_warn_level(self, level: int):
        level = int(level)
        if level == self._warn_level:
            if level > 0:
                self._update_warn_popup(level)
            return

        prev = self._warn_level
        self._warn_level = level

        if level <= 0:
            self._warn_popup_dismissed = 0
            self._close_warn_popup()
        else:
            if level > self._warn_popup_dismissed or prev != level:
                self._show_warn_popup(level)
            else:
                self._update_warn_popup(level)

        try:
            self.canvas.draw_idle()
        except Exception:
            pass

    def _on_warn_popup_closed(self, dismissed_level: int):
        try:
            self._warn_popup_dismissed = int(dismissed_level)
        except Exception:
            self._warn_popup_dismissed = 0
        self._warn_popup = None

    def _show_warn_popup(self, level: int):
        try:
            if self._warn_popup is not None:
                try:
                    if int(getattr(self._warn_popup, "kind", 0)) != int(level):
                        self._warn_popup.close()
                    else:
                        self._update_warn_popup(level)
                        return
                except Exception:
                    pass
        except Exception:
            pass

        try:
            anchor = self.canvas.get_tk_widget()
            self._warn_popup = WarningOverlay(
                master_widget=anchor,
                kind=int(level),
                title=getattr(self, "_hud_title", ""),
                value=getattr(self, "_hud_value", "--"),
                pre=getattr(self, "_pre", None),
                alert=getattr(self, "_alert", None),
                on_close=self._on_warn_popup_closed,
            )
        except Exception:
            self._warn_popup = None

    def _update_warn_popup(self, level: int):
        if self._warn_popup is None:
            return
        try:
            if int(getattr(self._warn_popup, "kind", 0)) != int(level):
                self._warn_popup.set_kind(int(level))
            self._warn_popup.set_text(
                title=getattr(self, "_hud_title", ""),
                value=getattr(self, "_hud_value", "--"),
                pre=getattr(self, "_pre", None),
                alert=getattr(self, "_alert", None),
            )
        except Exception:
            pass

    def _close_warn_popup(self):
        if self._warn_popup is None:
            return
        try:
            self._warn_popup.close()
        except Exception:
            try:
                self._warn_popup.destroy()
            except Exception:
                pass
        self._warn_popup = None

    def _compute_limits(self):

        n = len(self._y)
        if n <= 1:
            self._base_xlim = (0.0, 1.0)
            self._base_ylim = (-1.0, 1.0)
            self._base_zlim = (0.0, 1.0)
            self._ylim_frozen = (-1.0, 1.0)
            self._floor_y = -1.0
            return

        import numpy as np
        y = np.asarray(self._y, dtype=float)

        must = [float(y.min()), float(y.max())]
        if self._pre is not None:
            must.append(float(self._pre))
        if self._alert is not None:
            must.append(float(self._alert))

        ymin = float(min(must))
        ymax = float(max(must))
        span = max(1e-6, ymax - ymin)
        pad = span * 0.15

        if self._ylim_frozen is None:
            low = ymin - pad
            high = ymax + pad
            self._ylim_frozen = (low, high)
        else:
            low, high = self._ylim_frozen
            margin = span * 0.05
            if ymin < low + margin:
                low = ymin - pad
            if ymax > high - margin:
                high = ymax + pad
            self._ylim_frozen = (low, high)

        low, high = self._ylim_frozen
        self._floor_y = low  

        self._base_xlim = (0.0, float(max(1, n - 1)))
        self._base_ylim = (float(low), float(high))
        self._base_zlim = (0.0, 1.0)

    def _apply_zoom(self):
        zx = max(0.5, min(8.0, float(self._zoom)))
        x0, x1 = self._base_xlim
        y0, y1 = self._base_ylim
        z0, z1 = self._base_zlim

        cx = (x0 + x1) * 0.5
        cy = (y0 + y1) * 0.5

        hx = (x1 - x0) * 0.5 / zx
        hy = (y1 - y0) * 0.5 / zx

        try:
            self.ax.set_xlim(cx - hx, cx + hx)
            self.ax.set_ylim(cy - hy, cy + hy)
            self.ax.set_zlim(z0, z1)
        except Exception:
            pass

    def _redraw(self):
        try:
            self.ax.cla()
        except Exception:
            return

        try:
            self.ax.set_position([0.0, 0.0, 1.0, 1.0])
        except Exception:
            pass
        try:
            self.ax.set_box_aspect((6.0, 1.25, 1.0))
        except Exception:
            pass
        try:
            self.ax.grid(False)
        except Exception:
            pass
        try:
            self.ax.set_axis_off()
        except Exception:
            pass

        bg = self._bg
        rgba = self._bg_rgba()

        try:
            self.ax.set_facecolor(bg)
        except Exception:
            pass
        for a in ("xaxis", "yaxis", "zaxis"):
            try:
                getattr(self.ax, a).set_pane_color(rgba)
            except Exception:
                pass
        try:
            self.ax.grid(False)
        except Exception:
            pass
        try:
            self.ax.set_axis_off()
        except Exception:
            pass
        try:
            self.ax.set_box_aspect((6.0, 1.25, 1.0))
        except Exception:
            pass

        n = len(self._y)
        if n <= 1:
            try:
                self.ax.view_init(elev=float(self._elev), azim=float(self._azim))
            except Exception:
                pass
            self._draw_hud()
            try:
                self.canvas.draw_idle()
            except Exception:
                pass
            return

        import numpy as np
        from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

        x = np.asarray(self._x, dtype=float)
        y = np.asarray(self._y, dtype=float)
        z = np.linspace(0.0, 1.0, num=len(x), dtype=float)

        floor_y = float(self._floor_y if self._floor_y is not None else y.min())

        polys = []
        poly_colors = []
        segs = []
        seg_colors = []

        for i in range(len(x) - 1):
            p0 = (float(x[i]), float(y[i]), float(z[i]))
            p1 = (float(x[i + 1]), float(y[i + 1]), float(z[i + 1]))
            segs.append([p0, p1])

            ymid = 0.5 * (float(y[i]) + float(y[i + 1]))
            c = self._status_color(ymid)
            seg_colors.append(c)

            polys.append([
                p0,
                p1,
                (float(x[i + 1]), floor_y, float(z[i + 1])),
                (float(x[i]), floor_y, float(z[i])),
            ])
            poly_colors.append(c)

        try:
            self._shade = Poly3DCollection(polys, facecolors=poly_colors, edgecolors="none", alpha=0.18)
            self.ax.add_collection3d(self._shade)
        except Exception:
            self._shade = None

        try:
            self._line_coll = Line3DCollection(segs, colors=seg_colors, linewidths=2.2 * AR_GRAPH_SCALE)
            self.ax.add_collection3d(self._line_coll)
        except Exception:
            self._line_coll = None

        try:
            pt_colors = [self._status_color(v) for v in y]
            self._scatter = self.ax.scatter(
                x, y, z,
                s=12 * AR_GRAPH_SCALE,
                c=pt_colors,
                depthshade=True,
                alpha=0.90,
                picker=int(6 * AR_GRAPH_SCALE),
            )
        except Exception:
            self._scatter = None

        x0, x1 = float(x.min()), float(x.max())
        if self._pre is not None:
            try:
                self._pre_line = self.ax.plot([x0, x1], [self._pre, self._pre], [0.0, 1.0],
                                              linestyle="--", linewidth=1.2 * AR_GRAPH_SCALE, color="#f59e0b")[0]
            except Exception:
                self._pre_line = None
        if self._alert is not None:
            try:
                self._alert_line = self.ax.plot([x0, x1], [self._alert, self._alert], [0.0, 1.0],
                                                linestyle="--", linewidth=1.2 * AR_GRAPH_SCALE, color="#ef4444")[0]
            except Exception:
                self._alert_line = None

        self._apply_zoom()

        try:
            self.ax.view_init(elev=float(self._elev), azim=float(self._azim))
        except Exception:
            pass

        self._draw_hud()
        try:
            self.canvas.draw_idle()
        except Exception:
            pass

    def _draw_hud(self):
        try:
            txt_color = getattr(THEME, "text", "#e5e7eb")
            title = getattr(self, "_hud_title", "")
            value = getattr(self, "_hud_value", "--")

            self.ax.text2D(
                0.50, 0.985, title,
                transform=self.ax.transAxes,
                color=txt_color, fontsize=AR_HUD_TITLE_FS, fontweight="bold",
                va="top", ha="center",
            )
            self.ax.text2D(
                0.50, 0.935, value,
                transform=self.ax.transAxes,
                color=txt_color, fontsize=AR_HUD_VALUE_FS, fontweight="bold",
                va="top", ha="center",
            )
        except Exception:
            pass

    # ----------------------------
    # Mouse: rotate / zoom / hover
    # ----------------------------
    def _on_press(self, event):
        if event.inaxes != self.ax:
            return
        if getattr(event, "button", None) == 1:
            self._dragging = True
            self._press_xy = (getattr(event, "x", 0) or 0, getattr(event, "y", 0) or 0)
            self._press_view = (float(self._elev), float(self._azim))
            self._hide_tip()

    def _on_release(self, event):
        self._dragging = False

    def _on_motion(self, event):
        if event.inaxes != self.ax:
            self._hide_tip()
            return

        if self._dragging:
            x, y = (getattr(event, "x", 0) or 0), (getattr(event, "y", 0) or 0)
            dx = x - self._press_xy[0]
            dy = y - self._press_xy[1]

            elev0, azim0 = self._press_view

            self._azim = azim0 + dx * 0.25
            self._elev = max(-89.0, min(89.0, elev0 + dy * 0.20))

            try:
                self.ax.view_init(elev=float(self._elev), azim=float(self._azim))
                self.canvas.draw_idle()
            except Exception:
                pass
            return

        self._update_hover(event)

    def _on_scroll(self, event):
        step = 0.12
        direction = getattr(event, "step", None)
        if direction is None:
            direction = 1 if getattr(event, "button", None) == "up" else -1

        if direction > 0:
            self._zoom = min(8.0, float(self._zoom) * (1.0 + step))
        else:
            self._zoom = max(0.5, float(self._zoom) * (1.0 - step))

        self._apply_zoom()
        try:
            self.canvas.draw_idle()
        except Exception:
            pass

    def _update_hover(self, event):
        if self._scatter is None:
            self._hide_tip()
            return

        try:
            hit, info = self._scatter.contains(event)
        except Exception:
            hit, info = False, None

        if not hit or not info or not info.get("ind"):
            self._hide_tip()
            return

        idx = int(info["ind"][0])
        if idx < 0 or idx >= len(self._y):
            self._hide_tip()
            return

        t = idx
        v = float(self._y[idx])

        ge = getattr(event, "guiEvent", None)
        if ge is not None and hasattr(ge, "x_root") and hasattr(ge, "y_root"):
            x_root = int(ge.x_root) + 14
            y_root = int(ge.y_root) + 14
        else:
            x_root = self.winfo_rootx() + 20
            y_root = self.winfo_rooty() + 20

        self._tip_lbl.config(text=f"t={t}\nvalue={v:.4f}")
        self._tip.geometry(f"+{x_root}+{y_root}")
        self._tip.deiconify()

    def _hide_tip(self):
        try:
            self._tip.withdraw()
        except Exception:
            pass
        
class ARMiniCard(tk.Frame):
    """Compact floating AR callout used on Tab 2.

    The card stays lightweight so it reads like an augmented-reality text box
    over the live background instead of a sidebar panel.
    """

    def __init__(self, parent, init_code=None):
        super().__init__(parent, bg=THEME.dark_bg, highlightthickness=0, bd=0)
        self.param_code = init_code
        self.history = []
        self._hud_title = _friendly_name(init_code)
        self._hud_value = "--"
        self._pre = None
        self._alert = None
        self._use_dynamic_thresholds = False
        self._status = "OK"
        self._status_color = THEME.ok

        self.body = tk.Frame(
            self,
            bg="#0b1220",
            highlightthickness=2,
            highlightbackground="#38bdf8",
            highlightcolor="#38bdf8",
            bd=0,
        )
        self.body.pack(fill=tk.BOTH, expand=True)

        top = tk.Frame(self.body, bg="#0b1220")
        top.pack(fill=tk.X, padx=9, pady=(6, 1))

        self.title_lbl = tk.Label(
            top,
            text=self._hud_title,
            bg="#0b1220",
            fg=THEME.text,
            font=("Segoe UI", 9, "bold"),
            anchor="w",
            justify="left",
            wraplength=170,
        )
        self.title_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.triangle_lbl = tk.Label(
            top,
            text="▼",
            bg="#0b1220",
            fg="#38bdf8",
            font=("Segoe UI", 9, "bold"),
            width=2,
        )
        self.triangle_lbl.pack(side=tk.RIGHT, padx=(6, 0))

        self.value_lbl = tk.Label(
            self.body,
            text="--",
            bg="#0b1220",
            fg=THEME.text,
            font=("Segoe UI Semibold", 15),
            anchor="center",
        )
        self.value_lbl.pack(fill=tk.X, padx=9, pady=(0, 1))

        bottom = tk.Frame(self.body, bg="#0b1220")
        bottom.pack(fill=tk.X, padx=9, pady=(0, 6))

        self.status_dot = tk.Canvas(bottom, width=12, height=12, bg="#0b1220", highlightthickness=0, bd=0)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 6))
        self.status_circle = self.status_dot.create_oval(1, 1, 11, 11, fill=THEME.ok, outline="")

        self.status_lbl = tk.Label(
            bottom,
            text="OK",
            bg="#0b1220",
            fg=THEME.ok,
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        )
        self.status_lbl.pack(side=tk.LEFT)

        self.threshold_lbl = tk.Label(
            bottom,
            text="",
            bg="#0b1220",
            fg=THEME.subtle,
            font=("Segoe UI", 8),
            anchor="e",
        )
        self.threshold_lbl.pack(side=tk.RIGHT)

        self._apply_thresholds()
        self._refresh_box()

    def _apply_thresholds(self):
        saved = THRESHOLDS.get(self.param_code, {}) if self.param_code else {}
        pre = saved.get("pre")
        alert = saved.get("alert")

        if pre is None and alert is not None:
            pre = float(alert) * 0.8
        if alert is None and pre is not None:
            alert = float(pre) * 1.2

        self._pre = None if pre is None else float(pre)
        self._alert = None if alert is None else float(alert)
        self._use_dynamic_thresholds = (self._pre is None and self._alert is None)
        self._refresh_threshold_text()
        self._update_status_from_latest()

    def _refresh_threshold_text(self):
        parts = []
        if self._pre is not None:
            parts.append(f"Pre {self._pre:.3g}")
        if self._alert is not None:
            parts.append(f"Alert {self._alert:.3g}")
        self.threshold_lbl.config(text="  |  ".join(parts))

    def _update_status_from_latest(self):
        level = 0
        if self.history:
            try:
                v = float(self.history[-1])
                if self._alert is not None and v >= self._alert:
                    level = 2
                elif self._pre is not None and v >= self._pre:
                    level = 1
            except Exception:
                level = 0

        if level == 2:
            self._status = "ALERT"
            self._status_color = THEME.alert
        elif level == 1:
            self._status = "PRE-ALERT"
            self._status_color = THEME.warn
        else:
            self._status = "OK"
            self._status_color = THEME.ok

    def _refresh_box(self):
        try:
            self.title_lbl.config(text=self._hud_title)
            self.value_lbl.config(text=self._hud_value, fg=self._status_color)
            self.status_lbl.config(text=self._status, fg=self._status_color)
            self.status_dot.itemconfig(self.status_circle, fill=self._status_color)
        except Exception:
            pass

    def set_param_code(self, code):
        """Set displayed parameter. None/blank intentionally leaves this AR section empty."""
        self.param_code = code
        self.history = []
        if code is None or str(code).strip() == "":
            self._hud_title = ""
            self._hud_value = ""
            self._pre = None
            self._alert = None
            self._use_dynamic_thresholds = False
            self._status = ""
            self._status_color = THEME.subtle
            try:
                self.threshold_lbl.config(text="")
            except Exception:
                pass
            self._refresh_box()
            return
        self._hud_title = _friendly_name(code)
        self._hud_value = "--"
        self._status = "OK"
        self._status_color = THEME.ok
        self._apply_thresholds()
        self._refresh_box()

    def push(self, v):
        try:
            val = float(v)
        except Exception:
            return

        self.history.append(val)
        self._hud_value = f"{val:.3f}"

        if getattr(self, "_use_dynamic_thresholds", False) and len(self.history) >= 5:
            import numpy as _np
            arr = _np.array(self.history, dtype=float)
            mean_val = float(arr.mean())
            std_val = float(arr.std())
            if not _np.isfinite(std_val) or std_val == 0:
                std_val = max(1e-6, abs(mean_val) * 0.1 or 1.0)
            self._pre = mean_val + 1.5 * std_val
            self._alert = mean_val + 3.0 * std_val
            self._refresh_threshold_text()

        self._update_status_from_latest()
        self._refresh_box()

class ARParamSelectDialog(tk.Toplevel):
    def __init__(self, parent, title, groups_dict, on_pick):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=THEME.dark_bg)
        self.resizable(False, False)
        self.transient(parent)
        self.on_pick = on_pick
        try: self.grab_set()
        except Exception: pass

        frm = tk.Frame(self, bg=THEME.dark_bg); frm.pack(padx=16, pady=16)
        tk.Label(frm, text="Group", bg=THEME.dark_bg, fg=THEME.text, font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=(0,6))
        tk.Label(frm, text="Parameter", bg=THEME.dark_bg, fg=THEME.text, font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w")

        groups = list(groups_dict.keys())
        self.cbo_group = ttk.Combobox(frm, values=groups, state="readonly", width=46)
        self.cbo_group.grid(row=0, column=1, padx=(8,0), pady=(0,6))
        self.cbo_param = ttk.Combobox(frm, values=[], state="readonly", width=46)
        self.cbo_param.grid(row=1, column=1, padx=(8,0))

        def on_group_change(event=None):
            g = self.cbo_group.get()
            codes = groups_dict.get(g, [])
            display = [f"{c} - {_friendly_name(c)}" for c in codes]
            self.cbo_param.configure(values=display)
            if display:
                self.cbo_param.current(0)
        self.cbo_group.bind("<<ComboboxSelected>>", on_group_change)
        if groups:
            self.cbo_group.current(0); on_group_change()

        btns = tk.Frame(frm, bg=THEME.dark_bg); btns.grid(row=2, column=0, columnspan=2, pady=(12,0))
        tk.Button(btns, text="Cancel", bg="#334155", fg="white", relief="flat", padx=12, pady=6, command=self._cancel).pack(side=tk.RIGHT, padx=6)
        tk.Button(btns, text="Select", bg=THEME.ok, fg="white", relief="flat", padx=12, pady=6, command=self._select).pack(side=tk.RIGHT)

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _select(self):
        g = self.cbo_group.get()
        p_disp = self.cbo_param.get()
        code = p_disp.split(" - ")[0].strip() if " - " in p_disp else p_disp.strip()
        if not g or not code:
            messagebox.showerror("Pick a parameter", "Please choose a group and a parameter."); return
        try:
            self.on_pick(g, code)
        finally:
            self.destroy()

    def _cancel(self):
        self.destroy()

class ARPanelThreeRight(tk.Frame):
    """Tab 2 live stream with three fixed floating AR callouts."""

    FLOATING_POSITIONS = [
        (0.22, 0.23),
        (0.57, 0.18),
        (0.79, 0.49),
    ]

    CARD_WIDTH_RATIO = 0.16
    CARD_HEIGHT_RATIO = 0.10
    CARD_MIN_W = 165
    CARD_MAX_W = 240
    CARD_MIN_H = 78
    CARD_MAX_H = 102

    def _load_water_file(self):
        from tkinter import filedialog, messagebox
        import pandas as pd
        fname = filedialog.askopenfilename(
            title="Select Water Quality Excel",
            filetypes=[("Excel files","*.xlsx;*.xls"),("All files","*.*")]
        )
        if not fname:
            return
        try:
            sheets = pd.read_excel(fname, sheet_name=None)
            if not sheets:
                messagebox.showerror("Load error", "Excel file has no readable sheets.")
                return
            df = list(sheets.values())[0]
            ts_col = None
            for c in df.columns:
                cl = str(c).lower()
                if "time" in cl or "date" in cl or "timestamp" in cl:
                    df[c] = pd.to_datetime(df[c], errors="coerce")
                    if df[c].notna().any():
                        ts_col = c
                        break
            if ts_col is None:
                c0 = df.columns[0]
                df[c0] = pd.to_datetime(df[c0], errors="coerce")
                if df[c0].notna().any():
                    ts_col = c0
            if ts_col is None:
                messagebox.showerror("Time detection", "No valid timestamps found in water Excel.")
                return
            num_cols = []
            for c in df.columns:
                if c == ts_col:
                    continue
                s = pd.to_numeric(df[c], errors="coerce")
                if s.notna().sum() > 0:
                    num_cols.append(c)
            if not num_cols:
                messagebox.showerror("Data detection", "No numeric columns found for water quality.")
                return
            df = df.dropna(subset=[ts_col])
            self._water_ts_col = ts_col
            self._water_times = df[ts_col].astype(str).tolist()
            self._water_cols = [str(c) for c in num_cols]
            self._water_series = [[], [], []]
            for i in range(3):
                col = num_cols[i % len(num_cols)]
                series = pd.to_numeric(df[col], errors="coerce").dropna().tolist()
                self._water_series[i] = series
            self._water_indices = [0, 0, 0]
            messagebox.showinfo("Water XLSX loaded", f"Detected {len(num_cols)} numeric column(s). Using: {', '.join(self._water_cols[:3])}")
        except Exception as e:
            messagebox.showerror("Load error", f"Failed to load water Excel: {e}")

    def __init__(self, parent):
        super().__init__(parent, bg=THEME.dark_bg)
        self._alive = True
        self._tick_id = None
        self._mode_ticks = {"generator": 0, "turbine": 0, "ae": 0, "digital_twin": 0}

        bar = tk.Frame(self, bg=THEME.panel_bg)
        bar.pack(fill=tk.X)

        self.btn_gen = tk.Button(bar, text="Generator", bg=THEME.ok, fg="white", relief="flat",
                                 font=("Segoe UI", 12, "bold"), padx=14, pady=8,
                                 command=lambda: self.switch_mode("generator"))
        self.btn_gen.pack(side=tk.LEFT, padx=6, pady=6)
        self.btn_turb = tk.Button(bar, text="Turbine", bg="#2563eb", fg="white", relief="flat",
                                  font=("Segoe UI", 12, "bold"), padx=14, pady=8,
                                  command=lambda: self.switch_mode("turbine"))
        self.btn_turb.pack(side=tk.LEFT, padx=6, pady=6)
        self.btn_ae = tk.Button(bar, text="AE Sensors", bg="#2563eb", fg="white", relief="flat",
                                font=("Segoe UI", 12, "bold"), padx=14, pady=8,
                                command=lambda: self.switch_mode("ae"))
        self.btn_ae.pack(side=tk.LEFT, padx=6, pady=6)
        self.btn_digital_twin = tk.Button(bar, text="Digital Twin", bg="#2563eb", fg="white", relief="flat",
                                font=("Segoe UI", 12, "bold"), padx=14, pady=8,
                                command=lambda: self.switch_mode("digital_twin"))
        self.btn_digital_twin.pack(side=tk.LEFT, padx=6, pady=6)

        self.btn_mqtt = tk.Button(bar, text="MQTT / Mosquitto", bg="#9333ea", fg="white", relief="flat",
                                  font=("Segoe UI", 12, "bold"), padx=12, pady=6, command=self.open_mqtt_window)
        self.btn_mqtt.pack(side=tk.LEFT, padx=6, pady=6)
        self.btn_rtsp = tk.Button(bar, text="RTSP Settings", bg="#475569", fg="white", relief="flat",
                                  font=("Segoe UI", 12, "bold"), padx=12, pady=6, command=self.open_rtsp_settings)
        self.btn_rtsp.pack(side=tk.LEFT, padx=6, pady=6)
        self.btn_camera = tk.Button(bar, text="Camera OFF", bg="#64748b", fg="white", relief="flat",
                                    font=("Segoe UI", 12, "bold"), padx=12, pady=6, command=self.toggle_camera)
        self.btn_camera.pack(side=tk.LEFT, padx=6, pady=6)
        self.btn_info_tab2 = tk.Button(bar, text="Info", bg="#475569", fg="white", relief="flat",
                                      font=("Segoe UI", 12, "bold"), padx=12, pady=6,
                                      command=self._show_tab2_info)
        self.btn_info_tab2.pack(side=tk.LEFT, padx=6, pady=6)

        self.btn_load_tab2_json = tk.Button(bar, text="Load JSON Folder for Tab 2", bg="#0ea5e9", fg="white", relief="flat",
                                            font=("Segoe UI", 12, "bold"), padx=12, pady=6, command=self._load_tab2_json_for_current_mode)
        self.btn_load_tab2_json.pack(side=tk.RIGHT, padx=(6, 12), pady=6)

        self.canvas = tk.Canvas(self, bg=THEME.dark_bg, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_resize)

        self._cam = None
        self._cam_photo = None
        self._cam_active = False
        self._cam_after_id = None
        self._bg_item = None
        self._camera_enabled = False
        self._camera_loop()  

        gen_codes = []
        for v in GENERATOR_GROUPS.values():
            gen_codes.extend(list(v))
            break
        tur_codes = []
        for v in TURBINE_GROUPS.values():
            tur_codes.extend(list(v))
            break
        defaults_gen = (gen_codes + [None, None, None])[:3]
        defaults_tur = (tur_codes + [None, None, None])[:3]

        self.cards = [ARMiniCard(self.canvas, init_code=defaults_gen[i]) for i in range(3)]
        self._wins = [None, None, None]
        self.selected = {
            "generator": defaults_gen[:],
            "turbine": defaults_tur[:],
            "ae": [None, None, None],
            "digital_twin": ["Digital Twin 1", "Digital Twin 2", "Digital Twin 3"],
        }
        self.current_mode = None
        self._img = None
        self.histories = [[], [], []]

        self._water_times = []
        self._water_values = []
        self._water_idx = 0
        self._water_series = [[], [], []]
        self._water_indices = [0, 0, 0]
        self._water_cols = []
        self._water_ts_col = None

        self._ae_series_map = {}
        self._ae_series = [[], [], []]
        self._ae_indices = [0, 0, 0]
        self._ae_cols = []
        self._ae_ts_col = None

        self._tab2_json_series = {"generator": [[], [], []], "turbine": [[], [], []], "ae": [[], [], []], "digital_twin": [[], [], []]}
        self._tab2_json_indices = {"generator": [0, 0, 0], "turbine": [0, 0, 0], "ae": [0, 0, 0], "digital_twin": [0, 0, 0]}
        self._tab2_json_cols = {"generator": [], "turbine": [], "ae": [], "digital_twin": []}
        self._tab2_json_series_map = {"generator": {}, "turbine": {}, "ae": {}, "digital_twin": {}}
        self._tab2_json_times_map = {"generator": {}, "turbine": {}, "ae": {}, "digital_twin": {}}

        self._river_series_map = {}
        self._river_series = [[], [], []]
        self._river_indices = [0, 0, 0]
        self._river_cols = []
        self._river_ts_col = None

        self.switch_mode("generator")
        self._tick()

    def _find(self, filename):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        for p in (
            os.path.join(data_dir, filename),
            os.path.join(os.path.dirname(__file__), filename),
            os.path.join(os.getcwd(), filename),
        ):
            if os.path.exists(p):
                return p
        return None

    def _load_img(self, path, w, h):
        self.canvas.delete("bg")
        if not path or not os.path.exists(path):
            self._img = None
            return False
        img = Image.open(path).convert("RGB").resize((max(1, w), max(1, h)), Image.LANCZOS)
        self._img = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor="nw", image=self._img, tags="bg")
        self.canvas.tag_lower("bg")
        return True

    def _draw_placeholder_background(self, w, h, tick=0):
        """Fallback background when neither a camera nor an image asset is available."""
        from PIL import ImageDraw
        w = max(1, int(w)); h = max(1, int(h))
        img = Image.new("RGB", (w, h), "#0b1220")
        draw = ImageDraw.Draw(img)
        for y in range(0, h, max(24, h // 18 or 24)):
            shade = 18 + ((y // max(1, h // 18 or 1)) % 4) * 6
            draw.rectangle([0, y, w, min(h, y + max(24, h // 18 or 24))], fill=(shade, shade+6, shade+16))
        step_x = max(70, w // 18)
        step_y = max(55, h // 14)
        for x in range(0, w, step_x):
            draw.line([(x, 0), (x, h)], fill=(23, 35, 52), width=1)
        for y in range(0, h, step_y):
            draw.line([(0, y), (w, y)], fill=(23, 35, 52), width=1)
        offset = (tick * 6) % max(1, w + h)
        band_w = max(90, min(w, h) // 5)
        for i in range(-band_w, band_w, 3):
            x1 = i + offset
            y1 = 0
            x2 = i + offset - h
            y2 = h
            draw.line([(x1, y1), (x2, y2)], fill=(24, 73, 96), width=1)
        return ImageTk.PhotoImage(img)

    def _try_open_camera_capture_once(self):
        """Worker-thread helper. Never call this directly on the Tk UI thread."""
        for channel in (CHANNEL_MAIN, CHANNEL_SUB):
            cap = None
            try:
                url = build_rtsp_url(channel)
                cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
                try:
                    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000)
                    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass
                if cap is None or not cap.isOpened():
                    try: cap.release()
                    except Exception: pass
                    continue
                ok, test_frame = cap.read()
                if ok and test_frame is not None and getattr(test_frame, "size", 0) > 0:
                    return cap
                try: cap.release()
                except Exception: pass
            except Exception:
                try:
                    if cap is not None:
                        cap.release()
                except Exception:
                    pass
        return None

    def _show_camera_failed_warning(self, title="Camera connection failed", extra=""):
        """Show one warning and make sure the AR tab remains usable."""
        try:
            self._camera_enabled = False
            self._cam_active = False
            self._camera_connecting = False
            self.btn_camera.config(text="Camera OFF", bg="#64748b", state="normal")
        except Exception:
            pass
        msg = (
            "The RTSP camera is not connected, timed out, or the IP / user / password / channel is wrong.\n\n"
            "Camera activation was stopped so the AR display stays usable with the local image/fallback background.\n"
            "Open 'RTSP Settings' and try Camera ON again."
        )
        if extra:
            msg += "\n\n" + str(extra)
        try:
            messagebox.showwarning(title, msg)
        except Exception:
            pass

    def _open_camera_capture_async(self):
        """Open RTSP in a background thread so OpenCV/FFmpeg timeout cannot freeze Tk."""
        token = getattr(self, "_camera_connect_token", 0) + 1
        self._camera_connect_token = token
        self._camera_connecting = True
        self._camera_enabled = True
        self._cam_active = False
        try:
            self.btn_camera.config(text="Connecting...", bg="#f59e0b", state="disabled")
        except Exception:
            pass

        def worker(my_token):
            cap = self._try_open_camera_capture_once()
            def finish():
                if my_token != getattr(self, "_camera_connect_token", None) or not getattr(self, "_camera_enabled", False):
                    try:
                        if cap is not None:
                            cap.release()
                    except Exception:
                        pass
                    return
                self._camera_connecting = False
                if cap is not None:
                    self._cam = cap
                    self._cam_active = True
                    try:
                        self.btn_camera.config(text="Camera ON", bg=THEME.ok, state="normal")
                    except Exception:
                        pass
                else:
                    self._show_camera_failed_warning()
            try:
                self.after(0, finish)
            except Exception:
                try:
                    if cap is not None:
                        cap.release()
                except Exception:
                    pass

        threading.Thread(target=worker, args=(token,), daemon=True).start()

        def timeout_check(my_token):
            if my_token == getattr(self, "_camera_connect_token", None) and getattr(self, "_camera_connecting", False):
                # Do not wait for OpenCV's ~30 s timeout. Leave the worker daemon alone and keep UI responsive.
                self._camera_connect_token += 1
                self._show_camera_failed_warning(
                    title="Camera connection timeout",
                    extra="OpenCV/FFmpeg did not return quickly. This prevents the 30-second freeze such as: Stream timeout triggered."
                )
        try:
            self.after(5000, lambda t=token: timeout_check(t))
        except Exception:
            pass

    def _start_camera_stream(self):
        if getattr(self, "_camera_connecting", False):
            return
        self._open_camera_capture_async()

    def _stop_camera_stream(self):
        self._camera_connect_token = getattr(self, "_camera_connect_token", 0) + 1
        self._camera_connecting = False
        try:
            if getattr(self, "_cam", None) is not None:
                self._cam.release()
        except Exception:
            pass
        self._cam = None
        self._cam_active = False
        self._camera_enabled = False
        try:
            self.btn_camera.config(text="Camera OFF", bg="#64748b", state="normal")
        except Exception:
            pass

    def toggle_camera(self):
        if getattr(self, "_camera_enabled", False) or getattr(self, "_cam_active", False) or getattr(self, "_camera_connecting", False):
            self._stop_camera_stream()
        else:
            self._start_camera_stream()
        self._redraw(self.canvas.winfo_width() or 1280, self.canvas.winfo_height() or 720)

    def open_rtsp_settings(self):
        win = tk.Toplevel(self)
        win.title("RTSP Camera Settings")
        win.configure(bg=THEME.dark_bg)
        win.geometry("460x330")
        fields = {
            "ip": CAM_IP,
            "port": globals().get("RTSP_PORT", "554"),
            "username": USERNAME,
            "password": PASSWORD,
            "channel_main": CHANNEL_MAIN,
            "channel_sub": CHANNEL_SUB,
        }
        entries = {}
        for r, (key, val) in enumerate(fields.items()):
            tk.Label(win, text=key, bg=THEME.dark_bg, fg=THEME.text, font=("Segoe UI", 10, "bold")).grid(row=r, column=0, sticky="w", padx=12, pady=8)
            e = tk.Entry(win, width=34, show=("*" if key == "password" else ""))
            e.insert(0, str(val))
            e.grid(row=r, column=1, sticky="ew", padx=12, pady=8)
            entries[key] = e
        win.grid_columnconfigure(1, weight=1)

        def save_and_apply():
            global CAM_IP, USERNAME, PASSWORD, CHANNEL_MAIN, CHANNEL_SUB, RTSP_PORT, RTSP_CAMERA_CONFIG
            cfg = {k: entries[k].get().strip() for k in entries}
            CAM_IP = cfg["ip"] or CAM_IP
            RTSP_PORT = cfg["port"] or "554"
            USERNAME = cfg["username"]
            PASSWORD = cfg["password"]
            CHANNEL_MAIN = cfg["channel_main"] or "102"
            CHANNEL_SUB = cfg["channel_sub"] or CHANNEL_MAIN
            RTSP_CAMERA_CONFIG = cfg
            save_json_safely(RTSP_CONFIG_PATH, cfg)
            was_on = getattr(self, "_camera_enabled", False)
            self._stop_camera_stream()
            if was_on:
                self._start_camera_stream()
            messagebox.showinfo("RTSP", "Camera settings saved and applied.")
            win.destroy()

        tk.Button(win, text="Save / Apply", bg=THEME.ok, fg="white", relief="flat", command=save_and_apply, padx=14, pady=8).grid(row=7, column=0, columnspan=2, pady=16)

    def _show_tab2_info(self):
        anns = []
        anns.append((getattr(self, "btn_gen", None), "Generator subsection. Loads and displays three selected parameters for the generator AR view.", "left"))
        anns.append((getattr(self, "btn_turb", None), "Turbine subsection. Same three-card AR logic, separated from Generator data.", "left"))
        anns.append((getattr(self, "btn_ae", None), "AE Sensors subsection. JSON folder loading prioritizes Acceleration, Gyroscope, then Magnetometer when available.", "left"))
        anns.append((getattr(self, "btn_digital_twin", None), "Digital Twin subsection. Works the same as the other AR subsections and keeps its own JSON data.", "left"))
        anns.append((getattr(self, "btn_load_tab2_json", None), "Load JSON Folder for the currently selected Tab 2 subsection only. It scans many JSON files and picks up to 3 distinct parameter names.", "right"))
        anns.append((getattr(self, "btn_camera", None), "Camera ON/OFF. RTSP starts only when requested. If the camera is missing or times out, a warning popup appears and the GUI continues working.", "right"))
        anns.append((getattr(self, "btn_rtsp", None), "RTSP Settings. Change camera IP, username, password, and channel without editing the code.", "right"))
        anns.append((getattr(self, "btn_mqtt", None), "MQTT / Mosquitto control window. Opens PowerShell commands for broker/subscriber workflows.", "right"))
        if getattr(self, "cards", None):
            anns.append((self.cards[0], "Floating AR parameter card. Shows detected name, current value, unit, status, and warning state.", "right"))
            if len(self.cards) > 1:
                anns.append((self.cards[1], "Each AR card receives one distinct parameter. If fewer than 3 are found, remaining cards stay blank.", "left"))
        show_guided_help_overlay(
            self,
            "Quick Guide - Tab 2 AR Display / JSON Sensor Folders",
            "Three floating AR sections per subsection. JSON folders are loaded per subsection and do not change Tab 1.",
            anns,
        )

    def open_mqtt_window(self):
        MosquittoControlWindow(self)

    def _render_background(self, w, h):
        """Render the live RTSP stream if available, otherwise an image asset or fallback."""
        w = max(1, int(w))
        h = max(1, int(h))

        frame_img = None
        if getattr(self, "_cam_active", False) and getattr(self, "_cam", None) is not None:
            try:
                ok, frame = self._cam.read()
            except Exception:
                ok, frame = False, None

            if ok and frame is not None and getattr(frame, "size", 0) > 0:
                try:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame_img = Image.fromarray(frame).resize((w, h), Image.LANCZOS)
                except Exception:
                    frame_img = None
            else:
                try:
                    self._cam.release()
                except Exception:
                    pass
                self._cam = None
                self._cam_active = False
                if getattr(self, "_camera_enabled", False):
                    self._camera_enabled = False
                    self.after(0, lambda: self._show_camera_failed_warning(
                        title="Camera stream stopped",
                        extra="The RTSP stream stopped responding or OpenCV/FFmpeg reported a stream timeout."
                    ))

        if frame_img is None:
            if self.current_mode == "generator":
                bg_name = "generator.jpg"
            elif self.current_mode == "turbine":
                bg_name = "Turbine.JPG"
            elif self.current_mode == "ae":
                bg_name = "aesensors.jpg"
            elif self.current_mode == "digital_twin":
                bg_name = "digitaltwin.jpg"
            else:
                bg_name = "generator.jpg"

            bg = self._find(bg_name)
            if bg and os.path.exists(bg):
                try:
                    img = Image.open(bg).convert("RGB").resize((w, h), Image.LANCZOS)
                    frame_img = img
                except Exception:
                    frame_img = None

        if frame_img is None:
            self._cam_photo = self._draw_placeholder_background(
                w,
                h,
                tick=self._mode_ticks.get(self.current_mode or "generator", 0)
            )
        else:
            self._cam_photo = ImageTk.PhotoImage(frame_img)

        if getattr(self, "_bg_item", None) is None:
            self._bg_item = self.canvas.create_image(0, 0, anchor="nw", image=self._cam_photo, tags=("bg",))
        else:
            self.canvas.itemconfigure(self._bg_item, image=self._cam_photo)
        self.canvas.tag_lower(self._bg_item)
    def _camera_loop(self):
        if not getattr(self, "_alive", True):
            return
        try:
            if self.winfo_exists():
                self._render_background(self.canvas.winfo_width() or 1280, self.canvas.winfo_height() or 720)
        except Exception:
            pass
        try:
            self._cam_after_id = self.after(33, self._camera_loop)
        except Exception:
            self._cam_after_id = None

    def _on_resize(self, event):
        self._redraw(event.width, event.height)

    def _overlay_dimensions(self, w, h):
        card_w = int(w * self.CARD_WIDTH_RATIO)
        card_h = int(h * self.CARD_HEIGHT_RATIO)
        card_w = max(self.CARD_MIN_W, min(self.CARD_MAX_W, card_w))
        card_h = max(self.CARD_MIN_H, min(self.CARD_MAX_H, card_h))
        return card_w, card_h

    def _redraw(self, w, h):
        if self.current_mode == "generator":
            bg_name = "generator.jpg"
        elif self.current_mode == "turbine":
            bg_name = "Turbine.JPG"
        elif self.current_mode == "ae":
            bg_name = "aesensors.jpg"
        else:
            bg_name = "generator.jpg"

        self._render_background(w, h)

        card_w, card_h = self._overlay_dimensions(w, h)
        positions = self.FLOATING_POSITIONS

        for wid in self._wins:
            if wid is not None:
                self.canvas.delete(wid)

        for i in range(3):
            relx, rely = positions[i]
            x = int(w * relx)
            y = int(h * rely)
            self._wins[i] = self.canvas.create_window(
                x, y,
                anchor="center",
                window=self.cards[i],
                width=card_w,
                height=card_h,
            )
            code = (self.selected.get(self.current_mode) or [None, None, None])[i]
            if code:
                self.cards[i].set_param_code(code)

    def _load_tab2_json_for_current_mode(self):
        """Load a folder of partner JSON snapshot files only into the active Tab 2 subsection/mode.

        Each JSON file may contain one parameter value or a list/container of records.
        The loader groups records by JSON category, pivots them as Timestamp + parameter columns,
        then plays each detected parameter from first timestamp to last timestamp in the AR boxes.
        """
        mode = self.current_mode or "generator"
        if mode not in ("generator", "turbine", "ae", "digital_twin"):
            mode = "generator"
        from tkinter import filedialog, messagebox, simpledialog

        folder = filedialog.askdirectory(title=f"Select folder with JSON files for Tab 2 / {mode.title()}")
        if not folder:
            return

        try:
            frames = _load_partner_json_folder(folder)
            if not frames:
                messagebox.showerror("JSON folder load", "No valid JSON parameter records were found in the selected folder.")
                return

            cat_names = list(frames.keys())
            unique_cols, series_map, times_map, category_map = _collect_json_parameter_series(frames)

            if not unique_cols:
                messagebox.showerror("JSON folder load", "No numeric measurement values were found in the selected JSON folder.")
                return

            seen = set()
            deduped = []
            for c in unique_cols:
                if c not in seen:
                    seen.add(c)
                    deduped.append(c)
            unique_cols = deduped

            chosen = []
            used = set()
            available_txt = ", ".join(unique_cols)
            for slot in range(3):
                if len(unique_cols) <= slot:
                    chosen.append(None)
                    continue
                default = next((c for c in unique_cols if c not in used), unique_cols[slot])
                val = simpledialog.askstring(
                    "Select JSON parameter",
                    f"Select different parameter for AR section {slot+1}.\n\nRecommended order is acceleration, gyroscope/angular velocity, then magnetometer/magnetic field.\n\nAvailable parameters:\n{available_txt}",
                    initialvalue=default,
                )
                if not val:
                    chosen.append(None)
                    continue
                val = val.strip()
                if val not in unique_cols:
                    messagebox.showwarning("Invalid parameter", f"'{val}' was not found. Section {slot+1} will remain blank.")
                    chosen.append(None)
                    continue
                if val in used:
                    messagebox.showwarning("Duplicate parameter", f"'{val}' was already selected. Section {slot+1} will remain blank.")
                    chosen.append(None)
                    continue
                chosen.append(val)
                used.add(val)

            self._tab2_json_cols[mode] = unique_cols
            self._tab2_json_series_map[mode] = series_map
            self._tab2_json_times_map[mode] = times_map
            self._tab2_json_series[mode] = [list(series_map[c]) if c else [] for c in chosen]
            self._tab2_json_indices[mode] = [0, 0, 0]
            self.selected[mode] = chosen[:]
            self.histories = [[], [], []]

            for i, col in enumerate(chosen):
                try:
                    self.cards[i].set_param_code(col)
                except Exception:
                    pass

            self._redraw(self.canvas.winfo_width() or 1280, self.canvas.winfo_height() or 720)
            shown = [c for c in chosen if c]
            blanks = 3 - len(shown)
            messagebox.showinfo(
                "Tab 2 JSON folder loaded",
                f"Loaded {len(unique_cols)} distinct parameter(s) from categories: {', '.join(cat_names)} into {mode.title()}.\n"
                f"Displaying: {', '.join(shown) if shown else 'none'}"
                + (f"\nBlank sections: {blanks}" if blanks else "")
                + "\n\nPlayback runs through the folder values from first to last, then repeats."
            )
        except Exception as e:
            messagebox.showerror("JSON folder load", f"Failed to load JSON folder for Tab 2:\n{e}")

    def _choose_tab2_json_column(self, slot: int):
        mode = self.current_mode or "generator"
        from tkinter import messagebox, simpledialog
        cols = (getattr(self, "_tab2_json_cols", {}) or {}).get(mode, []) or []
        if not cols:
            messagebox.showerror("Tab 2 JSON", f"No JSON data loaded for {mode.title()}. Use 'Load JSON Folder for Tab 2' first.")
            return False
        available = ", ".join(cols)
        initial = cols[min(slot, len(cols)-1)]
        col = simpledialog.askstring("Select Tab 2 JSON Parameter", f"Enter parameter for P{slot+1}\nAvailable: {available}", initialvalue=initial)
        if not col:
            return True
        if col not in cols:
            messagebox.showerror("Invalid parameter", f"'{col}' was not found. Available: {available}")
            return True
        series = ((getattr(self, "_tab2_json_series_map", {}) or {}).get(mode, {}) or {}).get(col, [])
        if not series:
            messagebox.showerror("Empty parameter", f"No numeric data found in '{col}'.")
            return True
        self._tab2_json_series[mode][slot] = list(series)
        self._tab2_json_indices[mode][slot] = 0
        sel = self.selected.get(mode) or [None, None, None]
        sel[slot] = col
        self.selected[mode] = sel
        try:
            self.cards[slot].set_param_code(col)
        except Exception:
            pass
        self._redraw(self.canvas.winfo_width() or 1280, self.canvas.winfo_height() or 720)
        return True

    def open_selector(self, slot: int = 0):
        mode = self.current_mode or "generator"
        if (getattr(self, "_tab2_json_cols", {}) or {}).get(mode):
            if self._choose_tab2_json_column(slot):
                return
        groups = GENERATOR_GROUPS if mode == "generator" else TURBINE_GROUPS
        if not groups:
            groups = ALL_GROUPS
        def on_pick(group_name, code):
            sel = self.selected.get(mode) or [None, None, None]
            sel[slot] = code
            self.selected[mode] = sel
            try:
                self.cards[slot].set_param_code(code)
            except Exception:
                pass
            self._redraw(self.canvas.winfo_width() or 1280, self.canvas.winfo_height() or 720)
        ARParamSelectDialog(self, f"Select {mode.title()} Parameter", groups, on_pick)

    def _ensure_water_autoload(self):
        if getattr(self, "_water_cols", None) and any(getattr(self, "_water_series", [])):
            return
        import os, pandas as pd
        try:
            here = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            here = os.getcwd()
        candidates = [
            os.path.join(here, "data", "water_quality_900s_6params.xlsx"),
            os.path.join(here, "data", "data", "water_quality_900s_6params.xlsx"),
            os.path.join(os.getcwd(), "data", "water_quality_900s_6params.xlsx"),
            os.path.join(os.getcwd(), "data", "data", "water_quality_900s_6params.xlsx"),
            os.path.join(here, "water_quality_900s_6params.xlsx"),
            os.path.join(os.getcwd(), "water_quality_900s_6params.xlsx"),
        ]
        df = None
        used_path = None
        for path in candidates:
            if os.path.isfile(path):
                try:
                    df = list(pd.read_excel(path, sheet_name=None).values())[0]
                    used_path = path
                    break
                except Exception as e:
                    print("Failed to read", path, ":", e)
        if df is None:
            print("No water dataset found. Tried:", candidates)
            return
        ts_col = None
        for c in df.columns:
            cl = str(c).lower()
            if "time" in cl or "date" in cl or "timestamp" in cl:
                try:
                    df[c] = pd.to_datetime(df[c], errors="coerce")
                    if df[c].notna().any():
                        ts_col = c
                        break
                except Exception:
                    pass
        if ts_col is None:
            c0 = df.columns[0]
            try:
                df[c0] = pd.to_datetime(df[c0], errors="coerce")
                if df[c0].notna().any():
                    ts_col = c0
            except Exception:
                pass
        num_cols = []
        for c in df.columns:
            if c == ts_col:
                continue
            s = pd.to_numeric(df[c], errors="coerce")
            if s.notna().sum() > 0:
                num_cols.append(str(c))
        if not num_cols:
            print("No numeric columns found in water dataset:", used_path)
            return
        self._water_series_map = {str(c): pd.to_numeric(df[c], errors="coerce").dropna().tolist() for c in num_cols}
        self._water_cols = num_cols
        chosen = (num_cols * 3)[:3]
        self._water_series = [self._water_series_map[c][:] for c in chosen]
        self._water_indices = [0, 0, 0]
        self.selected["water"] = chosen
        for i, c in enumerate(chosen):
            try:
                self.cards[i].set_param_code(c)
            except Exception:
                pass
        print("Water auto-loaded from:", used_path, "columns:", chosen)

    def _choose_water_column(self, slot: int):
        from tkinter import messagebox, simpledialog
        try:
            self._ensure_water_autoload()
        except Exception as _e:
            print("Autoload failed:", _e)
        cols = getattr(self, "_water_cols", []) or []
        if not cols:
            try:
                messagebox.showerror("Water", "No water dataset available.")
            except Exception:
                pass
            return
        available = ", ".join(cols)
        initial = cols[min(slot, len(cols) - 1)]
        col = simpledialog.askstring("Select Water Column", f"Enter a column for P{slot+1}\nAvailable: {available}", initialvalue=initial)
        if not col:
            return
        if col not in cols:
            try:
                messagebox.showerror("Invalid column", f"'{col}' was not found. Available: {available}")
            except Exception:
                pass
            return
        series = (getattr(self, "_water_series_map", {}) or {}).get(col, [])
        if not series:
            try:
                messagebox.showerror("Empty column", f"No numeric data found in '{col}'.")
            except Exception:
                pass
            return
        self._water_series[slot] = list(series)
        self._water_indices[slot] = 0
        sel = self.selected.get("water") or [None, None, None]
        sel[slot] = col
        self.selected["water"] = sel
        try:
            self.cards[slot].set_param_code(col)
        except Exception:
            pass
        self._redraw(self.canvas.winfo_width() or 1280, self.canvas.winfo_height() or 720)

    def _ensure_river_autoload(self):
        if getattr(self, "_river_cols", None) and any(getattr(self, "_river_series", [])):
            return
        import os, pandas as pd
        try:
            here = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            here = os.getcwd()
        candidates = [
            os.path.join(here, "data", "river_params_900s.xlsx"),
            os.path.join(here, "data", "data", "river_params_900s.xlsx"),
            os.path.join(os.getcwd(), "data", "river_params_900s.xlsx"),
            os.path.join(os.getcwd(), "data", "data", "river_params_900s.xlsx"),
        ]
        df = None
        used_path = None
        for path in candidates:
            if os.path.isfile(path):
                try:
                    df = list(pd.read_excel(path, sheet_name=None).values())[0]
                    used_path = path
                    break
                except Exception as e:
                    print("Failed to read", path, ":", e)
        if df is None:
            print("No river dataset found. Tried:", candidates)
            return
        ts_col = None
        for c in df.columns:
            cl = str(c).lower()
            if "time" in cl or "date" in cl or "timestamp" in cl:
                try:
                    df[c] = pd.to_datetime(df[c], errors="coerce")
                    if df[c].notna().any():
                        ts_col = c
                        break
                except Exception:
                    pass
        if ts_col is None:
            c0 = df.columns[0]
            try:
                df[c0] = pd.to_datetime(df[c0], errors="coerce")
                if df[c0].notna().any():
                    ts_col = c0
            except Exception:
                pass
        num_cols = []
        for c in df.columns:
            if c == ts_col:
                continue
            s = pd.to_numeric(df[c], errors="coerce")
            if s.notna().sum() > 0:
                num_cols.append(str(c))
        if not num_cols:
            print("No numeric columns found in river dataset:", used_path)
            return
        self._river_series_map = {str(c): pd.to_numeric(df[c], errors="coerce").dropna().tolist() for c in num_cols}
        self._river_cols = num_cols
        chosen = (num_cols * 3)[:3]
        self._river_series = [self._river_series_map[c][:] for c in chosen]
        self._river_indices = [0, 0, 0]
        self.selected["river"] = chosen
        for i, c in enumerate(chosen):
            try:
                self.cards[i].set_param_code(c)
            except Exception:
                pass
        print("River auto-loaded from:", used_path, "columns:", chosen)

    def _ensure_ae_autoload(self):
        if getattr(self, "_ae_cols", None) and any(getattr(self, "_ae_series", [])):
            return
        import os, pandas as pd
        try:
            here = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            here = os.getcwd()
        candidates = [
            os.path.join(here, "data", "ae_sensors_900s.xlsx"),
            os.path.join(here, "data", "data", "ae_sensors_900s.xlsx"),
            os.path.join(os.getcwd(), "data", "ae_sensors_900s.xlsx"),
            os.path.join(os.getcwd(), "data", "data", "ae_sensors_900s.xlsx"),
        ]
        df = None
        used_path = None
        for path in candidates:
            if os.path.isfile(path):
                try:
                    df = list(pd.read_excel(path, sheet_name=None).values())[0]
                    used_path = path
                    break
                except Exception as e:
                    print("Failed to read", path, ":", e)
        if df is None:
            print("No ae dataset found. Tried:", candidates)
            return
        ts_col = None
        for c in df.columns:
            cl = str(c).lower()
            if "time" in cl or "date" in cl or "timestamp" in cl:
                try:
                    df[c] = pd.to_datetime(df[c], errors="coerce")
                    if df[c].notna().any():
                        ts_col = c
                        break
                except Exception:
                    pass
        if ts_col is None:
            c0 = df.columns[0]
            try:
                df[c0] = pd.to_datetime(df[c0], errors="coerce")
                if df[c0].notna().any():
                    ts_col = c0
            except Exception:
                pass
        num_cols = []
        for c in df.columns:
            if c == ts_col:
                continue
            s = pd.to_numeric(df[c], errors="coerce")
            if s.notna().sum() > 0:
                num_cols.append(str(c))
        if not num_cols:
            print("No numeric columns found in ae dataset:", used_path)
            return
        self._ae_series_map = {str(c): pd.to_numeric(df[c], errors="coerce").dropna().tolist() for c in num_cols}
        self._ae_cols = num_cols
        chosen = (num_cols * 3)[:3]
        self._ae_series = [self._ae_series_map[c][:] for c in chosen]
        self._ae_indices = [0, 0, 0]
        self.selected["ae"] = chosen
        for i, c in enumerate(chosen):
            try:
                self.cards[i].set_param_code(c)
            except Exception:
                pass
        print("Ae auto-loaded from:", used_path, "columns:", chosen)

    def _choose_river_column(self, slot: int):
        from tkinter import messagebox, simpledialog
        try:
            self._ensure_river_autoload()
        except Exception as _e:
            print("river autoload failed:", _e)
        cols = getattr(self, "_river_cols", []) or []
        if not cols:
            try:
                messagebox.showerror("RIVER", "No river dataset available.")
            except Exception:
                pass
            return
        available = ", ".join(cols)
        initial = cols[min(slot, len(cols) - 1)]
        col = simpledialog.askstring("Select River Column", f"Enter a column for P{slot+1}\nAvailable: {available}", initialvalue=initial)
        if not col:
            return
        if col not in cols:
            try:
                messagebox.showerror("Invalid column", f"'{col}' was not found. Available: {available}")
            except Exception:
                pass
            return
        series = (getattr(self, "_river_series_map", {}) or {}).get(col, [])
        if not series:
            try:
                messagebox.showerror("Empty column", f"No numeric data found in '{col}'.")
            except Exception:
                pass
            return
        self._river_series[slot] = list(series)
        self._river_indices[slot] = 0
        sel = self.selected.get("river") or [None, None, None]
        sel[slot] = col
        self.selected["river"] = sel
        try:
            self.cards[slot].set_param_code(col)
        except Exception:
            pass
        self._redraw(self.canvas.winfo_width() or 1280, self.canvas.winfo_height() or 720)

    def _choose_ae_column(self, slot: int):
        from tkinter import messagebox, simpledialog
        try:
            self._ensure_ae_autoload()
        except Exception as _e:
            print("ae autoload failed:", _e)
        cols = getattr(self, "_ae_cols", []) or []
        if not cols:
            try:
                messagebox.showerror("AE", "No ae dataset available.")
            except Exception:
                pass
            return
        available = ", ".join(cols)
        initial = cols[min(slot, len(cols) - 1)]
        col = simpledialog.askstring("Select Ae Column", f"Enter a column for P{slot+1}\nAvailable: {available}", initialvalue=initial)
        if not col:
            return
        if col not in cols:
            try:
                messagebox.showerror("Invalid column", f"'{col}' was not found. Available: {available}")
            except Exception:
                pass
            return
        series = (getattr(self, "_ae_series_map", {}) or {}).get(col, [])
        if not series:
            try:
                messagebox.showerror("Empty column", f"No numeric data found in '{col}'.")
            except Exception:
                pass
            return
        self._ae_series[slot] = list(series)
        self._ae_indices[slot] = 0
        sel = self.selected.get("ae") or [None, None, None]
        sel[slot] = col
        self.selected["ae"] = sel
        try:
            self.cards[slot].set_param_code(col)
        except Exception:
            pass
        self._redraw(self.canvas.winfo_width() or 1280, self.canvas.winfo_height() or 720)

    def switch_mode(self, mode):
        self.current_mode = mode
        try:
            self.btn_gen.config(bg=(THEME.ok if mode == "generator" else "#2563eb"))
            self.btn_turb.config(bg=(THEME.ok if mode == "turbine" else "#2563eb"))
            self.btn_ae.config(bg=(THEME.ok if mode == "ae" else "#2563eb"))
            self.btn_digital_twin.config(bg=(THEME.ok if mode == "digital_twin" else "#2563eb"))
        except Exception:
            pass
        self.histories = [[], [], []]
        if mode == "ae":
            try:
                self._ensure_ae_autoload()
            except Exception as _e:
                print("AE autoload error:", _e)
        self._redraw(self.winfo_width() or 1280, self.winfo_height() or 720)

    def _synthetic_value(self, code, slot, tick, mode):
        import math
        code = code or f"{mode}_{slot}"
        seed = sum(ord(ch) for ch in str(code)) + slot * 37 + sum(ord(ch) for ch in str(mode)) * 3
        base = 10.0 + (seed % 55) * 0.35
        amp = 0.8 + (seed % 17) * 0.05
        freq = 0.08 + (seed % 9) * 0.01
        phase = (seed % 360) * math.pi / 180.0
        return base + amp * math.sin(tick * freq + phase) + 0.22 * math.sin(tick * freq * 0.37 + phase * 0.7)

    def _tick(self):
        """Advance one step per second for the current mode."""
        if not getattr(self, "_alive", True):
            return
        try:
            mode = self.current_mode or "generator"
            json_series_by_mode = getattr(self, "_tab2_json_series", {}) or {}
            json_indices_by_mode = getattr(self, "_tab2_json_indices", {}) or {}
            json_loaded_for_mode = bool((getattr(self, "_tab2_json_cols", {}) or {}).get(mode))
            if json_loaded_for_mode:
                series_list = json_series_by_mode.get(mode, [[], [], []])
                indices = json_indices_by_mode.get(mode, [0, 0, 0])
            elif mode == "ae" and any(len(s) for s in getattr(self, "_ae_series", [[], [], []])):
                series_list = self._ae_series
                indices = self._ae_indices
            else:
                series_list = None
                indices = None

            t = self._mode_ticks.get(mode, 0)
            sel = self.selected.get(mode) or [None, None, None]
            for i in range(3):
                if series_list is not None and i < len(series_list) and series_list[i]:
                    idx = indices[i] % len(series_list[i])
                    v = series_list[i][idx]
                    indices[i] = (idx + 1) % len(series_list[i])
                    self.cards[i].push(v)
                elif json_loaded_for_mode:
                    continue
                else:
                    v = self._synthetic_value(sel[i], i, t, mode)
                    self.cards[i].push(v)

            self._mode_ticks[mode] = t + 1

        except Exception as e:
            try:
                print("Tick error:", e)
            except Exception:
                pass
        if getattr(self, "_alive", True):
            try:
                self._tick_id = self.after(1000, self._tick)
            except Exception:
                pass

    def prepare_to_quit(self):
        try:
            self._alive = False
        except Exception:
            pass
        try:
            if self._tick_id is not None:
                self.after_cancel(self._tick_id)
        except Exception:
            pass
        self._tick_id = None
        try:
            self._stop_camera_stream()
        except Exception:
            pass


class MosquittoControlWindow(tk.Toplevel):
    """Small operator window for Mosquitto + partner JSON subscription."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Mosquitto / Partner JSON Subscriber")
        self.configure(bg=THEME.dark_bg)
        self.geometry("980x620")
        self._procs = []
        cfg = MQTT_PARTNER_CONFIG or {}
        defaults = {
            "mosquitto_exe": cfg.get("mosquitto_exe", r"C:\Program Files\mosquitto\mosquitto.exe"),
            "mosquitto_conf": cfg.get("mosquitto_conf", ""),
            "broker_ip": cfg.get("broker_ip", "127.0.0.1"),
            "port": cfg.get("port", "1883"),
            "topic": cfg.get("topic", "#"),
            "username": cfg.get("username", ""),
            "password": cfg.get("password", ""),
            "save_folder": cfg.get("save_folder", os.path.join(os.path.dirname(ROOT_DIR), "data", "json_partners")),
        }
        self.entries = {}
        labels = [
            ("mosquitto_exe", "Mosquitto EXE"), ("mosquitto_conf", "mosquitto.conf optional"),
            ("broker_ip", "Broker IP"), ("port", "Port"), ("topic", "Topic"),
            ("username", "Username optional"), ("password", "Password optional"), ("save_folder", "Save JSON folder"),
        ]
        form = tk.Frame(self, bg=THEME.dark_bg); form.pack(fill=tk.X, padx=12, pady=10)
        for r, (key, label) in enumerate(labels):
            tk.Label(form, text=label, bg=THEME.dark_bg, fg=THEME.text, font=("Segoe UI", 10, "bold")).grid(row=r, column=0, sticky="w", pady=4)
            e = tk.Entry(form, width=90, show=("*" if key == "password" else ""))
            e.insert(0, defaults[key])
            e.grid(row=r, column=1, sticky="ew", padx=8, pady=4)
            self.entries[key] = e
        form.grid_columnconfigure(1, weight=1)

        btns = tk.Frame(self, bg=THEME.dark_bg); btns.pack(fill=tk.X, padx=12, pady=(0, 8))
        tk.Button(btns, text="Run Mosquitto", bg=THEME.ok, fg="white", relief="flat", padx=12, pady=6, command=self.run_mosquitto).pack(side=tk.LEFT, padx=4)
        tk.Button(btns, text="Subscribe", bg="#0ea5e9", fg="white", relief="flat", padx=12, pady=6, command=self.subscribe).pack(side=tk.LEFT, padx=4)
        tk.Button(btns, text="Save Config", bg="#64748b", fg="white", relief="flat", padx=12, pady=6, command=self.save_config).pack(side=tk.LEFT, padx=4)
        tk.Button(btns, text="Stop Processes", bg=THEME.alert, fg="white", relief="flat", padx=12, pady=6, command=self.stop_all).pack(side=tk.LEFT, padx=4)
        tk.Button(btns, text="Open Save Folder", bg="#475569", fg="white", relief="flat", padx=12, pady=6, command=self.open_save_folder).pack(side=tk.LEFT, padx=4)

        self.output = tk.Text(self, bg="#020617", fg="#e5e7eb", insertbackground="#e5e7eb", height=22, wrap="word")
        self.output.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._write("Ready. Use Run Mosquitto for a local broker, then Subscribe to save incoming JSON messages.\n")

    def _cfg(self):
        return {k: e.get().strip() for k, e in self.entries.items()}

    def _write(self, text):
        try:
            self.output.insert(tk.END, text)
            self.output.see(tk.END)
        except Exception:
            pass

    def _reader(self, proc, tag=""):
        try:
            for line in iter(proc.stdout.readline, ''):
                if not line:
                    break
                self.after(0, self._write, f"[{tag}] {line}")
        except Exception as e:
            self.after(0, self._write, f"[{tag}] reader stopped: {e}\n")

    def _spawn(self, args, tag):
        self._write(f"Running: {' '.join(args)}\n")
        try:
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            self._procs.append(proc)
            threading.Thread(target=self._reader, args=(proc, tag), daemon=True).start()
            return proc
        except Exception as e:
            messagebox.showerror(tag, f"Failed to start:\n{e}")
            self._write(f"[{tag}] ERROR: {e}\n")
            return None

    def run_mosquitto(self):
        cfg = self._cfg(); exe = cfg["mosquitto_exe"] or "mosquitto"
        args = [exe]
        if cfg.get("mosquitto_conf"):
            args += ["-c", cfg["mosquitto_conf"]]
        self._spawn(args, "mosquitto")

    def subscribe(self):
        cfg = self._cfg()
        os.makedirs(cfg["save_folder"] or ".", exist_ok=True)
        sub_exe = os.path.join(os.path.dirname(cfg["mosquitto_exe"]), "mosquitto_sub.exe") if cfg.get("mosquitto_exe") else "mosquitto_sub"
        if not os.path.exists(sub_exe):
            sub_exe = "mosquitto_sub"
        auth = []
        if cfg.get("username"):
            auth += ["-u", cfg["username"]]
        if cfg.get("password"):
            auth += ["-P", cfg["password"]]
        args = [sub_exe, "-h", cfg.get("broker_ip") or "127.0.0.1", "-p", cfg.get("port") or "1883", "-t", cfg.get("topic") or "#", "-v"] + auth
        proc = self._spawn(args, "subscribe")
        if proc:
            save_args = args[:]
            try:
                save_proc = subprocess.Popen(save_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                self._procs.append(save_proc)
                threading.Thread(target=self._save_reader, args=(save_proc, cfg["save_folder"]), daemon=True).start()
            except Exception as e:
                self._write(f"[save] ERROR: {e}\n")

    def _save_reader(self, proc, folder):
        import datetime
        for line in iter(proc.stdout.readline, ''):
            msg = line.strip()
            if not msg:
                continue
            payload = msg
            first_brace = msg.find('{')
            if first_brace >= 0:
                payload = msg[first_brace:]
            if payload.startswith('{') or payload.startswith('['):
                stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                path = os.path.join(folder, f"partner_{stamp}.json")
                try:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(payload)
                    self.after(0, self._write, f"[save] {path}\n")
                except Exception as e:
                    self.after(0, self._write, f"[save] ERROR: {e}\n")

    def save_config(self):
        cfg = self._cfg()
        save_json_safely(MQTT_CONFIG_PATH, cfg)
        messagebox.showinfo("MQTT", "Configuration saved.")

    def open_save_folder(self):
        folder = self._cfg().get("save_folder") or "."
        os.makedirs(folder, exist_ok=True)
        try:
            os.startfile(folder)
        except Exception as e:
            messagebox.showerror("Open folder", str(e))

    def stop_all(self):
        for proc in list(self._procs):
            try:
                proc.terminate()
            except Exception:
                pass
        self._procs.clear()
        self._write("Stopped tracked Mosquitto/subscriber processes.\n")

    def _on_close(self):
        self.stop_all()
        self.destroy()

class CombinedApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("The Di-Hydro Visualization Tool")
        self.configure(bg=THEME.dark_bg)

        style = ttk.Style()
        try: style.theme_use("clam")
        except Exception: 
            pass
        style.configure("TNotebook", background=THEME.dark_bg, borderwidth=0)
        style.configure("TNotebook.Tab", padding=[14, 8], font=("Segoe UI", 12, "bold"))
        style.map("TNotebook.Tab", background=[("selected", THEME.panel_bg)], foreground=[("selected", THEME.text)])

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        tab1 = TurbineCSVTab(nb)
        nb.add(tab1, text="Tab 1 - PPC UNIT 1")
        tab2 = ARPanelThreeRight(nb)
        nb.add(tab2, text="Tab 2 - Augmented Reality (AR)")

        self._nb = nb
        self._tab1 = tab1
        self._tab2 = tab2
        self._help_win = None

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _show_help_overlay(self):
        """Semi-transparent overlay showing a quick tutorial only for Tab 2 (AR panel)."""
        if self._help_win is not None and self._help_win.winfo_exists():
            try:
                self._help_win.lift()
            except Exception:
                pass
            return

        self.update_idletasks()
        w = max(800, self.winfo_width())
        h = max(600, self.winfo_height())
        x = self.winfo_rootx()
        y = self.winfo_rooty()

        overlay = tk.Toplevel(self)
        self._help_win = overlay
        overlay.overrideredirect(True)
        try:
            overlay.attributes("-topmost", True)
            overlay.attributes("-alpha", 0.86)
            overlay.configure(bg="#ff00ff")
            try:
                overlay.attributes("-transparentcolor", "#ff00ff")
            except Exception:
                pass
        except Exception:
            pass
        overlay.geometry(f"{w}x{h}+{x}+{y}")

        canvas = tk.Canvas(overlay, bg="#ff00ff", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_rectangle(0, 0, w, h, fill="#020617", outline="")

        def _close(event=None):
            try:
                overlay.destroy()
            except Exception:
                pass

        canvas.bind("<Button-1>", _close)
        overlay.bind("<Escape>", _close)

        canvas.create_text(
            w//2,
            30,
            text="Quick Guide - Tab 2 AR Three-Right",
            fill="#e5e7eb",
            font=("Segoe UI", 16, "bold")
        )
        canvas.create_text(
            w//2,
            60,
            text="Focus: Generator / Turbine / Water / River / AE sensors floating AR callouts over the live stream.",
            fill="#9ca3af",
            font=("Segoe UI", 11)
        )

        def widget_center(widget):
            try:
                widget.update_idletasks()
                rx = widget.winfo_rootx()
                ry = widget.winfo_rooty()
                rw = widget.winfo_width()
                rh = widget.winfo_height()
                return rx - x + rw/2, ry - y + rh/2, rw, rh
            except Exception:
                return None

        def punch_hole(widget, pad=10):
            info = widget_center(widget)
            if not info:
                return
            cx, cy, ww, hh = info
            x1 = cx - ww/2 - pad
            y1 = cy - hh/2 - pad
            x2 = cx + ww/2 + pad
            y2 = cy + hh/2 + pad
            canvas.create_rectangle(x1, y1, x2, y2, fill="#ff00ff", outline="")

        try:
            punch_hole(self._tab2.btn_gen)
            punch_hole(self._tab2.btn_turb)
            punch_hole(self._tab2.btn_water)
            punch_hole(self._tab2.btn_river)
            punch_hole(self._tab2.btn_ae)
            punch_hole(self._tab2.btn_sel_1)
            punch_hole(self._tab2.btn_sel_2)
            punch_hole(self._tab2.btn_sel_3)
        except Exception:
            pass

        left_index = 0
        right_index = 0

        def annotate(widget, text, side="left"):
            nonlocal left_index, right_index
            info = widget_center(widget)
            if info is None:
                return
            wx, wy, ww, wh = info
            margin_x = 220
            box_w = 280
            box_h = 90

            if side == "left":
                idx = left_index
                left_index += 1
            else:
                idx = right_index
                right_index += 1
            base_y = 120
            step_y = 130
            ty = base_y + idx * step_y

            if side == "left":
                tx = max(30, wx - margin_x - box_w/2)
            else:
                tx = min(w - box_w - 30, wx + margin_x - box_w/2)

            x1 = tx
            y1 = ty
            x2 = tx + box_w
            y2 = ty + box_h

            canvas.create_rectangle(
                x1, y1, x2, y2,
                fill="#111827",
                outline="#38bdf8",
                width=2
            )
            canvas.create_text(
                (x1+x2)/2,
                (y1+y2)/2,
                text=text,
                fill="#e5e7eb",
                font=("Segoe UI", 10),
                width=box_w-20
            )

            canvas.create_line(
                (x2 if side == "left" else x1),
                (y1+y2)/2,
                wx,
                wy,
                fill="#38bdf8",
                width=2,
                arrow="last"
            )

            pad = 6
            canvas.create_rectangle(
                wx - ww/2 - pad,
                wy - wh/2 - pad,
                wx + ww/2 + pad,
                wy + wh/2 + pad,
                outline="#f97316",
                width=2
            )

        tab2 = getattr(self, "_tab2", None)

        if tab2 is None:
            canvas.create_text(
                w//2,
                h//2,
                text="Tab 2 (AR panel) not initialised yet.",
                fill="#e5e7eb",
                font=("Segoe UI", 12)
            )
        else:
            if hasattr(tab2, "btn_gen"):
                annotate(
                    tab2.btn_gen,
                    "Generator mode for AR. Floating cards show generator-related parameters over the generator background.",
                    side="left"
                )
            if hasattr(tab2, "btn_turb"):
                annotate(
                    tab2.btn_turb,
                    "Turbine mode for AR. Switches the background to the turbine region and shows floating turbine parameters.",
                    side="left"
                )
            if hasattr(tab2, "btn_water"):
                annotate(
                    tab2.btn_water,
                    "Water mode: visualises water-quality parameters (pH, turbidity, temperature, etc.) in AR cards.",
                    side="right"
                )
            if hasattr(tab2, "btn_river"):
                annotate(
                    tab2.btn_river,
                    "River mode: similar to Water but using river-related datasets and background.",
                    side="right"
                )
            if hasattr(tab2, "btn_ae"):
                annotate(
                    tab2.btn_ae,
                    "AE Sensors mode: shows Acoustic Emission / advanced sensor parameters in the same AR layout.",
                    side="right"
                )
            if hasattr(tab2, "btn_sel_1"):
                annotate(
                    tab2.btn_sel_1,
                    side="right"
                )
            if hasattr(tab2, "btn_load_water"):
                annotate(
                    tab2.btn_load_water,
                    "Load custom Water Quality Excel. The app auto-detects timestamps and numeric columns for the AR cards.",
                    side="right"
                )

        close_btn = tk.Button(
            overlay,
            text="Close help",
            command=_close,
            bg="#0f172a",
            fg="white",
            relief="flat",
            padx=14,
            pady=6,
            font=("Segoe UI", 9, "bold")
        )
        canvas.create_window(
            w-110,
            h-40,
            window=close_btn
        )

    def _on_close(self):
        try:
            if self._help_win is not None and self._help_win.winfo_exists():
                self._help_win.destroy()
        except Exception:
            pass
        try:
            if hasattr(self, "_tab1") and self._tab1:
                self._tab1.prepare_to_quit()
        except Exception:
            pass
        try:
            if hasattr(self, "_tab2") and self._tab2:
                self._tab2.prepare_to_quit()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        try:
            self.quit()
        except Exception:
            pass
        os._exit(0)


if __name__ == "__main__":
    app = CombinedApp()
    app.geometry("2400x1350")
    try:
        app.state("zoomed")
    except Exception:
        pass
    app.mainloop()


try:
    cls = ARPanelThreeRight
    if not hasattr(cls, "_tick"):
        def _tick(self):
            if not getattr(self, "_alive", True): 
                return
            try:
                for i in range(3):
                    self.cards[i].push(0.0)
                self._tick_id = self.after(1000, self._tick)
            except Exception:
                pass
        ARPanelThreeRight._tick = _tick
except NameError:
    pass
