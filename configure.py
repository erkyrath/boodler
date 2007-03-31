#!/usr/bin/python

import sys
import os
import os.path
import string
import getopt

usagemessage = 'usage: ' + sys.argv[0] + ' [-d NAME] [-i] [-I /dir/path] [-L /dir/path] [-l]'
usagemessage = usagemessage + '\n   or: ' + sys.argv[0] + ' [--driver NAME] [--integer] [--include /dir/path] [--lib /dir/path] [--list]'

helpmessage = 'Boodler configuration script\n\n' + usagemessage + '''

This script attempts to determine what sound drivers and libraries are
available on your machine, so that Boodler can compile itself. Boodler
currently supports five interfaces:

  OSS (the Open Sound System) is a low-level sound driver. If you build
  Boodler to use OSS, it will monopolize the sound hardware -- no other
  sound-producing program will be able to run.

  ALSA (the Advanced Linux Sound Architecture) is a more modern and
  powerful sound driver. As with OSS, only one ALSA program can use the
  sound hardware at a time. (ALSA is designed to emulate OSS, so if your
  machine has ALSA installed, you can probably build Boodler using
  either the OSS or ALSA interfaces.)

  ESD (EsounD, the "Enlightened Sound Daemon") is a more flexible
  system. Many programs can use the ESD sound interface on your computer
  at the same time. However, the ESD form of Boodler will use somewhat
  more CPU time. (Also, ESD is kind of junky and unsupported. I never
  liked it much.)

  MACOSX (MacOSX CoreAudio) uses the CoreAudio framework. This is the
  configuration you will likely want under MacOSX. (Although ESD should
  also work, if you're running the MacOSX port of ESD.)

  FILE (direct file dump) simply dumps raw sound data straight to a
  file on disk. You can use a sound editor or translator, such as sox,
  to change the data to another format.

If you don't care about the difference, just type
  python configure.py
The configure script will pick one (trying them in the order given)
and set up Boodler for compilation. You can then type
  make
...and then begin testing Boodler, as described in the documentation.

To list which interfaces will work, type
  python configure.py -l
To pick a particular interface, type (for example)
  python configure.py -d alsa

The configure script determines which interfaces are available by
searching for header files. It looks for header files and libraries in
the standard locations (/usr/include, /usr/local/include, /usr/lib,
/usr/local/lib). If your sound header files are in a different
location, you will have to tell the configure script:
  python configure.py -I/usr/contrib/include -L/usr/contrib/include
The configure script will search the given directories, and will also
build them into the Makefile so that Boodler can find them when
compiling.

To build Boodler to prefer integer computation over floating-point, type
  python configure.py -i
(This reduces the number of floating-point operations in the rendering
loop, but does not eliminate them entirely.)
'''

try:
	(opts, args) = getopt.getopt(sys.argv[1:], 'd:I:L:lih', 
		['driver=', 'include=', 'lib=', 'list', 'integer', 'help'])
except getopt.error, ex:
	print (sys.argv[0] + ':'), str(ex)
	print usagemessage
	sys.exit()

if (len(args) > 0):
	print usagemessage
	sys.exit()

driver = None
showhelp = 0
listdrivers = 0
headerpath = ['/usr/local/include', '/usr/include']
libpath = ['/usr/local/lib', '/usr/lib']
extraheaders = []
extralibs = []
cflagopts = ''

for (opname, opval) in opts:
	if (opname == '--driver' or opname == '-d'):
		driver = string.lower(opval)
	if (opname == '--integer' or opname == '-i'):
		cflagopts = cflagopts + ' -DBOODLER_INTMATH'
	if (opname == '--help' or opname == '-h'):
		showhelp = 1
	if (opname == '--list' or opname == '-l'):
		listdrivers = 1
	if (opname == '--include' or opname == '-I'):
		extraheaders.append(opval)
	if (opname == '--lib' or opname == '-L'):
		extralibs.append(opval)

headerpath = extraheaders + headerpath
libpath = extralibs + libpath
pyheader = sys.prefix + '/include/python' + sys.version[:3]
drivers = {}

if (showhelp):
	print helpmessage
	sys.exit()

class Driver:
	def __init__(self):
		drivers[self.name] = self
	def available(self):
		return 0
	libs = ''

class OSSDriver(Driver):
	name = 'oss'
	fullname = 'Open Sound System sound driver'
	def available(self):
		for dir in headerpath:
			name = os.path.join(dir, 'sys')
			name = os.path.join(name, 'soundcard.h')
			if (os.access(name, os.R_OK)):
				return 1
		return 0

class ESDDriver(Driver):
	name = 'esd'
	fullname = 'Enlightened Sound Daemon (EsounD)'
	def available(self):
		for dir in headerpath:
			name = os.path.join(dir, 'esd.h')
			if (os.access(name, os.R_OK)):
				return 1
		return 0
	libs = '-lesd'

class ALSADriver(Driver):
	name = 'alsa'
	fullname = 'Advanced Linux Sound Architecture sound driver'
	def available(self):
		for dir in headerpath:
			name = os.path.join(dir, 'sys')
			name = os.path.join(name, 'asoundlib.h')
			if (os.access(name, os.R_OK)):
				return 1
		return 0
	libs = '-lasound'

class FileDriver(Driver):
	name = 'file'
	fullname = 'write to disk file'
	def available(self):
		return 1

class MacOSXDriver(Driver):
	name = 'macosx'
	fullname = 'MacOSX CoreAudio'
	def available(self):
		if (sys.platform == 'darwin'):
			return 1
		return 0
	libs = '-framework Carbon'

driverlist = [ 
	OSSDriver(), ALSADriver(), MacOSXDriver(), ESDDriver(), FileDriver() 
]

if (listdrivers):
	worklist = filter((lambda driv: driv.available()), driverlist)
	if (len(worklist) == 0):
		print 'None of Boodler\'s sound drivers seem to be compatible with your OS. Sorry.'
	else:
		print str(len(worklist)) + ' of Boodler\'s sound drivers are compatible with your OS:'
		for driv in worklist:
			print '  ' + driv.name + ': ' + driv.fullname
	sys.exit()

if (driver == None):
	worklist = filter((lambda driv: driv.available()), driverlist)
	if (len(worklist) == 0):
		print 'None of Boodler\'s sound drivers seem to be compatible with your OS. Sorry.'
		sys.exit()
	driv = worklist[0]
else:
	driv = drivers.get(driver)
	if (driv == None):
		print '"' + driver + '" is not one of Boodler\'s sound drivers. Try configure --list.'
		sys.exit()
	if (driv.available() == 0):
		print '"' + driv.name + '" (' + driv.fullname + ') is not compatible with your OS. Try configure --list.'
		sys.exit()

print 'Configuring Boodler for ' + driv.name + ': ' + driv.fullname

fl = open(os.path.join('cboodle', 'Makefile-template'))
makefile = fl.read()
fl.close()

makefile = string.replace(makefile, '@@PYTHONINCLUDE', pyheader)
val = ''
for dir in extraheaders:
	val = val + ' -I' + dir
makefile = string.replace(makefile, '@@EXTRAINCLUDE', val)
val = ''
for dir in extralibs:
	val = val + ' -L' + dir
makefile = string.replace(makefile, '@@EXTRALIB', val)
makefile = string.replace(makefile, '@@AUDEVOBJ', ('audev-'+driv.name+'.o'))
makefile = string.replace(makefile, '@@LIBS', driv.libs)
makefile = string.replace(makefile, '@@CFLAGOPTS', cflagopts)
val = 'ld -Bshareable'
if (sys.platform == 'darwin'):
	if (string.find(sys.prefix, 'Python.framework') >= 0):
		val = 'cc -Wl,-F. -Wl,-flat_namespace,-U,_environ -bundle -framework Python'
	else:
		val = 'cc -bundle -flat_namespace -undefined suppress'
makefile = string.replace(makefile, '@@LINKSHARE', val)

fl = open(os.path.join('cboodle', 'Makefile'), 'w')
fl.write(makefile)
fl.close()
