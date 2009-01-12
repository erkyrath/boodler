#!/usr/bin/env python

# Boodler: a programmable soundscape tool
# Designed by Andrew Plotkin <erkyrath@eblong.com>
# For more information, see <http://boodler.org/>
#
# This Python script ("boodle-event.py") is in the public domain. 

"""boodle-event.py: send events to Boodler
usage: boodle-event.py [--hostname host] [--port port] evname [ evdata ... ]

Send an event to a listening Boodler process.

The hostname defaults to "localhost". The port defaults to the Boodler
port of 31863. If port is given as an absolute pathname (beginning
with "/"), boodle-event uses a Unix domain socket instead of a network
socket.
"""

import sys
import os.path
import optparse
import socket

usage = 'usage: %prog [--hostname host] [--port port] evname [ evdata ... ]'

popt = optparse.OptionParser(usage=usage)

popt.add_option('-H', '--hostname',
    action='store', type='string', dest='hostname', metavar='HOST',
    help='Boodler host to send event to (default: localhost)')
popt.add_option('-p', '--port',
    action='store', type='string', dest='port', metavar='PORT/PIPE',
    help='Port (or Unix pipe) to send event to (default: port 31863)')

popt.set_defaults(hostname='localhost', port='31863')

(opts, args) = popt.parse_args()

host = opts.hostname
if (opts.port.startswith('/')):
    port = opts.port
    use_tcp = False
    if (host != 'localhost'):
        print 'Cannot write to a Unix pipe on a different host.'
        sys.exit(1)
else:
    try:
        port = int(opts.port)
        use_tcp = True
    except:
        print 'Port must be an absolute pathname or an integer.'
        sys.exit(1)

if (len(args) == 0):
    print usage.replace('%prog', os.path.basename(sys.argv[0]))
    sys.exit()

dat = ' '.join(args) + '\n'

if (use_tcp):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
else:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(port)
sock.send(dat)
sock.close()

