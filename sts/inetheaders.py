# -*- coding: utf-8 -*-

class Header(object):

    def __init__(self, name):

        if (isinstance(name, Header)):
            name = name.normalized

        name            = name.strip()
        self.normalized = name.lower()

    def __hash__(self):
        return hash(self.normalized)

    def __eq__(self, right):
        assert isinstance(right, Header), 'Invalid Comparison'
        return self.normalized == right.normalized

    def __str__(self):
        return self.normalized

ACCEPT = Header('a')
CONTENT_ENCODING = Header('e')
CONTENT_LENGTH = Header('l')
CONTENT_RANGE = Header('n')
CONTENT_TYPE = Header('c')
FROM = Header('f')
FROM_EX = Header('g')
FROM_RIGHTS = Header('h')
REFER_TO = Header('r')
REPLY_TO = Header('p')
SEQUENCE = Header('q')
STREAM = Header('m')
SUBJECT = Header('s')
TIMESTAMP = Header('z')
TO = Header('t')
TRACE = Header('i')
TRANSFER_ENCODING = Header('x')
VIA = Header('v')


COMPACT_HEADERS = dict([(Header(key), value) for key, value in {
    'Accept': ACCEPT,
    'Content-Encoding': CONTENT_ENCODING,
    'Content-Length': CONTENT_LENGTH,
    'Content-Range': CONTENT_RANGE,
    'Content-Type': CONTENT_TYPE,
    'From': FROM,
    'X-From-Game': FROM_EX,
    'X-From-Rights': FROM_RIGHTS,
    'Refer-To': REFER_TO,
    'Reply-To': REPLY_TO,
    'X-Sequence': SEQUENCE,
    'Stream': STREAM,
    'Subject': SUBJECT,
    'Timestamp': TIMESTAMP,
    'To': TO,
    'X-Trace-ID': TRACE,
    'Transfer-Encoding': TRANSFER_ENCODING,
    'Via': VIA
}.items()])


MULTI_HEADERS = frozenset([Header(name) for name in [
    ACCEPT, 'Accept-Charset', 'Accept-Encoding', 'Accept-Language', 'Accept-Ranges', 'Allow', 'Cache-Control',
    'Connection', CONTENT_ENCODING, 'Content-Language', 'Expect', 'If-Match', 'If-None-Match', 'Pragma',
    'Proxy-Authenticate', 'Set-Cookie', 'TE', 'Trailer', TRANSFER_ENCODING, 'Upgrade', 'User-Agent', 'Vary', VIA,
    'Warning', 'WWW-Authenticate', 'X-Forwarded-For'
]])
