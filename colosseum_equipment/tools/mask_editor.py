"""Interactive mask editor (tkinter + matplotlib)."""

# mypy: disable-error-code="no-untyped-call,attr-defined,import-untyped"

from __future__ import annotations

import contextlib
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

from colosseum_equipment.tools.mask_schema import (
    REGION_KINDS,
    MaskSchemaError,
    load_mask,
    load_mask_template,
    save_mask,
    validate_mask,
)


class MaskEditorCancelled(RuntimeError):
    """User closed the mask editor without saving."""

    def __init__(self) -> None:
        super().__init__("mask editor cancelled")


def _default_mask(domain: str) -> dict[str, Any]:
    if domain == "time":
        return validate_mask(
            {
                "version": 1,
                "domain": "time",
                "x_unit": "s",
                "y_unit": "V",
                "setup": {"timebase_s": 1e-6, "scale_v": 0.5, "offset_v": 0.0},
                "regions": [],
            },
        )
    return validate_mask(
        {
            "version": 1,
            "domain": "frequency",
            "x_unit": "Hz",
            "y_unit": "dBm",
            "setup": {
                "center_hz": 1e9,
                "span_hz": 100e6,
                "ref_level_dbm": 0.0,
                "rbw_hz": 1e5,
            },
            "regions": [],
        },
    )


def _axis_limits(mask: dict[str, Any]) -> tuple[float, float, float, float]:
    setup = mask.get("setup") or {}
    if mask["domain"] == "frequency":
        center = float(setup.get("center_hz", 1e9))
        span = float(setup.get("span_hz", 100e6))
        xref = float(setup.get("ref_level_dbm", 0.0))
        return center - span / 2, center + span / 2, xref - 100.0, xref + 10.0
    timebase = float(setup.get("timebase_s", 1e-6))
    scale = float(setup.get("scale_v", 0.5))
    offset = float(setup.get("offset_v", 0.0))
    return 0.0, 10 * timebase, offset - 4 * scale, offset + 4 * scale


def _apply_axis_formatters(ax: Any, domain: str) -> None:
    """Stable tick labels so large Hz values do not jump via scientific offset text."""
    from matplotlib.ticker import EngFormatter, ScalarFormatter

    if domain == "frequency":
        ax.xaxis.set_major_formatter(EngFormatter(unit="Hz"))
    else:
        ax.xaxis.set_major_formatter(EngFormatter(unit="s"))
    y_fmt = ScalarFormatter(useOffset=False)
    y_fmt.set_scientific(False)
    ax.yaxis.set_major_formatter(y_fmt)


class MaskEditorApp:
    def __init__(
        self,
        *,
        domain: str,
        path: str = "",
        template: str = "",
        import_path: str = "",
    ) -> None:
        self._path = path
        self._result_path: Path | None = None
        self._drag_start: tuple[float, float] | None = None
        self._temp_rect: Any = None
        self._patches: list[Any] = []
        self._bg_line: tuple[list[float], list[float]] | None = None
        # Locked view (xmin, xmax, ymin, ymax); not recomputed on every region edit.
        self._view: tuple[float, float, float, float] | None = None
        self._selected: int | None = None

        if import_path:
            self._mask = load_mask(import_path)
            domain = str(self._mask["domain"])
        elif template:
            self._mask = load_mask_template(template)
            domain = str(self._mask["domain"])
        else:
            self._mask = _default_mask(domain)

        self._domain = domain
        self._root = tk.Tk()
        self._root.title(f"Colosseum mask editor ({domain})")
        self._root.protocol("WM_DELETE_WINDOW", self._on_cancel)

        with contextlib.suppress(ImportError, ModuleNotFoundError):
            import customtkinter as ctk

            ctk.set_appearance_mode("System")

        self._build_ui()
        self._redraw(reset_view=True)

    def _build_ui(self) -> None:
        import matplotlib as mpl

        mpl.use("TkAgg")
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        from matplotlib.figure import Figure

        toolbar = ttk.Frame(self._root)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(toolbar, text="Save", command=self._on_save).pack(side=tk.LEFT, padx=4, pady=4)
        ttk.Button(toolbar, text="Import…", command=self._on_import).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="Load template…", command=self._on_template).pack(
            side=tk.LEFT, padx=4,
        )
        ttk.Button(toolbar, text="Background CSV…", command=self._on_bg_csv).pack(
            side=tk.LEFT, padx=4,
        )
        ttk.Button(toolbar, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT, padx=4)

        body = ttk.Frame(self._root)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        list_frame = ttk.Frame(body)
        list_frame.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4)
        ttk.Label(list_frame, text="Regions").pack(anchor=tk.W)
        self._list = tk.Listbox(list_frame, width=36, exportselection=False)
        self._list.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self._list.bind("<<ListboxSelect>>", lambda _e: self._on_select_region())
        self._list.bind("<Delete>", lambda _e: self._on_delete())
        self._list.bind("<BackSpace>", lambda _e: self._on_delete())
        list_btns = ttk.Frame(list_frame)
        list_btns.pack(side=tk.TOP, fill=tk.X, pady=4)
        ttk.Button(list_btns, text="Delete", command=self._on_delete).pack(
            side=tk.LEFT, padx=(0, 4),
        )
        ttk.Button(list_btns, text="Delete all", command=self._on_delete_all).pack(side=tk.LEFT)

        kind_frame = ttk.Frame(body)
        kind_frame.pack(side=tk.LEFT, fill=tk.Y, padx=2)
        ttk.Label(kind_frame, text="Region kind").pack(anchor=tk.W)
        self._kind_var = tk.StringVar(value="keep_below")
        for kind in sorted(REGION_KINDS):
            ttk.Radiobutton(
                kind_frame, text=kind, value=kind, variable=self._kind_var,
                command=self._on_kind_change,
            ).pack(anchor=tk.W)

        self._root.bind("<Delete>", lambda _e: self._on_delete())
        self._root.bind("<BackSpace>", lambda _e: self._on_delete())

        plot_frame = ttk.Frame(body)
        plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        fig = Figure(figsize=(8, 5), dpi=100)
        self._ax = fig.add_subplot(111)
        self._ax.set_autoscale_on(False)
        self._canvas = FigureCanvasTkAgg(fig, master=plot_frame)
        self._canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        nav = NavigationToolbar2Tk(self._canvas, plot_frame)
        nav.update()
        self._canvas.mpl_connect("button_press_event", self._on_press)
        self._canvas.mpl_connect("button_release_event", self._on_release)
        self._canvas.mpl_connect("motion_notify_event", self._on_motion)
        # Remember pan/zoom from the matplotlib toolbar between region edits.
        self._ax.callbacks.connect("xlim_changed", self._on_limits_changed)
        self._ax.callbacks.connect("ylim_changed", self._on_limits_changed)

    def _on_limits_changed(self, _ax: Any) -> None:
        if self._drag_start is not None:
            return
        if self._view is None:
            return
        self._view = (
            float(self._ax.get_xlim()[0]),
            float(self._ax.get_xlim()[1]),
            float(self._ax.get_ylim()[0]),
            float(self._ax.get_ylim()[1]),
        )

    def _apply_view(self) -> None:
        if self._view is None:
            self._view = _axis_limits(self._mask)
        xmin, xmax, ymin, ymax = self._view
        self._ax.set_xlim(xmin, xmax)
        self._ax.set_ylim(ymin, ymax)
        self._ax.set_autoscale_on(False)

    def _refresh_list(self) -> None:
        self._list.delete(0, tk.END)
        for region in self._mask["regions"]:
            self._list.insert(
                tk.END,
                f"{region['id']}: {region['kind']} "
                f"[{region['x0']:g},{region['x1']:g}]×[{region['y0']:g},{region['y1']:g}]",
            )
        if self._selected is not None:
            if 0 <= self._selected < len(self._mask["regions"]):
                self._list.selection_set(self._selected)
                self._list.activate(self._selected)
                self._list.see(self._selected)
            else:
                self._selected = None

    def _set_selected(self, index: int | None, *, redraw: bool = False) -> None:
        n = len(self._mask["regions"])
        if index is not None and not (0 <= index < n):
            index = None
        self._selected = index
        if index is not None:
            self._kind_var.set(self._mask["regions"][index]["kind"])
        if redraw:
            self._redraw()
        else:
            self._refresh_list()

    def _region_index_at(self, x: float, y: float) -> int | None:
        """Return the topmost (smallest-area) region containing (x, y)."""
        hits: list[tuple[float, int]] = []
        for index, region in enumerate(self._mask["regions"]):
            x0, x1 = float(region["x0"]), float(region["x1"])
            y0, y1 = float(region["y0"]), float(region["y1"])
            if x0 <= x <= x1 and y0 <= y <= y1:
                area = max(x1 - x0, 1e-30) * max(y1 - y0, 1e-30)
                hits.append((area, index))
        if not hits:
            return None
        hits.sort(key=lambda item: item[0])
        return hits[0][1]

    def _redraw(self, *, reset_view: bool = False) -> None:
        from matplotlib.patches import Rectangle

        if reset_view:
            self._view = _axis_limits(self._mask)
        elif self._view is None:
            self._view = _axis_limits(self._mask)

        self._temp_rect = None
        self._ax.clear()
        self._ax.set_autoscale_on(False)
        self._apply_view()
        self._ax.grid(visible=True, which="both", alpha=0.35)
        self._ax.minorticks_on()
        _apply_axis_formatters(self._ax, self._domain)
        if self._domain == "frequency":
            self._ax.set_xlabel("Frequency")
            self._ax.set_ylabel("Amplitude (dBm)")
        else:
            self._ax.set_xlabel("Time")
            self._ax.set_ylabel("Voltage (V)")
        self._ax.set_title("Click a region to select · Delete / Backspace to remove")

        if self._bg_line is not None:
            xs, ys = self._bg_line
            (line,) = self._ax.plot(
                xs, ys, color="0.5", linewidth=1.0, alpha=0.7, label="background",
            )
            line.set_clip_on(True)

        colors = {
            "keep_below": "#e74c3c55",
            "keep_above": "#3498db55",
            "keep_inside": "#2ecc7155",
            "keep_outside": "#9b59b655",
        }
        self._patches.clear()
        for index, region in enumerate(self._mask["regions"]):
            width = float(region["x1"]) - float(region["x0"])
            height = float(region["y1"]) - float(region["y0"])
            selected = index == self._selected
            patch = Rectangle(
                (float(region["x0"]), float(region["y0"])),
                width,
                height,
                facecolor=colors.get(region["kind"], "#88888855"),
                edgecolor="#f1c40f" if selected else "black",
                linewidth=2.4 if selected else 1.2,
                clip_on=True,
            )
            # Patches must not expand data limits / autoscale the graticule.
            patch.set_in_layout(False)
            self._ax.add_patch(patch)
            self._patches.append(patch)
            self._ax.text(
                float(region["x0"]),
                float(region["y1"]),
                region["id"],
                fontsize=8,
                va="bottom",
                clip_on=True,
            )
        self._apply_view()
        self._refresh_list()
        self._canvas.draw_idle()

    def _on_select_region(self) -> None:
        sel = self._list.curselection()
        if not sel:
            return
        index = int(sel[0])
        if index == self._selected:
            self._kind_var.set(self._mask["regions"][index]["kind"])
            return
        self._set_selected(index, redraw=True)

    def _on_kind_change(self) -> None:
        if self._selected is None:
            return
        self._mask["regions"][self._selected]["kind"] = self._kind_var.get()
        self._mask = validate_mask(self._mask)
        self._redraw()

    def _on_delete(self) -> None:
        if self._selected is None:
            sel = self._list.curselection()
            if sel:
                self._selected = int(sel[0])
        if self._selected is None:
            return
        index = self._selected
        if not (0 <= index < len(self._mask["regions"])):
            self._selected = None
            return
        del self._mask["regions"][index]
        if self._mask["regions"]:
            self._selected = min(index, len(self._mask["regions"]) - 1)
        else:
            self._selected = None
        self._redraw()

    def _on_delete_all(self) -> None:
        if not self._mask["regions"]:
            return
        if not messagebox.askyesno("Delete all", "Remove every mask region?"):
            return
        self._mask["regions"] = []
        self._selected = None
        self._redraw()

    def _on_press(self, event: Any) -> None:
        if event.inaxes != self._ax or event.xdata is None or event.ydata is None:
            return
        if event.button != 1:
            return
        # Ignore clicks while using matplotlib pan/zoom tools.
        mode = getattr(getattr(self._canvas, "toolbar", None), "mode", "")
        if mode:
            return
        self._drag_start = (float(event.xdata), float(event.ydata))

    def _on_motion(self, event: Any) -> None:
        if self._drag_start is None or event.inaxes != self._ax:
            return
        if event.xdata is None or event.ydata is None:
            return
        from matplotlib.patches import Rectangle

        x0, y0 = self._drag_start
        x1, y1 = float(event.xdata), float(event.ydata)
        left, bottom = min(x0, x1), min(y0, y1)
        width, height = abs(x1 - x0), abs(y1 - y0)
        if self._temp_rect is None:
            self._temp_rect = Rectangle(
                (left, bottom),
                width,
                height,
                fill=False,
                edgecolor="black",
                linestyle="--",
                clip_on=True,
            )
            self._temp_rect.set_in_layout(False)
            self._ax.add_patch(self._temp_rect)
        else:
            self._temp_rect.set_xy((left, bottom))
            self._temp_rect.set_width(width)
            self._temp_rect.set_height(height)
        self._apply_view()
        self._canvas.draw_idle()

    def _on_release(self, event: Any) -> None:
        if self._drag_start is None or event.xdata is None or event.ydata is None:
            self._drag_start = None
            if self._temp_rect is not None:
                self._temp_rect.remove()
                self._temp_rect = None
            return
        x0, y0 = self._drag_start
        x1, y1 = float(event.xdata), float(event.ydata)
        self._drag_start = None
        if self._temp_rect is not None:
            self._temp_rect.remove()
            self._temp_rect = None

        # Tiny drag → select existing region under the click (or clear selection).
        view = self._view or _axis_limits(self._mask)
        x_span = max(abs(view[1] - view[0]), 1e-30)
        y_span = max(abs(view[3] - view[2]), 1e-30)
        click_tol = 0.01  # 1% of each axis span
        if abs(x1 - x0) < click_tol * x_span and abs(y1 - y0) < click_tol * y_span:
            hit = self._region_index_at(x1, y1)
            self._set_selected(hit, redraw=True)
            return

        region_id = f"region_{len(self._mask['regions'])}"
        self._mask["regions"].append(
            {
                "id": region_id,
                "kind": self._kind_var.get(),
                "x0": min(x0, x1),
                "x1": max(x0, x1),
                "y0": min(y0, y1),
                "y1": max(y0, y1),
            },
        )
        self._mask = validate_mask(self._mask)
        self._selected = len(self._mask["regions"]) - 1
        self._redraw()

    def _on_import(self) -> None:
        path = filedialog.askopenfilename(
            title="Import mask",
            filetypes=[("Mask JSON", "*.json"), ("All", "*.*")],
        )
        if not path:
            return
        self._mask = load_mask(path)
        self._domain = str(self._mask["domain"])
        self._redraw(reset_view=True)

    def _on_template(self) -> None:
        from colosseum_equipment.tools.mask_schema import list_mask_templates

        templates = list_mask_templates()
        if not templates:
            messagebox.showerror("Templates", "No built-in templates found")
            return
        choice = simpledialog.askstring(
            "Load template",
            "Template id:\n" + ", ".join(templates),
            parent=self._root,
        )
        if not choice:
            return
        try:
            self._mask = load_mask_template(choice)
        except (MaskSchemaError, OSError, ValueError) as exc:
            messagebox.showerror("Templates", str(exc))
            return
        self._domain = str(self._mask["domain"])
        self._redraw(reset_view=True)

    def _on_bg_csv(self) -> None:
        path = filedialog.askopenfilename(
            title="Background trace CSV",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
        )
        if not path:
            return
        try:
            from colosseum_equipment.tools.mask_verify import read_trace_xy

            xs, ys, _domain = read_trace_xy(Path(path))
            self._bg_line = (xs, ys)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Background CSV", str(exc))
            return
        self._redraw()

    def _resolve_save_path(self) -> Path | None:
        if self._path:
            candidate = Path(self._path)
            try:
                from colosseum.context import get_context

                get_context()
                from colosseum_equipment._paths import resolve_artifact_path

                return resolve_artifact_path(str(candidate).replace("\\", "/"))
            except (RuntimeError, ValueError, OSError):
                candidate.parent.mkdir(parents=True, exist_ok=True)
                return candidate
        path = filedialog.asksaveasfilename(
            title="Save mask",
            defaultextension=".json",
            filetypes=[("Mask JSON", "*.json")],
        )
        return Path(path) if path else None

    def _on_save(self) -> None:
        out = self._resolve_save_path()
        if out is None:
            return
        try:
            save_mask(out, self._mask)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self._result_path = out
        self._root.quit()

    def _on_cancel(self) -> None:
        self._result_path = None
        self._root.quit()

    def run(self) -> Path:
        self._root.mainloop()
        with contextlib.suppress(tk.TclError):
            self._root.destroy()
        if self._result_path is None:
            raise MaskEditorCancelled()
        return self._result_path


def run_mask_editor(
    *,
    domain: str,
    path: str = "",
    template: str = "",
    import_path: str = "",
) -> Path:
    """Block until the user saves a mask; raise ``MaskEditorCancelled`` on cancel."""
    domain_norm = domain.strip().lower()
    if domain_norm not in {"frequency", "time"}:
        raise ValueError("domain must be 'frequency' or 'time'")
    app = MaskEditorApp(
        domain=domain_norm,
        path=path,
        template=template,
        import_path=import_path,
    )
    return app.run()
