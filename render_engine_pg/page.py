from render_engine.page import Page


class PGPage(Page):
    """CUSTOM PAGE OBJECT THAT MAKES IT EASY TO WORK WITH **KWARGS"""

    def __init__(self, *args, **kwargs):
        # Extract Page-specific arguments
        page_kwargs = {
            k: v for k, v in kwargs.items()
            if k in ('content_path', 'content', 'Parser')
        }
        # Initialize parent Page with valid arguments
        super().__init__(**page_kwargs)

        # Attach remaining kwargs as attributes
        for key, value in kwargs.items():
            if key not in page_kwargs:
                setattr(self, key, value)

