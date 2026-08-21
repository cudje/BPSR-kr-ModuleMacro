"""9번 키 — 등록된 영역을 색이 다른 빈 박스로 표시."""

from __future__ import annotations

import logging
import threading
import tkinter as tk

from agent.regions import Region, get_all_regions

log = logging.getLogger(__name__)

_TRANSPARENT = "#010101"
_lock = threading.Lock()
_controller: "_OverlayController | None" = None


class _OverlayController:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._root: tk.Tk | None = None
        self._visible = False
        self._ready = threading.Event()

    @property
    def visible(self) -> bool:
        return self._visible

    def ensure_started(self) -> None:
        if self._thread and self._thread.is_alive():
            self._ready.wait(timeout=5)
            return
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="region-overlay")
        self._thread.start()
        self._ready.wait(timeout=5)

    def _run(self) -> None:
        root = tk.Tk()
        self._root = root
        root.withdraw()
        root.title("ModuleMacro Regions")
        root.attributes("-topmost", True)
        root.overrideredirect(True)
        root.configure(bg=_TRANSPARENT)
        try:
            root.attributes("-transparentcolor", _TRANSPARENT)
        except tk.TclError:
            log.warning("transparentcolor 미지원 — 반투명으로 표시")
            root.attributes("-alpha", 0.35)

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"{sw}x{sh}+0+0")

        canvas = tk.Canvas(
            root,
            width=sw,
            height=sh,
            bg=_TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        canvas.pack(fill="both", expand=True)
        self._canvas = canvas
        self._draw_regions(get_all_regions())

        self._ready.set()
        root.mainloop()
        self._root = None
        self._visible = False

    def _draw_regions(self, regions: tuple[Region, ...]) -> None:
        canvas = self._canvas
        canvas.delete("all")
        for region in regions:
            canvas.create_rectangle(
                region.left,
                region.top,
                region.right,
                region.bottom,
                outline=region.color,
                width=2,
                fill="",
            )
            label_y = max(0, region.top - 18)
            canvas.create_text(
                region.left,
                label_y,
                anchor="nw",
                text=region.name,
                fill=region.color,
                font=("Segoe UI", 10, "bold"),
            )

    def show(self) -> None:
        self.ensure_started()
        root = self._root
        if root is None:
            return

        def _show() -> None:
            self._draw_regions(get_all_regions())
            root.deiconify()
            root.lift()
            root.attributes("-topmost", True)
            self._visible = True

        root.after(0, _show)
        log.info("영역 보기 ON (%s개)", len(get_all_regions()))

    def hide(self) -> None:
        root = self._root
        if root is None:
            self._visible = False
            return

        def _hide() -> None:
            root.withdraw()
            self._visible = False

        root.after(0, _hide)
        log.info("영역 보기 OFF")

    def toggle(self) -> None:
        self.ensure_started()
        if self._visible:
            self.hide()
        else:
            self.show()


def toggle_region_overlay() -> None:
    """등록된 모든 영역을 토글 표시."""
    global _controller
    with _lock:
        if _controller is None:
            _controller = _OverlayController()
        _controller.toggle()
