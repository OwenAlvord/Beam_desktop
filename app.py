from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

try:
    import tkintermapview
except Exception:
    tkintermapview = None


ACCENT = "#1877a7"
ACCENT_DARK = "#115b7d"
BACKGROUND = "#f3f6f8"
BORDER = "#dfe6eb"
TEXT = "#1d2a33"
MUTED = "#657681"
TRAVEL = "#4a90a4"
UNLOADING = "#e39a38"
RETURN = "#7c9db5"
WASHOUT = "#8a7eb8"


def geographic_area(corners: list[tuple[float, float]]) -> float:
    if len(corners) < 3:
        return 0.0
    radius = 6378137.0
    total = 0.0
    for index, (lat1, lon1) in enumerate(corners):
        lat2, lon2 = corners[(index + 1) % len(corners)]
        lon1_rad = math.radians(lon1)
        lon2_rad = math.radians(lon2)
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        total += (lon2_rad - lon1_rad) * (2 + math.sin(lat1_rad) + math.sin(lat2_rad))
    return radius * radius * abs(total) / 2 * 10.7639


def calculate_pour(
    area: float,
    thickness: float,
    waste: float,
    truck_capacity: float,
    one_way_travel: float,
    placement_rate: float,
    washout: float,
    arrival_minutes: int,
) -> dict:
    unwasted_volume = area * thickness / 12 / 27
    volume_with_waste = unwasted_volume * (1 + waste / 100)
    ordered_volume = math.ceil((volume_with_waste - 1e-12) * 2) / 2
    truckloads = math.ceil((ordered_volume - 1e-12) / truck_capacity)
    final_load_size = max(0.0, ordered_volume - truck_capacity * (truckloads - 1))
    full_unload_minutes = truck_capacity / placement_rate * 60
    partial_unload_minutes = final_load_size / placement_rate * 60
    round_trip_minutes = 2 * one_way_travel + full_unload_minutes + washout
    trucks_in_rotation = max(1, min(truckloads, math.ceil(round_trip_minutes / full_unload_minutes)))
    final_is_full = abs(final_load_size - truck_capacity) < 1e-9
    final_unload_minutes = full_unload_minutes if final_is_full else partial_unload_minutes
    pour_duration_minutes = (truckloads - 1) * full_unload_minutes + final_unload_minutes
    return {
        "unwasted_volume": unwasted_volume,
        "volume_with_waste": volume_with_waste,
        "ordered_volume": ordered_volume,
        "truckloads": truckloads,
        "load_sizes": [
            final_load_size if index == truckloads - 1 else truck_capacity
            for index in range(truckloads)
        ],
        "final_load_size": final_load_size,
        "full_unload_minutes": full_unload_minutes,
        "round_trip_minutes": round_trip_minutes,
        "trucks_in_rotation": trucks_in_rotation,
        "pour_duration_minutes": pour_duration_minutes,
        "finish_minutes": arrival_minutes + pour_duration_minutes,
    }


def estimate_cost(
    ordered_volume: float,
    price_per_cy: float,
    short_load_fee: float,
    final_load_size: float,
    truck_capacity: float,
) -> tuple[float, float]:
    concrete_cost = ordered_volume * price_per_cy
    fee = short_load_fee if final_load_size < truck_capacity - 1e-9 else 0.0
    return concrete_cost, fee


def format_duration(total_minutes: float) -> str:
    rounded = max(0, round(total_minutes))
    if rounded < 60:
        return f"{rounded} min"
    hours, minutes = divmod(rounded, 60)
    return f"{hours}h" if minutes == 0 else f"{hours}h {minutes}m"


def format_clock_time(total_minutes: float) -> str:
    wrapped = int(round(total_minutes)) % 1440
    if wrapped < 0:
        wrapped += 1440
    hours, minutes = divmod(wrapped, 60)
    period = "PM" if hours >= 12 else "AM"
    display_hour = hours % 12 or 12
    return f"{display_hour}:{minutes:02d} {period}"


def format_schedule_time(total_minutes: float) -> str:
    day_offset = math.floor(total_minutes / 1440)
    if day_offset == 0:
        suffix = ""
    elif day_offset == 1:
        suffix = " (+1 day)"
    elif day_offset == -1:
        suffix = " (previous day)"
    elif day_offset > 1:
        suffix = f" (+{day_offset} days)"
    else:
        suffix = f" ({day_offset} days)"
    return format_clock_time(total_minutes) + suffix


class ToolTip:
    def __init__(self, widget: tk.Misc) -> None:
        self.widget = widget
        self.text = ""
        self.tip_window: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)
        widget.bind("<FocusIn>", self.show)
        widget.bind("<FocusOut>", self.hide)

    def set_text(self, text: str) -> None:
        self.text = text

    def show(self, event=None) -> None:
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip_window,
            text=self.text,
            background="#fff7d6",
            foreground=TEXT,
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=4,
        )
        label.pack()

    def hide(self, event=None) -> None:
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


def segment_intersects(a: tuple[float, float], b: tuple[float, float],
                       c: tuple[float, float], d: tuple[float, float]) -> bool:
    def cross(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def on_segment(p, q, r):
        return (q[0] <= max(p[0], r[0]) + 1e-12 and
                q[0] >= min(p[0], r[0]) - 1e-12 and
                q[1] <= max(p[1], r[1]) + 1e-12 and
                q[1] >= min(p[1], r[1]) - 1e-12)

    ab_c = cross(a, b, c)
    ab_d = cross(a, b, d)
    cd_a = cross(c, d, a)
    cd_b = cross(c, d, b)
    if ((ab_c > 0 and ab_d < 0) or (ab_c < 0 and ab_d > 0)) and \
       ((cd_a > 0 and cd_b < 0) or (cd_a < 0 and cd_b > 0)):
        return True
    if abs(ab_c) < 1e-12 and on_segment(a, c, b):
        return True
    if abs(ab_d) < 1e-12 and on_segment(a, d, b):
        return True
    if abs(cd_a) < 1e-12 and on_segment(c, a, d):
        return True
    if abs(cd_b) < 1e-12 and on_segment(c, b, d):
        return True
    return False


def has_self_intersection(corners: list[tuple[float, float]]) -> bool:
    count = len(corners)
    if count < 4:
        return False
    for i in range(count):
        a = (corners[i][1], corners[i][0])
        b = (corners[(i + 1) % count][1], corners[(i + 1) % count][0])
        for j in range(i + 1, count):
            if j == i or (i == 0 and j == count - 1):
                continue
            c = (corners[j][1], corners[j][0])
            d = (corners[(j + 1) % count][1], corners[(j + 1) % count][0])
            if b == c or d == a:
                continue
            if segment_intersects(a, b, c, d):
                return True
    return False


class ConcretePourApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Concrete Pour Planner")
        self.geometry("1180x820")
        self.minsize(820, 620)
        self.configure(background=BACKGROUND)

        self.mode = "typed"
        self.drawing = False
        self.draft_corners: list[tuple[float, float]] = []
        self.completed_corners: list[tuple[float, float]] = []
        self.draft_markers = []
        self.completed_markers = []
        self.polygon = None
        self.current_slab_area: Optional[float] = None
        self.current_calculation: Optional[dict] = None

        self._configure_styles()
        self._build_header()
        self._build_scroll_layout()
        self._build_map_and_inputs()
        self._build_outputs()

        self.bind_all("<Control-c>", lambda event: None)
        self.after(100, self.enter_typed_mode)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background=BACKGROUND, foreground=TEXT)
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("Title.TLabel", background="#ffffff", foreground=TEXT,
                        font=("Segoe UI", 11, "bold"))
        style.configure("Hint.TLabel", background="#edf6fa", foreground=ACCENT_DARK,
                        font=("Segoe UI", 9))
        style.configure("Accent.TButton", foreground="#ffffff", background=ACCENT,
                        font=("Segoe UI", 10, "bold"), borderwidth=0, padding=(10, 7))
        style.map("Accent.TButton", background=[("active", ACCENT_DARK)])
        style.configure("Secondary.TButton", foreground=ACCENT, background="#ffffff",
                        font=("Segoe UI", 10, "bold"), borderwidth=1, padding=(8, 6))
        style.map("Secondary.TButton", foreground=[("active", ACCENT_DARK)])
        style.configure("Error.TLabel", background="#ffffff", foreground="#b42318",
                        font=("Segoe UI", 8, "bold"))

    def _build_header(self) -> None:
        header = ttk.Frame(self, style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Concrete Pour Planner", style="Title.TLabel",
                  font=("Segoe UI", 16, "bold"), background="#ffffff").pack(anchor="w", padx=24, pady=(14, 0))
        ttk.Label(header, text="Plan slab volume, truck rotations, and arrival timing",
                  background="#ffffff", foreground=MUTED).pack(anchor="w", padx=24, pady=(2, 14))

    def _build_scroll_layout(self) -> None:
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(container, background=BACKGROUND, highlightthickness=0)
        yscroll = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=yscroll.set)
        yscroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.content = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._resize_content)
        self.canvas.bind_all("<MouseWheel>", self._mouse_wheel)

        self.layout = ttk.Frame(self.content)
        self.layout.pack(fill="both", expand=True, padx=20, pady=14)
        self.left = ttk.Frame(self.layout)
        self.right = ttk.Frame(self.layout)
        self.left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.right.pack(side="right", fill="both", expand=True, padx=(10, 0))
        self.layout.bind("<Configure>", self._resize_layout)

    def _resize_content(self, event: tk.Configure) -> None:
        self.canvas.itemconfigure(self.canvas_window, width=event.width)

    def _resize_layout(self, event: tk.Configure) -> None:
        if event.width < 980:
            self.left.pack_forget()
            self.right.pack_forget()
            self.left.pack(fill="x", padx=0, pady=(0, 12))
            self.right.pack(fill="x", padx=0)
        else:
            self.left.pack_forget()
            self.right.pack_forget()
            self.left.pack(side="left", fill="both", expand=True, padx=(0, 10))
            self.right.pack(side="right", fill="both", expand=True, padx=(10, 0))

    def _mouse_wheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _build_map_and_inputs(self) -> None:
        map_card = ttk.Frame(self.left, style="Card.TFrame", padding=14)
        map_card.pack(fill="x", pady=(0, 12))
        map_title = ttk.Frame(map_card, style="Card.TFrame")
        map_title.pack(fill="x")
        ttk.Label(map_title, text="Slab outline", style="Title.TLabel").pack(side="left")
        self.draw_button = ttk.Button(map_title, text="Draw slab", style="Secondary.TButton",
                                      command=self.toggle_drawing)
        self.draw_button.pack(side="right")
        self.hint = ttk.Label(map_card, text="Enter dimensions or choose Draw slab.",
                             style="Hint.TLabel", wraplength=480, padding=(8, 6))
        self.hint.pack(fill="x", pady=(10, 8))

        if tkintermapview:
            self.map = tkintermapview.TkinterMapView(map_card, width=480, height=330,
                                                     corner_radius=8)
            self.map.set_tile_server(
                "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
                "MapServer/tile/{z}/{y}/{x}",
                max_zoom=20,
            )
            self.map.set_position(40.2508, -111.6493)
            self.map.set_zoom(15)
            self.map.pack(fill="both", expand=True)
            self.map_label = ttk.Label(map_card, text="", background="#ffffff",
                                       foreground=TEXT, padding=(8, 5), anchor="center")
            self.map_label.place(relx=0.5, rely=0.94, anchor="s")
            self.map.add_left_click_map_command(self.on_map_click)
            self.map.bind("<Double-1>", self.on_map_double_click)
        else:
            self.map = tk.Canvas(map_card, width=480, height=330, background="#b9c3a9",
                                 highlightthickness=1, highlightbackground=BORDER)
            self.map.pack(fill="both", expand=True)
            self.map.create_text(240, 165, text="Esri map tiles unavailable.\nCalculations remain available.",
                                 fill=TEXT, justify="center")
            self.map_label = ttk.Label(map_card, text="", background="#ffffff",
                                       foreground=TEXT, padding=(8, 5), anchor="center")
            self.map_label.place(relx=0.5, rely=0.94, anchor="s")
            self.map.bind("<Button-1>", self.on_fallback_map_click)

        ttk.Label(map_card, text="Esri World Imagery tiles",
                  background="#ffffff", foreground=MUTED,
                  font=("Segoe UI", 8)).place(relx=0.02, rely=0.97, anchor="sw")

        inputs_card = ttk.Frame(self.left, style="Card.TFrame", padding=14)
        inputs_card.pack(fill="x")
        ttk.Label(inputs_card, text="Pour inputs", style="Title.TLabel").pack(anchor="w")
        mode_row = ttk.Frame(inputs_card, style="Card.TFrame")
        mode_row.pack(fill="x", pady=(10, 8))
        self.draw_mode_button = ttk.Button(mode_row, text="Drawn outline",
                                           style="Secondary.TButton",
                                           command=self.start_drawing)
        self.draw_mode_button.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.typed_mode_button = ttk.Button(mode_row, text="Typed dimensions",
                                            style="Accent.TButton",
                                            command=self.enter_typed_mode)
        self.typed_mode_button.pack(side="left", expand=True, fill="x", padx=(4, 0))

        grid = ttk.Frame(inputs_card, style="Card.TFrame")
        grid.pack(fill="x")
        self.inputs: dict[str, tk.Widget] = {}
        self.errors: dict[str, ttk.Label] = {}
        fields = [
            ("length", "Length (ft)", "40"),
            ("width", "Width (ft)", "60"),
            ("thickness", "Slab thickness (in)", "6"),
            ("waste", "Waste allowance (%)", "5"),
            ("capacity", "Truck capacity (cy)", "10"),
            ("price", "Concrete price (USD/cy)", ""),
            ("fee", "Short-load fee (optional, USD)", ""),
            ("travel", "One-way travel (min)", "20"),
            ("placement", "Placement rate (cy/hr)", "30"),
            ("available", "Available working time (min)", ""),
            ("washout", "Washout & reload (min)", "10"),
            ("arrival", "First truck arrival", "07:00"),
        ]
        for index, (key, label, default) in enumerate(fields):
            frame = ttk.Frame(grid, style="Card.TFrame")
            frame.grid(row=index // 2, column=index % 2, sticky="ew", padx=5, pady=5)
            grid.columnconfigure(index % 2, weight=1)
            ttk.Label(frame, text=label, background="#ffffff",
                      foreground="#42545f", font=("Segoe UI", 9, "bold")).pack(anchor="w")
            entry = ttk.Entry(frame)
            entry.insert(0, default)
            entry.pack(fill="x", pady=(4, 0))
            error = ttk.Label(frame, text="", style="Error.TLabel")
            error.pack(anchor="w", pady=(2, 0))
            self.inputs[key] = entry
            self.errors[key] = error
            entry.bind("<KeyRelease>", lambda event, k=key: self.on_input_changed(k))
            entry.bind("<<Paste>>", lambda event, k=key: self.after_idle(self.on_input_changed, k))

    def _build_outputs(self) -> None:
        summary_card = ttk.Frame(self.right, style="Card.TFrame", padding=14)
        summary_card.pack(fill="x", pady=(0, 12))
        ttk.Label(summary_card, text="Pour summary", style="Title.TLabel").pack(anchor="w")
        cards = ttk.Frame(summary_card, style="Card.TFrame")
        cards.pack(fill="x", pady=(10, 0))
        self.summary_values: dict[str, tk.Widget] = {}
        summary_fields = [
            ("volume", "Concrete to order", "—", "cubic yards"),
            ("loads", "Truckloads", "—", "loads"),
            ("rotation", "Trucks in rotation", "—", "trucks"),
            ("duration", "Pour duration", "—", "estimated"),
            ("finish", "Finish time", "—", "local time"),
        ]
        for index, (key, label, value, unit) in enumerate(summary_fields):
            card = tk.Frame(cards, background="#ffffff", highlightbackground=BORDER,
                            highlightthickness=1, padx=10, pady=10)
            card.grid(row=0, column=index, sticky="nsew", padx=3)
            cards.columnconfigure(index, weight=1)
            tk.Label(card, text=label.upper(), background="#ffffff", foreground=MUTED,
                     font=("Segoe UI", 8, "bold"), wraplength=110, justify="left").pack(anchor="w")
            value_label = tk.Label(card, text=value, background="#ffffff", foreground=TEXT,
                                   font=("Segoe UI", 15, "bold"))
            value_label.pack(anchor="w", pady=(8, 0))
            tk.Label(card, text=unit, background="#ffffff", foreground=MUTED,
                     font=("Segoe UI", 8)).pack(anchor="w", pady=(6, 0))
            self.summary_values[key] = value_label

        set_card = tk.Frame(summary_card, background="#ffffff", highlightbackground=BORDER,
                            highlightthickness=1, padx=10, pady=10)
        set_card.pack(fill="x", pady=(10, 0))
        tk.Label(set_card, text="CONCRETE SET-TIME CHECK", background="#ffffff",
                 foreground=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.set_time_status = tk.Label(set_card,
                                        text="Enter an available working time to check this pour.",
                                        background="#ffffff", foreground=TEXT, wraplength=500,
                                        justify="left")
        self.set_time_status.pack(anchor="w", pady=(8, 0))

        cost_card = tk.Frame(summary_card, background="#ffffff", highlightbackground=BORDER,
                             highlightthickness=1, padx=10, pady=10)
        cost_card.pack(fill="x", pady=(10, 0))
        tk.Label(cost_card, text="ESTIMATED CONCRETE COST", background="#ffffff",
                 foreground=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.cost_total = tk.Label(cost_card, text="—", background="#ffffff", foreground=TEXT,
                                   font=("Segoe UI", 17, "bold"))
        self.cost_total.pack(anchor="w", pady=(8, 0))
        self.cost_breakdown = tk.Label(cost_card,
                                       text="Enter a price per cubic yard to see an estimate.",
                                       background="#ffffff", foreground=MUTED, justify="left")
        self.cost_breakdown.pack(anchor="w", pady=(6, 0))

        timeline_card = ttk.Frame(self.right, style="Card.TFrame", padding=14)
        timeline_card.pack(fill="x", pady=(0, 12))
        ttk.Label(timeline_card, text="Truck schedule", style="Title.TLabel").pack(anchor="w")
        self.schedule_metrics = tk.Label(timeline_card, text="", background="#ffffff",
                                         foreground=MUTED, justify="left", wraplength=520)
        self.schedule_metrics.pack(fill="x", pady=(8, 4))
        timeline_outer = tk.Frame(timeline_card, background="#ffffff")
        timeline_outer.pack(fill="x")
        xscroll = ttk.Scrollbar(timeline_outer, orient="horizontal")
        self.timeline_canvas = tk.Canvas(timeline_outer, height=280, background="#ffffff",
                                         highlightthickness=1,
                                         highlightbackground=BORDER,
                                         xscrollcommand=xscroll.set)
        xscroll.configure(command=self.timeline_canvas.xview)
        self.timeline_canvas.pack(fill="x", expand=True)
        xscroll.pack(fill="x")
        legend = tk.Frame(timeline_card, background="#ffffff")
        legend.pack(fill="x", pady=(8, 0))
        for color, label in [(TRAVEL, "Travel out"), (UNLOADING, "Unloading"),
                             (RETURN, "Trip back"), (WASHOUT, "Washout")]:
            item = tk.Frame(legend, background="#ffffff")
            item.pack(side="left", padx=(0, 12))
            tk.Frame(item, width=10, height=10, background=color).pack(side="left", padx=(0, 5))
            tk.Label(item, text=label, background="#ffffff", foreground=MUTED,
                     font=("Segoe UI", 8)).pack(side="left")

        order_card = ttk.Frame(self.right, style="Card.TFrame", padding=14)
        order_card.pack(fill="x")
        ttk.Label(order_card, text="Order summary", style="Title.TLabel").pack(anchor="w")
        self.order_text = tk.Text(order_card, height=10, wrap="word", background="#f8fafb",
                                  foreground=TEXT, relief="solid", borderwidth=1,
                                  font=("Segoe UI", 9), padx=10, pady=10)
        self.order_text.insert("1.0", "Order details appear when all inputs are valid.")
        self.order_text.configure(state="disabled")
        self.order_text.pack(fill="x", pady=(8, 8))
        action = ttk.Frame(order_card, style="Card.TFrame")
        action.pack(fill="x")
        self.copy_button = ttk.Button(action, text="Copy", style="Accent.TButton",
                                      command=self.copy_order)
        self.copy_button.pack(side="left")
        self.copy_status = tk.Label(action, text="", background="#ffffff",
                                    foreground=MUTED, font=("Segoe UI", 9))
        self.copy_status.pack(side="left", padx=(10, 0))

    def on_input_changed(self, key: str) -> None:
        if key in ("length", "width") and self.mode == "typed":
            self.draw_typed_rectangle()
        self.update_all()

    def parse_positive(self, key: str) -> Optional[float]:
        raw = self.inputs[key].get().strip()
        if not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            return None
        if not math.isfinite(value):
            return None
        return value

    def set_error(self, key: str, valid: bool, message: str) -> bool:
        self.errors[key].configure(text="" if valid else message)
        if valid:
            self.inputs[key].configure(foreground=TEXT)
        else:
            self.inputs[key].configure(foreground="#b42318")
        return valid

    def parse_arrival(self) -> Optional[int]:
        raw = self.inputs["arrival"].get().strip()
        try:
            hour_text, minute_text = raw.split(":")
            hour = int(hour_text)
            minute = int(minute_text)
        except (ValueError, AttributeError):
            return None
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        return hour * 60 + minute

    def toggle_drawing(self) -> None:
        if self.drawing:
            self.cancel_drawing()
        else:
            self.start_drawing()

    def clear_draft(self) -> None:
        if tkintermapview:
            for marker in self.draft_markers:
                marker.delete()
            if self.polygon and self.draft_corners:
                self.polygon.delete()
        self.draft_markers = []
        self.draft_corners = []
        self.drawing = False

    def clear_completed_map_items(self) -> None:
        if not tkintermapview:
            return
        for marker in self.completed_markers:
            marker.delete()
        if self.polygon:
            self.polygon.delete()
        self.completed_markers = []
        self.polygon = None
        self.completed_corners = []

    def start_drawing(self) -> None:
        self.mode = "draw"
        self.drawing = True
        self.draft_corners = []
        self.completed_corners = []
        self.current_slab_area = None
        self.clear_draft()
        self.drawing = True
        if tkintermapview:
            for marker in self.completed_markers:
                marker.delete()
            self.completed_markers = []
            if self.polygon:
                self.polygon.delete()
                self.polygon = None
        self.draw_button.configure(text="Cancel drawing")
        self.hint.configure(text="Click at least three corners, then double-click or click the first point.")
        self.map_label.configure(text="")
        self.clear_calculated_outputs()
        self.update_all()

    def cancel_drawing(self) -> None:
        self.clear_draft()
        self.drawing = False
        self.draw_button.configure(text="Draw slab")
        self.hint.configure(text="Choose Draw slab and click at least three corners.")
        if self.completed_corners:
            self.current_slab_area = geographic_area(self.completed_corners)
        else:
            self.current_slab_area = None
            self.map_label.configure(text="")
        self.update_all()

    def on_map_click(self, coordinates: tuple[float, float]) -> None:
        if not self.drawing:
            return
        lat, lon = coordinates
        if len(self.draft_corners) >= 3:
            first_lat, first_lon = self.draft_corners[0]
            if abs(lat - first_lat) < 0.00025 and abs(lon - first_lon) < 0.00025:
                self.finish_drawing()
                return
        if self.draft_corners:
            prev_lat, prev_lon = self.draft_corners[-1]
            if abs(lat - prev_lat) < 1e-7 and abs(lon - prev_lon) < 1e-7:
                return
        self.draft_corners.append((lat, lon))
        marker = self.map.set_marker(lat, lon, text=str(len(self.draft_corners)),
                                     marker_color_circle=ACCENT,
                                     marker_color_outside=ACCENT_DARK)
        self.draft_markers.append(marker)
        if self.polygon:
            self.polygon.delete()
        self.polygon = self.map.set_polygon(
            [(lat, lon) for lat, lon in self.draft_corners],
            fill_color="#f8c64b",
            outline_color=ACCENT,
            border_width=3,
        )
        self.hint.configure(text="Add at least three corners. Double-click or click the first point to finish.")

    def on_map_double_click(self, event: tk.Event) -> None:
        if self.drawing:
            self.finish_drawing()

    def on_fallback_map_click(self, event: tk.Event) -> None:
        if not self.drawing:
            return
        lat = 40.2508 + (165 - event.y) / 165 * 0.003
        lon = -111.6493 + (event.x - 240) / 240 * 0.003
        self.on_map_click((lat, lon))

    def finish_drawing(self) -> None:
        if len(self.draft_corners) < 3:
            self.hint.configure(text="Choose at least three corners before finishing the slab.")
            self.map_label.configure(text="")
            return
        if has_self_intersection(self.draft_corners):
            self.hint.configure(text="The outline is self-intersecting. Change the last corners and try again.")
            self.map_label.configure(text="")
            return
        self.completed_corners = list(self.draft_corners)
        self.draft_corners = []
        self.draft_markers = []
        self.drawing = False
        self.draw_button.configure(text="Draw slab")
        self.polygon = None
        self.show_completed_polygon()
        self.hint.configure(text="Drag a corner or enter dimensions.")

    def show_completed_polygon(self) -> None:
        if not tkintermapview:
            self.current_slab_area = geographic_area(self.completed_corners)
            self.update_all()
            return
        if self.polygon:
            self.polygon.delete()
        self.polygon = self.map.set_polygon(
            self.completed_corners,
            fill_color="#f8c64b",
            outline_color=ACCENT,
            border_width=3,
        )
        for marker in self.completed_markers:
            marker.delete()
        self.completed_markers = []
        for index, (lat, lon) in enumerate(self.completed_corners):
            marker = self.map.set_marker(lat, lon, text=str(index + 1),
                                         marker_color_circle=ACCENT,
                                         marker_color_outside=ACCENT_DARK)
            self.completed_markers.append(marker)
            self.bind_marker_drag(marker, index)
        self.current_slab_area = geographic_area(self.completed_corners)
        self.update_all()

    def bind_marker_drag(self, marker, index: int) -> None:
        shapes = [marker.big_circle, marker.canvas_icon, marker.canvas_image,
                  marker.canvas_text]
        for shape in shapes:
            if shape is not None:
                marker.map_widget.canvas.tag_bind(shape, "<B1-Motion>",
                                                  lambda event, m=marker, i=index:
                                                  self.drag_marker(event, m, i))
                marker.map_widget.canvas.tag_bind(shape, "<ButtonRelease-1>",
                                                  lambda event, m=marker, i=index:
                                                  self.finish_marker_drag(m, i))

    def drag_marker(self, event: tk.Event, marker, index: int) -> None:
        lat, lon = self.map.convert_canvas_coords_to_decimal_coords(event.x, event.y)
        candidate = list(self.completed_corners)
        candidate[index] = (lat, lon)
        if len(candidate) >= 3 and not has_self_intersection(candidate):
            marker.set_position(lat, lon)
            self.completed_corners[index] = (lat, lon)
            if self.polygon:
                self.polygon.delete()
            self.polygon = self.map.set_polygon(
                self.completed_corners,
                fill_color="#f8c64b",
                outline_color=ACCENT,
                border_width=3,
            )
            self.current_slab_area = geographic_area(self.completed_corners)
            self.update_all()
        else:
            marker.set_position(*self.completed_corners[index])

    def finish_marker_drag(self, marker, index: int) -> None:
        self.hint.configure(text="Drag a corner or enter dimensions.")
        self.update_all()

    def enter_typed_mode(self) -> None:
        self.mode = "typed"
        self.drawing = False
        self.draw_button.configure(text="Draw slab")
        self.typed_mode_button.configure(style="Accent.TButton")
        self.draw_mode_button.configure(style="Secondary.TButton")
        self.draft_corners = []
        if tkintermapview:
            for marker in self.completed_markers:
                marker.delete()
            self.completed_markers = []
        self.completed_corners = []
        if tkintermapview and self.polygon:
            self.polygon.delete()
            self.polygon = None
        self.draw_typed_rectangle()

    def draw_typed_rectangle(self) -> None:
        length = self.parse_positive("length")
        width = self.parse_positive("width")
        length_valid = length is not None and length > 0
        width_valid = width is not None and width > 0
        self.set_error("length", length_valid, "Enter a finite length greater than 0.")
        self.set_error("width", width_valid, "Enter a finite width greater than 0.")
        if not length_valid or not width_valid:
            self.current_slab_area = None
            self.map_label.configure(text="")
            self.clear_calculated_outputs()
            self.hint.configure(text="Correct the highlighted input.")
            if tkintermapview and self.polygon:
                self.polygon.delete()
                self.polygon = None
            return

        self.current_slab_area = length * width
        if tkintermapview:
            center_lat, center_lon = self.map.get_position()
            length_meters = length * 0.3048
            width_meters = width * 0.3048
            lat_delta = (length_meters / 111320) / 2
            lon_delta = (width_meters / (111320 * math.cos(math.radians(center_lat)))) / 2
            corners = [
                (center_lat - lat_delta, center_lon - lon_delta),
                (center_lat - lat_delta, center_lon + lon_delta),
                (center_lat + lat_delta, center_lon + lon_delta),
                (center_lat + lat_delta, center_lon - lon_delta),
            ]
            self.completed_corners = corners
            if self.polygon:
                self.polygon.delete()
            self.polygon = self.map.set_polygon(
                corners,
                fill_color="#f8c64b",
                outline_color=ACCENT,
                border_width=3,
            )
            for marker in self.completed_markers:
                marker.delete()
            self.completed_markers = []
            self.map.set_position(center_lat, center_lon)
        self.hint.configure(text="Drag a corner or enter dimensions.")
        self.update_all()

    def clear_calculated_outputs(self) -> None:
        for key in ("volume", "loads", "rotation", "duration", "finish"):
            self.summary_values[key].configure(text="—")
        self.current_calculation = None
        self.order_text.configure(state="normal")
        self.order_text.delete("1.0", "end")
        self.order_text.insert("1.0", "Correct invalid inputs to generate the order.")
        self.order_text.configure(state="disabled")
        self.copy_button.configure(state="disabled")
        self.copy_status.configure(text="")
        self.cost_total.configure(text="—")
        self.cost_breakdown.configure(text="Enter valid slab and pour inputs to estimate cost.")
        self.set_time_status.configure(
            text="Checker unavailable until all required pour inputs are valid."
        )
        self.timeline_canvas.delete("all")
        self.timeline_canvas.configure(scrollregion=(0, 0, 1, 1))
        self.schedule_metrics.configure(text="")

    def update_all(self) -> None:
        all_valid = True
        if self.mode == "typed":
            length = self.parse_positive("length")
            width = self.parse_positive("width")
            all_valid = self.set_error("length", length is not None and length > 0,
                                       "Enter a finite length greater than 0.") and all_valid
            all_valid = self.set_error("width", width is not None and width > 0,
                                       "Enter a finite width greater than 0.") and all_valid
        else:
            all_valid = self.set_error("length", True, "") and all_valid
            all_valid = self.set_error("width", True, "") and all_valid

        if self.drawing or self.current_slab_area is None or not math.isfinite(self.current_slab_area) or self.current_slab_area <= 0:
            all_valid = False

        rules = [
            ("thickness", lambda value: value is not None and value > 0,
             "Enter a finite thickness greater than 0."),
            ("waste", lambda value: value is not None and value >= 0,
             "Enter a finite waste percentage of 0 or more."),
            ("capacity", lambda value: value is not None and value > 0,
             "Enter a finite truck capacity greater than 0."),
            ("travel", lambda value: value is not None and value > 0,
             "Enter a finite travel time greater than 0."),
            ("placement", lambda value: value is not None and value > 0,
             "Enter a finite placement rate greater than 0."),
            ("washout", lambda value: value is not None and value >= 0,
             "Enter a finite washout time of 0 or more."),
        ]
        values = {}
        for key, rule, message in rules:
            value = self.parse_positive(key)
            valid = rule(value)
            all_valid = self.set_error(key, valid, message) and all_valid
            values[key] = value

        arrival = self.parse_arrival()
        all_valid = self.set_error("arrival", arrival is not None,
                                   "Enter a valid first-truck arrival time.") and all_valid

        if not all_valid:
            self.map_label.configure(text="")
            self.clear_calculated_outputs()
            self.hint.configure(text="Correct the highlighted input.")
            return

        calculation = calculate_pour(
            area=self.current_slab_area,
            thickness=values["thickness"],
            waste=values["waste"],
            truck_capacity=values["capacity"],
            one_way_travel=values["travel"],
            placement_rate=values["placement"],
            washout=values["washout"],
            arrival_minutes=arrival,
        )
        self.current_calculation = calculation
        self.summary_values["volume"].configure(text=f'{calculation["ordered_volume"]:.1f}')
        self.summary_values["loads"].configure(text=str(calculation["truckloads"]))
        self.summary_values["rotation"].configure(text=str(calculation["trucks_in_rotation"]))
        self.summary_values["duration"].configure(
            text=format_duration(calculation["pour_duration_minutes"])
        )
        self.summary_values["finish"].configure(
            text=format_clock_time(calculation["finish_minutes"])
        )
        self.map_label.configure(
            text=f'{self.current_slab_area:,.0f} ft² • {calculation["ordered_volume"]:.1f} cy'
        )
        self.hint.configure(text="Drag a corner or enter dimensions.")
        self.update_set_time_check(calculation["pour_duration_minutes"])
        self.update_cost_estimate(calculation)
        self.update_order_summary(calculation)
        self.render_timeline(calculation)

    def update_set_time_check(self, pour_duration_minutes: float) -> None:
        raw = self.inputs["available"].get().strip()
        if raw == "":
            self.set_error("available", True, "")
            self.set_time_status.configure(
                text="Enter an available working time to check this pour."
            )
            return
        available = self.parse_positive("available")
        valid = available is not None and available > 0
        self.set_error("available", valid,
                       "Enter a finite available working time greater than 0.")
        if not valid:
            self.set_time_status.configure(
                text="Correct the available working time to check this pour."
            )
            return
        remaining = available - pour_duration_minutes
        if remaining >= 0:
            self.set_time_status.configure(
                text=f"Expected to finish within the available time; "
                     f"{remaining:,.2f}".rstrip("0").rstrip(".") + " min remaining."
            )
        else:
            overrun = abs(remaining)
            self.set_time_status.configure(
                text=f"Expected to exceed the available time by "
                     f"{overrun:,.2f}".rstrip("0").rstrip(".") + " min."
            )
        self.set_time_status.configure(text=self.set_time_status.cget("text") +
                                       "\nThis status is an estimate, not a guarantee.")

    def update_cost_estimate(self, calculation: dict) -> None:
        price_raw = self.inputs["price"].get().strip()
        fee_raw = self.inputs["fee"].get().strip()
        price_valid = True
        fee_valid = True
        price = None
        fee = 0.0
        if price_raw == "":
            price_valid = False
        else:
            try:
                price = float(price_raw)
                price_valid = math.isfinite(price) and price >= 0
            except ValueError:
                price_valid = False
        if fee_raw != "":
            try:
                fee = float(fee_raw)
                fee_valid = math.isfinite(fee) and fee >= 0
            except ValueError:
                fee_valid = False
        self.set_error("price", price_valid,
                       "Enter a finite price per cubic yard of 0 or more.")
        self.set_error("fee", fee_valid,
                       "Enter a finite fee of 0 or more, or leave it blank.")
        if not price_valid:
            self.cost_total.configure(text="—")
            self.cost_breakdown.configure(
                text="Enter a valid price per cubic yard to see an estimate."
            )
            return
        if not fee_valid:
            self.cost_total.configure(text="—")
            self.cost_breakdown.configure(text="Correct the short-load fee to see an estimate.")
            return
        concrete_cost, applicable_fee = estimate_cost(
            calculation["ordered_volume"],
            price,
            fee,
            calculation["final_load_size"],
            self.parse_positive("capacity"),
        )
        total = concrete_cost + applicable_fee
        if not math.isfinite(total):
            self.cost_total.configure(text="—")
            self.cost_breakdown.configure(text="This estimate exceeds the supported numeric range.")
            return
        self.cost_total.configure(text=f"${total:,.2f}")
        short = applicable_fee > 0
        self.cost_breakdown.configure(
            text=f"Concrete: ${concrete_cost:,.2f}\n"
                 f"Short-load fee: ${applicable_fee:,.2f}"
                 f"{'' if short else ' (no partial-load fee)'}"
        )

    def update_order_summary(self, calculation: dict) -> None:
        truckloads = calculation["truckloads"]
        capacity = self.parse_positive("capacity")
        final_load = calculation["final_load_size"]
        rotation = calculation["trucks_in_rotation"]
        arrival = self.parse_arrival()
        lines = [
            f'{calculation["ordered_volume"]:.1f} cy concrete',
            f"{truckloads} {'load' if truckloads == 1 else 'loads'}:",
        ]
        for index in range(truckloads):
            load_size = final_load if index == truckloads - 1 else capacity
            truck_number = index % rotation + 1
            partial = " (final partial load)" if load_size < capacity - 1e-9 else ""
            lines.append(
                f"Load {index + 1}: {load_size:,.2f} cy{partial} — Truck {truck_number}"
            )
        lines.extend([
            f"First truck arrival: {format_schedule_time(arrival)}",
            f'Truck spacing: every {format_duration(calculation["full_unload_minutes"])}',
            f"Trucks in rotation: {rotation}",
            f'Final load empty: '
            f'{format_schedule_time(calculation["finish_minutes"])}',
        ])
        text = "\n".join(lines)
        self.order_text.configure(state="normal")
        self.order_text.delete("1.0", "end")
        self.order_text.insert("1.0", text)
        self.order_text.configure(state="disabled")
        self.copy_button.configure(state="normal")
        self.copy_status.configure(text="")

    def copy_order(self) -> None:
        text = self.order_text.get("1.0", "end-1c")
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.clipboard_update()
        except tk.TclError:
            self.copy_status.configure(
                text="Automatic copying was unsuccessful. Select and copy the order text."
            )
        else:
            self.copy_status.configure(text="Copied.")
            self.after(2500, lambda: self.copy_status.configure(text=""))

    def render_timeline(self, calculation: dict) -> None:
        canvas = self.timeline_canvas
        canvas.delete("all")
        truckloads = calculation["truckloads"]
        capacity = self.parse_positive("capacity")
        placement = self.parse_positive("placement")
        travel = self.parse_positive("travel")
        washout = self.parse_positive("washout")
        arrival = self.parse_arrival()
        final_load = calculation["final_load_size"]
        full_unload = calculation["full_unload_minutes"]
        round_trip = calculation["round_trip_minutes"]
        rotation = calculation["trucks_in_rotation"]
        pour_duration = calculation["pour_duration_minutes"]
        last_unload = final_load / placement * 60

        axis_start = math.floor((-travel) / 20) * 20
        total_schedule = (truckloads - 1) * full_unload + last_unload + travel + washout
        axis_end = math.ceil(total_schedule / 20) * 20
        duration = max(20, axis_end - axis_start)
        track_width = max(720, duration * 4)
        scale = track_width / duration
        label_width = 150
        canvas_width = label_width + track_width + 30
        canvas.configure(scrollregion=(0, 0, canvas_width, 280))

        canvas.create_text(8, 18, text="Load / truck", anchor="w",
                           fill=MUTED, font=("Segoe UI", 8, "bold"))
        for tick in range(int(axis_start), int(axis_end) + 20, 20):
            x = label_width + (tick - axis_start) * scale
            canvas.create_line(x, 36, x, 250, fill="#edf1f3")
            canvas.create_text(x, 22, text=format_schedule_time(arrival + tick),
                               anchor="n", fill=MUTED, font=("Segoe UI", 7))

        for index in range(truckloads):
            row_y = 50 + index * 38
            load_number = index + 1
            truck_number = index % rotation + 1
            load_size = final_load if index == truckloads - 1 else capacity
            unload = load_size / placement * 60
            arrival_offset = index * full_unload
            unload_end = arrival_offset + unload
            return_end = unload_end + travel
            washout_end = return_end + washout
            canvas.create_text(8, row_y + 12,
                               text=f"Load {load_number} · T{truck_number}",
                               anchor="w", fill=TEXT,
                               font=("Segoe UI", 8, "bold"))
            segments = [
                ("travel", arrival_offset - travel, arrival_offset, "Travel out"),
                ("unloading", arrival_offset, unload_end, "Unloading"),
                ("return", unload_end, return_end, "Trip back"),
                ("washout", return_end, washout_end, "Washout"),
            ]
            for kind, start, end, label in segments:
                if end <= start:
                    continue
                x1 = label_width + (start - axis_start) * scale
                x2 = label_width + (end - axis_start) * scale
                color = {"travel": TRAVEL, "unloading": UNLOADING,
                         "return": RETURN, "washout": WASHOUT}[kind]
                item = canvas.create_rectangle(x1, row_y, x2, row_y + 24,
                                               fill=color, outline=color)
                detail = (
                    f"{label}, load {load_number}, truck {truck_number}: "
                    f"{format_schedule_time(arrival + start)} to "
                    f"{format_schedule_time(arrival + end)}"
                )
                canvas.tag_bind(item, "<Enter>", lambda event, d=detail:
                                self.show_timeline_tooltip(event, d))
                canvas.tag_bind(item, "<Leave>", lambda event:
                                self.hide_timeline_tooltip())
                canvas.tag_bind(item, "<Return>", lambda event, d=detail:
                                self.show_timeline_tooltip(event, d))
                canvas.tag_bind(item, "<Tab>", lambda event:
                                self.hide_timeline_tooltip())

        self.schedule_metrics.configure(
            text=f"Full-truck unloading: {format_duration(full_unload)} · "
                 f"Truck round trip: {format_duration(round_trip)} · "
                 f"Truck spacing: every {format_duration(full_unload)} · "
                 f"Final load unload: {format_duration(last_unload)} · "
                 f"Last load empty: {format_schedule_time(arrival + pour_duration)}"
        )

    def show_timeline_tooltip(self, event: tk.Event, detail: str) -> None:
        if getattr(self, "_timeline_tooltip", None):
            self._timeline_tooltip.destroy()
        tip = tk.Toplevel(self.timeline_canvas)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
        tk.Label(tip, text=detail, background="#fff7d6", foreground=TEXT,
                 relief="solid", borderwidth=1, padx=6, pady=4).pack()
        self._timeline_tooltip = tip

    def hide_timeline_tooltip(self) -> None:
        tip = getattr(self, "_timeline_tooltip", None)
        if tip:
            tip.destroy()
            self._timeline_tooltip = None


if __name__ == "__main__":
    app = ConcretePourApp()
    app.mainloop()

