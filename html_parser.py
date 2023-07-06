from html.parser import HTMLParser


class MyHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = ""

    def handle_data(self, data):
        self.text += data


def html_to_text(html):
    parser = MyHTMLParser()
    parser.feed(html)
    return parser.text
