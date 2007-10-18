# Boodler: a programmable soundscape tool
# Copyright 2002-7 by Andrew Plotkin <erkyrath@eblong.com>
# <http://eblong.com/zarf/boodler/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

import sys
import socket
import select
import os
import fcntl
import errno

class SocketListener:

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

	def __init__(self, handler):
		self.handler = handler
		
		self.blockerrors = [ errno.EAGAIN, errno.EWOULDBLOCK ]
		self.data = ''
		
		self.origflags = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
		fcntl.fcntl(sys.stdin, fcntl.F_SETFL, os.O_NONBLOCK | self.origflags)

	def close(self):
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
