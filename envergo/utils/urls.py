from urllib.parse import parse_qs, urlencode, urlparse, urlsplit, urlunparse, urlunsplit


def update_qs(url, params):
    """Update an url query string with new parameters."""

    bits = urlsplit(url)
    query = parse_qs(bits.query)
    query.update(params)
    new_query = urlencode(query, doseq=True)
    new_bits = bits._replace(query=new_query)
    return urlunsplit(new_bits)


def copy_qs(url, from_url):
    """Replace url querystring with querystring from `from_url`."""

    bits = urlsplit(url)
    from_bits = urlsplit(from_url)
    new_bits = bits._replace(query=from_bits.query)
    return urlunsplit(new_bits)


def remove_from_qs(url, key):
    """Remove a parameter from an url query string."""

    bits = urlsplit(url)
    query = parse_qs(bits.query)
    query.pop(key, None)
    new_query = urlencode(query, doseq=True)
    new_bits = bits._replace(query=new_query)
    return urlunsplit(new_bits)


def extract_mtm_params(url):
    """Extract mtm parameters from an url."""

    bits = urlsplit(url)
    query = parse_qs(bits.query)
    mtm_params = {k: v for k, v in query.items() if k.startswith("mtm_")}
    return mtm_params


def extract_param_from_url(url, param_name):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    return query_params.get(param_name, [None])[0]


def update_fragment(url, fragment):
    """Update the fragment of a given URL."""
    parts = urlparse(url)
    new_parts = (
        parts.scheme,
        parts.netloc,
        parts.path,
        parts.params,
        parts.query,
        fragment,
    )
    return urlunparse(new_parts)


def remove_mtm_params(url):
    """Remove mtm parameters from an url."""
    mtm_params = extract_mtm_params(url)
    for param in mtm_params.keys():
        url = remove_from_qs(url, param)
    return url
