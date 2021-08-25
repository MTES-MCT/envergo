import markdown


def markdown_to_html(md):
    return markdown.markdown(md, extensions=["nl2br"])
