from render_engine.page import BasePageParser


class PGParser(BasePageParser):
    @staticmethod
    def parse_content(content):
        return {}, content
