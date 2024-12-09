from urllib.parse import parse_qs, urlencode, urlparse, urlsplit, urlunsplit


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
