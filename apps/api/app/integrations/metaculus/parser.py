import re
from urllib.parse import urlsplit


def parse_metaculus_url(url: str) -> int:
    parsed = urlsplit(url)
    match = re.fullmatch(r'/questions/([1-9][0-9]*)(?:/[^/]*)?/?', parsed.path)
    if (
        parsed.scheme not in {'http', 'https'}
        or parsed.netloc.lower() not in {'metaculus.com', 'www.metaculus.com'}
        or match is None
    ):
        raise ValueError('Enter a valid Metaculus question URL')
    post_id = int(match.group(1))
    if post_id > 2147483647:
        raise ValueError('Metaculus post ID exceeds the supported range')
    return post_id
