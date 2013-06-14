# -*- coding: utf-8 -*-
import collections
from xml.etree import ElementTree

SUCCESS = 0
PENDING = -1
BAD_SERVER_DATA = 4
TIMEOUT = 42

Error = collections.namedtuple('Error', 'code server module line text')

def err(code, text=''):
    import inspect
    frame = inspect.stack()[1]
    return Error(code, 0, 0, line=frame[2], text=text)


def parse_error(body):
    try:
        elem = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        return err(BAD_SERVER_DATA, 'parse_error, invalid XML')

    try:
        return Error(
            int(elem.get('code', '0')),
            int(elem.get('server', '0')),
            int(elem.get('module', '0')),
            int(elem.get('line', '0')),
            elem.get('text', '')
        )
    except ValueError:
        return err(BAD_SERVER_DATA, 'parse_error, invalid attribute(s)')


def build_error(error):
    return ElementTree.Element('Error', error._asdict()).tostring()