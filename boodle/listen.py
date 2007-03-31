# Boodler: a programmable soundscape tool
# Copyright 2002 by Andrew Plotkin <erkyrath@eblong.com>
# <http://www.eblong.com/zarf/boodler/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

import string
import socket
import select
import os

class Listener:

	unlinkport = None

	def __init__(self, handler, listenport=None):
		if (listenport == None):
			listenport = 31863
		if (type(listenport) == type(1)):
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
		self.active = 1

	def close(self):
		for sock in self.sockets:
			sock.close()
		self.socket = None
		self.insock = None
		self.active = 0
		if (self.unlinkport != None):
			os.unlink(self.unlinkport)

	def poll(self):
		while (1):
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
						dat = string.replace(dat, '\015', '\012')
						dat = self.datas[sock] + dat
						while (1):
							linepos = string.find(dat, '\012')
							if (linepos < 0):
								break
							message = string.strip(dat[:linepos])
							dat = string.lstrip(dat[linepos:])
							self.handler(message)
						self.datas[sock] = dat
