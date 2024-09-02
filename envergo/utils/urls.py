from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit


def update_qs(url, params):
    """Update an url query string with new parameters."""

    bits = urlsplit(url)
    query = parse_qs(bits.query)
    query.update(params)
    new_query = urlencode(query, doseq=True)
    new_bits = bits._replace(query=new_query)
    return urlunsplit(new_bits)


def remove_from_qs(url, key):
    """Remove a parameter from an url query string."""

    bits = urlsplit(url)
    query = parse_qs(bits.query)
    query.pop(key, None)
    new_query = urlencode(query, doseq=True)
    new_bits = bits._replace(query=new_query)
    return urlunsplit(new_bits)
