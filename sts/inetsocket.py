# -*- coding: utf-8 -*-

import Queue     as pqueue
import socket    as psocket
import threading as pthread
import itertools as it
from . import inetheaders, inetmsg, ineterr

AUTO_PING_SECONDS = 5.0

class Socket(object):

    def __init__(self, socket):

        self._txn_id     = it.count(start = 1)
        self._txn_queues = {}

        self._socket = None
        self.attach_socket(socket)

    def is_closed(self):
        return self._cancel.is_set()

    def detach_socket(self):
        assert self._socket, 'Invalid Socket State'

        self._cancel.set()
        self._read_thread.join()
        self._send_thread.join()

        socket, self._socket = self._socket, None
        return socket

    def attach_socket(self, socket):
        assert not self._socket, 'Invalid Socket State'

        self._socket = socket
        self._socket.settimeout(AUTO_PING_SECONDS)

        self._cancel      = pthread.Event()
        self._send_queue  = pqueue.Queue()
        self._send_thread = pthread.Thread(target = self._send_worker, args = (socket, self._send_queue, self._cancel))
        self._send_thread.daemon = True;
        self._send_thread.start()

        self._read_queue  = pqueue.Queue()
        self._read_thread = pthread.Thread(target = self._read_worker, args = (socket, self._read_queue, self._cancel))
        self._read_thread.daemon = True;
        self._read_thread.start()

    def _read_worker(self, socket, queue, cancel):

        fd = socket.makefile('rb')

        while (not cancel.is_set()):

            start_line = False
            headers    = False
            body       = False

            try:
                start_line, headers, body = inetmsg.read_message(fd)

            except psocket.timeout:
                continue

            except:
                cancel.set()
                continue

            if (isinstance(start_line, inetmsg.StatusLine)):

                if (not self._handle_response(start_line, headers, body, cancel)):
                    queue.put((start_line, headers, body), False)

    def _handle_response(self, start_line, headers, body, cancel):

        try:
            subject = headers.get(inetheaders.SUBJECT, 0)
            subject = subject.lower()
            txn_id  = subject.split(';')[0]
            txn_id  = int(txn_id.split('r')[0])

        except ValueError:
            cancel.set()

        if (txn_id in self._txn_queues):
            self._txn_queues[txn_id].put((start_line, headers, body), False)
            return True

        return False

    def _read(self, queue, timeout):

        start_line, headers, body = queue.get(timeout = timeout)

        if (isinstance(start_line, inetmsg.StatusLine)):

            if (start_line.code >= 400):
                err = ineterr.parse_error(body)

                if err.code == ineterr.PENDING:
                    err = ineterr.err(ineterr.BAD_SERVER_DATA, '_read, received PENDING')

                body = None

            else:
                err = ineterr.err(ineterr.SUCCESS)

        return err, start_line, headers, body

    def read(self, timeout = None):

        while True:

            try:
                err, start_line, headers, body = self._read(self._read_queue, timeout)

            except pqueue.Empty:
                return None

            if (isinstance(start_line, inetmsg.StatusLine)):
                err = ineterr.err(ineterr.BAD_SERVER_DATA, 'read, received status')

            if (body is None):
                continue

            try:
                __, protocol, command = start_line.uri.split('/')

            except ValueError:
                continue

            return (protocol, command, headers, body)

    def _send_worker(self, socket, queue, cancel):

        while (not cancel.is_set()):

            try:
                start_line, headers, body = queue.get(timeout = AUTO_PING_SECONDS)
                socket.sendall(inetmsg.build_message(start_line, headers, body))

            except pqueue.Empty:
                self._send(queue, inetmsg.RequestLine(method = 'P', uri='/Sts/Ping'))

    def _send(self, queue, start_line, headers = False, body = False):

        headers      = headers if headers else {}
        body         = body if body else ''
        content_type = headers.get(inetheaders.CONTENT_TYPE, 'application/xml')

        if (content_type == 'application/xml'):
            body += '\n'

        if (len(body) > 0):
            headers[inetheaders.CONTENT_LENGTH] = str(len(body))

        elif (inetheaders.CONTENT_LENGTH in headers):
            del headers[inetheaders.CONTENT_LENGTH]

        queue.put((start_line, headers, body))

    def send(self, protocol, command, headers = False, body = False):

        request_line = inetmsg.RequestLine(method='P', uri='/%s/%s' % (protocol, command))
        self._send(self._send_queue, request_line, headers, body)

    def _request(self, protocol, command, headers = False, body = False, timeout = None):

        txn_id                   = self._txn_id.next()
        self._txn_queues[txn_id] = pqueue.Queue()

        headers = headers if headers else {}
        headers[inetheaders.SUBJECT] = str(txn_id)

        self.send(protocol, command, headers, body)

        try:

            body_result = False
            next_seq = False
            while True:

                try:
                    err, start_line, headers, body = self._read(self._txn_queues[txn_id], timeout)

                except pqueue.Empty:
                    yield ineterr.err(ineterr.TIMEOUT), None
                    break

                if (isinstance(start_line, inetmsg.RequestLine)):
                    err = ineterr.err(ineterr.BAD_SERVER_DATA, '_request, received request')

                subject = headers[inetheaders.SUBJECT].split(';')[0]

                try:
                    __, seq = subject.lower().split('r')
                    seq = int(seq) if seq else False

                except ValueError:
                    err = ineterr.err(ineterr.BAD_SERVER_DATA, '_request, malformed subject')

                if (not seq and next_seq):
                    err = ineterr.err(ineterr.BAD_SERVER_DATA, '_request, out of sequence')
                elif (next_seq and seq != next_seq):
                    err = ineterr.err(ineterr.BAD_SERVER_DATA, '_request, out of sequence')
                elif (seq and seq != 1 and not next_seq):
                    err = ineterr.err(ineterr.BAD_SERVER_DATA, '_request, out of sequence')
                elif (seq):
                    next_seq = seq + 1

                complete = 'R' in subject
                if (not seq and not complete):
                    err = ineterr.err(ineterr.BAD_SERVER_DATA, '_request, invalid seq')

                if (err.code != ineterr.SUCCESS and not complete):
                    err = ineterr.err(ineterr.BAD_SERVER_DATA, '_request, pending error')

                if (inetheaders.CONTENT_RANGE in headers):

                    raw_range       = headers[inetheaders.CONTENT_RANGE]
                    type_segments   = raw_range.split(' ')
                    range_segments  = type_segments[1].split('/')
                    numerator_range = range_segments[0].split('-')
                    start_range     = int(numerator_range[0])
                    end_range       = int(numerator_range[1])
                    denominator     = int(range_segments[1])

                    if (start_range == 0):
                        body_result = body
                    else:
                        body_result += body

                    if ((end_range + 1) == denominator):

                        if (not len(body_result) == denominator):
                            err = ineterr.err(ineterr.BAD_SERVER_DATA, '_request, invalid chunked result')

                        yield err, (headers, body_result)

                    continue

                if (body):
                    yield err, (headers, body)
                else:
                    yield err, None

                if (err.code != ineterr.SUCCESS or complete):
                    break

        finally:
            del self._txn_queues[txn_id]


    def _request_one(self, protocol, command, headers, body, timeout):

        iter     = self._request(protocol, command, headers, body, timeout)
        err, msg = iter.next()

        if (err.code == ineterr.PENDING):
            iter.close()
            return ineterr.err(ineterr.BAD_SERVER_DATA, '_request_one, multi-part response'), None

        return err, msg

    def request_many(self, protocol, command, headers = False, body = False, timeout = None):

        return self._request(protocol, command, headers, body, timeout)

    def request_one(self, protocol, command, headers = False, body = False, timeout = None):

        err, msg = self._request_one(protocol, command, headers, body, timeout)

        if (err.code == ineterr.SUCCESS and not msg):
            return ineterr.err(ineterr.BAD_SERVER_DATA, 'request_one, reply not message'), None

        return err, msg

    def request_none(self, protocol, command, headers = False, body = False, timeout = None):

        err, msg = self._request_one(protocol, command, headers, body, timeout)

        if (msg):
            return ineterr.err(ineterr.BAD_SERVER_DATA, 'request_none, message response'), None

        return err
