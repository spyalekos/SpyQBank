"""Live Log Console component for SpyQBank (Windows instant repaint compliant)."""

from datetime import datetime
import flet as ft
from src.ui.theme import BG_DARK, BORDER_DARK


class LogConsole(ft.Container):
    """
    Log Console control with auto-scroll and instant text buffer update.
    Follows the LogConsole pattern from .agents/flet.md.
    """

    def __init__(self, height: int = 140):
        self.log_text = ft.Text(
            value="[SpyQBank] Έτοιμο για χρήση.\n",
            font_family="Consolas, monospace",
            size=11,
            color="#94A3B8",
            selectable=True,
        )

        self.scroll_col = ft.Column(
            controls=[self.log_text],
            scroll=ft.ScrollMode.ALWAYS,
            auto_scroll=True,
            spacing=0,
            tight=True,
        )

        super().__init__(
            content=self.scroll_col,
            bgcolor="#0B0F19",
            border=ft.Border.all(1, BORDER_DARK),
            border_radius=8,
            padding=ft.Padding(10, 8, 10, 8),
            height=height,
            expand=False,
        )

    def log(self, message: str, level: str = "INFO"):
        """Add a log line and repaint immediately."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "SYNC": "🔄",
            "PDF": "📑",
        }.get(level, "•")

        line = f"[{timestamp}] {prefix} {message}\n"
        self.log_text.value += line
        try:
            self.update()
        except Exception:
            pass

    def clear(self):
        """Clear log console."""
        self.log_text.value = f"[{datetime.now().strftime('%H:%M:%S')}] Κονσόλα καθαρίστηκε.\n"
        try:
            self.update()
        except Exception:
            pass
