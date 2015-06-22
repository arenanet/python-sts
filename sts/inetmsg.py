# -*- coding: utf-8 -*-
from . import inetheaders
import collections

PROTOCOL_VERSION = 'STS/1.0'


class ParseError(Exception):
    """Invalid message content."""


RequestLine = collections.namedtuple('RequestLine', 'method uri')
StatusLine = collections.namedtuple('StatusLine', 'code reason')


def _read_start_line(fp):
    line = fp.readline().strip().split(' ')
    if len(line) != 3:
        raise ParseError('start line, invalid format')

    if line[0] == PROTOCOL_VERSION:
        return StatusLine(code=int(line[1]), reason=line[2])
    elif line[2] == PROTOCOL_VERSION:
        return RequestLine(method=line[0], uri=line[1])
    else:
        raise ParseError('start line, invalid protocol version')


def _parse_header(line):
    name, value = line.split(':', 1)
    name = inetheaders.Header(name.strip())

    if name in inetheaders.COMPACT_HEADERS:
        name = inetheaders.COMPACT_HEADERS[name]

    value = value.strip()
    if name in inetheaders.MULTI_HEADERS:
        value = [value.strip() for value in value.split(',')]

    return name, value


def _read_headers(fp):
    headers = {}

    while True:
        line = fp.readline()
        if not line:
            raise ParseError('headers, EOF during parsing')
        if line == '\r\n':
            break

        name, value = _parse_header(line)
        if isinstance(value, list):
            headers.get(name, []).extend(value)
        else:
            headers[name] = value

    return headers


def _read_body(fp, headers):
    return fp.read(int(headers.get(inetheaders.CONTENT_LENGTH, 0)))


def read_message(fp):
    """Read an STS message from a file-like object and return the start line, headers, and body."""
    start_line = _read_start_line(fp)
    headers = _read_headers(fp)
    body = _read_body(fp, headers)

    return start_line, headers, body


def _build_start_line(start_line):
    if isinstance(start_line, StatusLine):
        return '%s %d %s\r\n' % (PROTOCOL_VERSION, start_line.code, start_line.reason)
    elif isinstance(start_line, RequestLine):
        return '%s %s %s\r\n' % (start_line.method, start_line.uri, PROTOCOL_VERSION)
    else:
        raise TypeError('start_line must be a StatusLine or RequestLine')


def _build_header_line(header):
    name, value = header
    if isinstance(value, list):
        value = ','.join(value)

    return '%s: %s\r\n' % (name, value)


def _build_header_lines(headers):
    return [_build_header_line(header) for header in headers.items()] + ['\r\n']


def build_message(start_line, headers, body):
    """Return a string containing an STS message built using the provided start line, headers, and body."""
    return ''.join([_build_start_line(start_line)] + _build_header_lines(headers) + [body])
