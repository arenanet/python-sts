python-sts
===============================

## Overview

Communication between clients and servers is through STS, an HTTP-
like protocol. It is important to understand the HTTP format.

For more information about HTTP messages and HTTP in general:

  * [http://www.jmarshall.com/easy/http/](http://www.jmarshall.com/easy/http/)
  * [http://tools.ietf.org/html/rfc2616](http://tools.ietf.org/html/rfc2616)

***Important differences from HTTP***

  * The protocol is STS/1.0 instead of HTTP/1.1
  * The request URI contains two parts, the protocol and command of the request.
  * Compact headers are used, but full headers are also accepted. For example, both 'l' and 'content-length' will be interpreted as the Content-Length header.
  * The Content-Type header is optional and defaults to 'application/xml'.
  * Requests without matching responses are allowed and serve as unidirectional notifications.
  * XML Message bodies must have a trailing LF (CRLF is fine).
  * Messages can be fragmented.

## Types of messages

  * A simple message (or "message") may have more than one destination; for example, a service can send a status message to multiple other services with only one send operation. Further, no response is expected from the services that receive the message, though they may send back other messages if they so choose.
  * A transaction message (or "request") may be sent to only one destination service, and a response is required from the destination during normal operation. If no response is forthcoming the sender MUST synthesize a timeout response; generally after 30 seconds.
  * A reply message (or "reply") is sent only in response to a transaction message, though a single transaction may receive multiple replies (for example: request -> partial reply -> partial reply -> final reply). If a reply is received after a transaction has been completed (for example, due to a synthesized timeout) it MUST be silently dropped.

## Maintaining a connection

If there is no activity over a client connection for a period of time a server
will assume that something has happened to the client and drop the connection.
A client that has nothing to send, but wants to keep the connection open, can
send ping messages. These are ignored except to keep the connection open.

## Transactions

Since replies to requests may be received out of order and with additional
messages mixed in a transaction id is used. The transaction id is set in the
'Subject' or 's' (compact version) header of the request and must be unique
for each message sent by the client that needs a reply. It must be from 1 thru
2^32. If there is no transaction id, or the id is zero, no replies will be sent.

In responses the transaction id is also returned in the 'subject' (or 's').


### Timeouts and reply sequence numbers

Transactions waiting for replies need to timeout to handle cases where
messages are lost or internal errors prevent replies from arriving. Generally
the correct behavior is to ask the user if they want to retry.

If replies arrive out of sequence the client can simply treat it as a failed
timed out transaction, queuing out of sequence replies is possible but
probably doesn't bring very much value since it should be quite rare.

## Error replies

When an error occurs during a transaction, or if just a simple success code is
required, an error reply is sent. The body contains a single Error element,
attributes of the Error element should be treated as zero if they are not
present. It is detected as an error reply if the status code in the start line
is 400 or greater.


## Compact headers

Sts supports the compact form of the RFC 2822 headers as specified in
[http://www.iana.org/assignments/sip-
parameters](http://www.iana.org/assignments/sip-parameters). Some new compact
forms have been defined where official ones did not exist. Compact forms are
optional, and clients do not have to implement support for them. 


## Message size and fragmented messages

Individual messages are limited to a 32K header section and a 64K body,
however content up to 64M can be sent as multiple "fragments". Fragments are
messages that have Content-Range set, must not overlap, can arrive in any
order, and are grouped together to form a "complete" message. The grouping is
done by the transaction id, or the 'X-Sequence' header ('q') if it's not a 
transaction.

