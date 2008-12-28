#!/usr/bin/env python

# Boodler: a programmable soundscape tool
# Designed by Andrew Plotkin <erkyrath@eblong.com>
# For more information, see <http://boodler.org/>
#
# This Python script ("boomsg.py") is in the public domain. 

"""boomsg.py: send events to Boodler
usage: boomsg.py [--hostname host] [--port port] msgname [ msgdata ... ]

The hostname defaults to "localhost". The port defaults to the Boodler
port of 31863. If port is given as an absolute pathname (beginning
with "/"), boomsg uses a Unix domain socket instead of a network socket.
"""

import sys
import getopt
import socket

try:
	(opts, args) = getopt.getopt(sys.argv[1:], 'h:p:', 
		['hostname=', 'port='])
except getopt.error, ex:
	print (sys.argv[0] + ':'), str(ex)
	sys.exit()

host = 'localhost'
port = 31863

for (opname, opval) in opts:
	if (opname == '--port' or opname == '-p'):
		if (opval[0] == '/'):
			port = opval
		else:
			port = int(opval)
	elif (opname == '--hostname' or opname == '-h'):
		host = opval

if (len(args) == 0):
	print 'usage:', sys.argv[0], '[--hostname host] [--port port]', 'msgname [ msgdata ... ]'
	sys.exit()

dat = ' '.join(args) + '\n'

if (type(port) == type(1)):
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.connect((host, port))
else:
	sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	sock.connect(port)
sock.send(dat)
sock.close()

