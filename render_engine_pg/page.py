from pathlib import Path

from render_engine.page import Page
from render_engine.themes import ThemeManager


class PGPage(Page):
    """CUSTOM PAGE OBJECT THAT MAKES IT EASY TO WORK WITH **KWARGS"""

    def __init__(self, *args, **kwargs):
        # Extract Page-specific arguments
        # Attach remaining kwargs as attributes
        for key, value in kwargs.items():
            setattr(self, key, value)

    def render(self, route: str | Path, theme_manager: ThemeManager) -> int:
        result = super().render(route=route, theme_manager=theme_manager)
        return result if isinstance(result, int) else 0
