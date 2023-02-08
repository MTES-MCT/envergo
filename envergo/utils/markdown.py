import markdown


def markdown_to_html(md, *extensions):
    return markdown.markdown(md, extensions=extensions)
