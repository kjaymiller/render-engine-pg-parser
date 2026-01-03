from render_engine.page import BasePageParser


class PGPageParser(BasePageParser):
    @staticmethod
    def parse_content(data):
        return data, data.get("content")
