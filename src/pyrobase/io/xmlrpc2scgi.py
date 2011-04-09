""" PyroBase - XMLRPC via SCGI client proxy over various transports.

    Copyright (c) 2011 The PyroScope Project <pyroscope.project@gmail.com>

    Losely based on code Copyright (C) 2005-2007, Glenn Washburn <crass@berlios.de>
    SSH tunneling back-ported from https://github.com/Quantique

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with this program; if not, write to the Free Software Foundation, Inc.,
    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""
import os
import time
import socket
import urllib2
import urlparse
import xmlrpclib

# Types of exceptions thrown
ERRORS = (urllib2.URLError, xmlrpclib.Fault, socket.error)


#
# SCGI transports
#

class LocalTransport(object):
    """ Transport via TCP or a UNIX domain socket.
    """

    # Amount of bytes to read at once
    CHUNK_SIZE = 32768

    
    def __init__(self, url):
        self.url = url
        
        if url.netloc:
            # TCP socket
            addrinfo = list(set(socket.getaddrinfo(url.hostname, url.port, socket.AF_INET, socket.SOCK_STREAM)))
            if len(addrinfo) != 1:
                raise urllib2.URLError("Host of URL %r resolves to multiple addresses" % url.geturl())

            self.sock = socket.socket(*addrinfo[0][:3])
            self.sock_addr = addrinfo[0][4] 
        else:
            # UNIX domain socket
            path = url.path
            if path.startswith("/~"):
                path = os.path.expanduser(path)
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock_addr = os.path.abspath(path) 


    def send(self, data):
        """ Open transport, send data, and yield response chunks.
        """
        try:
            self.sock.connect(self.sock_addr)
        except socket.error, exc:
            raise socket.error("Can't connect to %r (%s)" % (self.url.geturl(), exc))
        
        try:
            # Send request        
            self.sock.send(data)

            # Read response
            while True:
                chunk = self.sock.recv(self.CHUNK_SIZE)
                if chunk:
                    yield chunk
                else:
                    break
        finally:
            # Clean up
            self.sock.close()


TRANSPORTS = {
    "scgi": LocalTransport,
    #"scgi+ssh": ,
}

# Register our schemes to be parsed as having a netloc
urlparse.uses_netloc.extend(TRANSPORTS.keys())


def transport_from_url(url):
    """ Create a transport for the given URL.
    """
    url = urlparse.urlsplit(url, "scgi", allow_fragments=False)

    try:
        transport = TRANSPORTS[url.scheme.lower()]
    except KeyError:
        if not any((url.netloc, url.query)) and url.path.isdigit():
            # Support simplified "domain:port" URLs
            return transport_from_url("scgi://%s:%s" % (url.scheme, url.path))
        else:
            raise urllib2.URLError("Unsupported scheme in URL %r" % url.geturl())
    else:
        return transport(url)


#
# Helpers to handle SCGI data
# See spec at http://python.ca/scgi/protocol.txt
#

def _encode_netstring(text):
    "Encode text as netstring."
    return "%d:%s," % (len(text), text)


def _encode_headers(headers):
    "Make SCGI header bytes from list of tuples."
    return ''.join(['%s\0%s\0' % i for i in headers])


def _encode_payload(data, headers=None):
    "Wrap data in an SCGI request."
    prolog = "CONTENT_LENGTH\0%d\0SCGI\x001\0" % len(data)
    if headers:
        prolog += _encode_headers(headers)
    
    return _encode_netstring(prolog) + data


def _parse_headers(headers):
    "Get headers dict from header string."
    return dict(line.rstrip().split(": ", 1)
        for line in headers.splitlines()
        if line
    )


def _parse_response(resp):
    """ Get xmlrpc response from scgi response
    """
    # Assume they care for standards and send us CRLF (not just LF)
    headers, payload = resp.split("\r\n\r\n", 1)
    headers = _parse_headers(headers)

    clen = headers.get("Content-Length")
    if clen is not None:
        # Check length, just in case the transport is bogus
        assert len(payload) == int(clen) 
    
    return payload, headers


#
# SCGI request handling
#
class SCGIRequest(object):
    """ Send a SCGI request.
        See spec at "http://python.ca/scgi/protocol.txt".
        
        Use tcp socket
        SCGIRequest('scgi://host:port').send(data)
        
        Or use the named unix domain socket
        SCGIRequest('scgi:///tmp/rtorrent.sock').send(data)
    """

    def __init__(self, url_or_transport):
        try:
            self.transport = transport_from_url(url_or_transport + "")
        except TypeError: 
            self.transport = url_or_transport

        self.resp_headers = {}
        self.latency = 0.0

    
    def send(self, data):
        """ Send data over scgi to URL and get response.
        """
        start = time.time()
        try:
            scgi_resp = ''.join(self.transport.send(_encode_payload(data)))
        finally:
            self.latency = time.time() - start

        resp, self.resp_headers = _parse_response(scgi_resp)
        return resp


def scgi_request(url, methodname, deserialize=False, *params):
    """ Send a XMLRPC request over SCGI to the given URL.

        @param url: Endpoint URL.
        @param methodname: XMLRPC method name.
        @param params: tuple of simple python objects.
        @param deserialize: parse XML result? 
        @return: XMLRPC response, or the equivalent Python data.
    """
    xmlreq = xmlrpclib.dumps(params, methodname)
    xmlresp = SCGIRequest(url).send(xmlreq)
    
    if deserialize:
        # This fixes a bug with the Python xmlrpclib module
        # (has no handler for <i8> in some versions)
        xmlresp = xmlresp.replace("<i8>", "<i4>").replace("</i8>", "</i4>")

        # Return deserialized data
        return xmlrpclib.loads(xmlresp)[0][0]
    else:
        # Return raw XML
        return xmlresp