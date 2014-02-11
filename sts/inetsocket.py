# -*- coding: utf-8 -*-
import gevent
import gevent.queue
import gevent.socket
import itertools
from . import inetheaders, inetmsg, ineterr


AUTO_PING_SECONDS = 30


class Socket(object):
    def __init__(self, socket):
        self._txn_id = itertools.count(start=1)
        self._txn_queues = {}
        self._socket = None
        self.attach_socket(socket)

    def detach_socket(self):
        assert(self._socket is not None)
        self._send_greenlet.kill()
        self._read_greenlet.kill()
        socket, self._socket = self._socket, None
        return socket

    def attach_socket(self, socket):
        assert(self._socket is None)
        assert(type(socket) is gevent.socket.socket)
        self._socket = socket
        self._send_queue = gevent.queue.Queue()
        self._send_greenlet = gevent.spawn(self._send_worker, socket, self._send_queue)
        self._read_queue = gevent.queue.Queue()
        self._read_greenlet = gevent.spawn(self._read_worker, socket, self._read_queue)

    def _read_worker(self, socket, queue):
        fd = socket.makefile('rb')
        while True:
            start_line, headers, body = inetmsg.read_message(fd)
            if isinstance(start_line, inetmsg.StatusLine):
                self._handle_response(start_line, headers, body)
                continue

            queue.put((start_line, headers, body))

    def _handle_response(self, start_line, headers, body):
        try:
            txn_id = int(headers.get(inetheaders.SUBJECT, '0').lower().split(';')[0].split('r')[0])
        except ValueError:
            return

        if txn_id in self._txn_queues:
            self._txn_queues[txn_id].put((start_line, headers, body))

    def _read(self, queue, timeout):
        start_line, headers, body = queue.get(timeout=timeout)
        if isinstance(start_line, inetmsg.StatusLine) and start_line.code >= 400:
            err = ineterr.parse_error(body)
            if err.code == ineterr.PENDING:
                err = ineterr.err(ineterr.BAD_SERVER_DATA, '_read, received PENDING')
            body = None
        else:
            err = ineterr.err(ineterr.SUCCESS)

        return err, start_line, headers, body

    def read(self, timeout=None):
        while True:
            try:
                err, start_line, headers, body = self._read(self._read_queue, timeout)
            except gevent.queue.Empty:
                return None

            if isinstance(start_line, inetmsg.StatusLine):
                err = ineterr.err(ineterr.BAD_SERVER_DATA, 'read, received status')

            if body is None:
                #TODO: log error
                continue
            try:
                __, protocol, command = start_line.uri.split('/')
            except ValueError:
                #TODO: Log error
                continue
            return (protocol, command, headers, body)

    def _send_worker(self, socket, queue):
        while True:
            try:
                start_line, headers, body = queue.get(timeout=AUTO_PING_SECONDS)
                socket.sendall(inetmsg.build_message(start_line, headers, body))
            except gevent.queue.Empty:
                self._send(queue, inetmsg.RequestLine(method='P', uri='/Sts/Ping'))

    def _send(self, queue, start_line, headers=None, body=None):
        headers = headers if headers is not None else {}
        body = body if body is not None else ''

        content_type = headers.get(inetheaders.CONTENT_TYPE, 'application/xml')
        if content_type == 'application/xml':
            body += '\n'

        if len(body) > 0:
            headers[inetheaders.CONTENT_LENGTH] = str(len(body))
        elif inetheaders.CONTENT_LENGTH in headers:
            del headers[inetheaders.CONTENT_LENGTH]

        queue.put((start_line, headers, body))

    def send(self, protocol, command, headers=None, body=None):
        request_line = inetmsg.RequestLine(method='P', uri='/%s/%s' % (protocol, command))
        self._send(self._send_queue, request_line, headers, body)

    def _request(self, protocol, command, headers=None, body=None, timeout=None):
        txn_id = self._txn_id.next()
        self._txn_queues[txn_id] = gevent.queue.Queue()
        try:
            if headers is None:
                headers = {}
            headers[inetheaders.SUBJECT] = str(txn_id)
            self.send(protocol, command, headers, body)
            next_seq = None
            while True:
                try:
                    err, start_line, headers, body = self._read(self._txn_queues[txn_id], timeout)
                except gevent.queue.Empty:
                    yield ineterr.err(ineterr.TIMEOUT), None
                    break

                if isinstance(start_line, inetmsg.RequestLine):
                    err = ineterr.err(ineterr.BAD_SERVER_DATA, '_request, received request')

                subject = headers[inetheaders.SUBJECT].split(';')[0]

                try:
                    __, seq = subject.lower().split('r')
                    seq = int(seq) if seq else None
                except ValueError:
                    err = ineterr.err(ineterr.BAD_SERVER_DATA, '_request, malformed subject')

                if seq is None and next_seq is not None:
                    err = ineterr.err(ineterr.BAD_SERVER_DATA, '_request, out of sequence')
                elif seq != next_seq and next_seq is not None:
                    err = ineterr.err(ineterr.BAD_SERVER_DATA, '_request, out of sequence')
                elif seq is not None and seq != 1 and next_seq is None:
                    err = ineterr.err(ineterr.BAD_SERVER_DATA, '_request, out of sequence')
                elif seq is not None:
                    next_seq = seq + 1

                complete = 'R' in subject
                if seq is None and not complete:
                    err = ineterr.err(ineterr.BAD_SERVER_DATA, '_request, invalid seq')
                if err.code != ineterr.SUCCESS and not complete:
                    err = ineterr.err(ineterr.BAD_SERVER_DATA, '_request, pending error')

                if body is not None:
                    yield err, (headers, body)
                else:
                    yield err, None

                if err.code != ineterr.SUCCESS or complete:
                    break
        finally:
            del self._txn_queues[txn_id]

    def _request_one(self, protocol, command, headers, body, timeout):
        iter = self._request(protocol, command, headers, body, timeout)
        err, msg = iter.next()
        if err.code == ineterr.PENDING:
            iter.close()
            return ineterr.err(ineterr.BAD_SERVER_DATA, '_request_one, multi-part response'), None
        return err, msg

    def request_many(self, protocol, command, headers=None, body=None, timeout=None):
        return self._request(protocol, command, headers, body, timeout)

    def request_one(self, protocol, command, headers=None, body=None, timeout=None):
        err, msg = self._request_one(protocol, command, headers, body, timeout)
        if err.code == ineterr.SUCCESS and msg is None:
            return ineterr.err(ineterr.BAD_SERVER_DATA, 'request_one, reply not message'), None
        return err, msg

    def request_none(self, protocol, command, headers=None, body=None, timeout=None):
        err, msg = self._request_one(protocol, command, headers, body, timeout)
        if msg is not None:
            return ineterr.err(ineterr.BAD_SERVER_DATA, 'request_none, message response'), None
        return err
