from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit


def update_qs(url, params):
    """Update an url query string with new parameters."""

    bits = urlsplit(url)
    query = parse_qs(bits.query)
    query.update(params)
    new_query = urlencode(query, doseq=True)
    new_bits = bits._replace(query=new_query)
    return urlunsplit(new_bits)
