# Boodler: a programmable soundscape tool
# Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

"""listen: A module containing ways for Boodler to listen to external
events.

SocketListener -- listen for events on an Internet or Unix domain socket
StdinListener -- listen for events on stdin

(Logically these are subclasses of a base Listener class, but I didn't
implement it that way.)
"""

import sys
import socket
import select
import os
import errno

class SocketListener:
    """SocketListener: Listen for events on an Internet or Unix domain socket.

    This opens a socket; external processes can connect and send Boodler
    events to it. You can open either Internet sockets (with a numeric
    port number), or Unix domain sockets. (Unix sockets exist as a "file"
    on disk; only processes on the same machine can connect to a Unix
    socket.)

    SocketListener(handler, listenport=31863) -- constructor

    The socket is opened as soon as the SocketListener is constructed.
    If listenport is an integer, this will be an Internet socket. If
    listenport is a string, it will be a Unix domain socket.

    Events will be sent to the handler function.

    Public methods:

    poll() -- read as many events as are available
    close() -- close the socket
    """

    unlinkport = None

    def __init__(self, handler, listenport=None):
        if (listenport == None):
            listenport = 31863
        if (type(listenport) in [int, long]):
            insock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sockaddr = ('localhost', listenport)
        else:
            insock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sockaddr = str(listenport)
            self.unlinkport = sockaddr
        insock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, (insock.getsockopt (socket.SOL_SOCKET, socket.SO_REUSEADDR) | 1))
        insock.bind(sockaddr)
        insock.listen(32)
        self.insock = insock
        self.sockets = [insock]
        self.handler = handler
        self.datas = {}
        self.active = True

    def close(self):
        for sock in self.sockets:
            sock.close()
        self.socket = None
        self.insock = None
        self.active = False
        if (self.unlinkport != None):
            os.unlink(self.unlinkport)

    def poll(self):
        while (True):
            (readls, writels, exls) = select.select(self.sockets, [], [], 0)
            if (len(readls) == 0):
                return
            for sock in readls:
                if (sock == self.insock):
                    (newsock, addr) = sock.accept()
                    newsock.setblocking(0)
                    self.datas[newsock] = ''
                    self.sockets.append(newsock)
                else:
                    dat = sock.recv(1024)
                    if (len(dat) == 0):
                        sock.close()
                        del self.datas[sock]
                        self.sockets.remove(sock)
                    else:
                        dat = dat.replace('\r', '\n')
                        dat = self.datas[sock] + dat
                        dat = handle_by_lines(self.handler, dat)
                        self.datas[sock] = dat

class StdinListener:
    """StdinListener: Listen for events arriving on standard input.

    This is intended for when Boodler is running as a subordinate process
    in some other program. The hosting program can write event data in
    to Boodler.

    NOTE: This does not currently work on Windows, because the fcntl
    module is not available.

    StdinListener(handler) -- constructor

    Events will be sent to the handler function.

    Public methods:

    poll() -- read as many events as are available
    close() -- close the socket
    """
    
    def __init__(self, handler):
        # We import fcntl only when needed, because it's not available on
        # all platforms.
        import fcntl
        
        self.handler = handler
        
        self.blockerrors = [ errno.EAGAIN, errno.EWOULDBLOCK ]
        self.data = ''
        
        self.origflags = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, os.O_NONBLOCK | self.origflags)

    def close(self):
        import fcntl
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, self.origflags)

    def poll(self):
        try:
            dat = sys.stdin.read()
        except IOError, ex:
            (errnum, errstr) = ex
            if (errnum in self.blockerrors):
                return
            else:
                raise
        dat = self.data + dat
        dat = handle_by_lines(self.handler, dat)
        self.data = dat
    
                        
def handle_by_lines(handler, dat):
    """handle_by_lines(handler, dat) -> str

    Take an input buffer, parse as many events out of it as possible,
    handle them, and return the remainder. For each valid event, the
    handler argument will be called with the event tuple for an
    argument.

    An event is a newline-terminated string (which is not just whitespace).
    So the returned value will be the remainder after the last newline.
    The event line is split on whitespace, producing a tuple of strings.
    """
    
    while (True):
        pos = dat.find('\n')
        if (pos < 0):
            return dat
        message = dat[ : pos ].strip()
        dat = dat[ pos+1 : ]

        if (not message):
            continue
        try:
            ev = message.split()
            ev[0] = boodle.check_prop_name(ev[0])
            handler(tuple(ev))
        except:
            pass

# Late imports
import boodle
