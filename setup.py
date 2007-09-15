#!/usr/bin/env python

import sys
import os.path
import re
from distutils.core import setup, Command, Extension
from distutils.command.build_ext import build_ext
from distutils.command.build_scripts import build_scripts
from distutils.errors import *
from distutils.util import convert_path
import distutils.log

def check_header_available(path):
	"""check_header_available(path) -> func(includedirs) -> bool

	Determine whether the given header is available in any of the
	configured include directories. The path should be in the usual
	C format: relative, forward slashes. (E.g.: 'sys/time.h')

	This function is curried. check_header_available(path) does not
	return a result; instead, it returns a function f(ls) which you
	can call when you have a list of include directories to check.
	The f(ls) function is what returns the boolean result.
	"""
	
	pathels = path.split('/')
	def func(ls):
		for dir in ls:
			filename = os.path.join(dir, *pathels)
			if (os.path.isfile(filename)):
				return True
		distutils.log.info("unable to locate header '%s'", path)
		return False
	return func

class BooExtension(Extension):
	"""BooExtension: A distutils.Extension class customized for Boodler
	driver extensions.

	Since all the drivers have nearly the same list of source files,
	this class generates the list at init time. You don't need to
	pass the source list in.

		BooExtension(key, available=bool) -- constructor

	The keyword argument 'available', if provided, must indicate
	whether the extension can be built. If not provided, True is
	assumed.
	"""
	
	def __init__(self, key, **opts):
		self.boodler_key = key
		modname = 'boodle.cboodle_'+key
		
		ls = ['audev-'+key, 'cboodle-'+key, 'noteq', 'sample']
		ls = [ ('cboodle/' + val + '.c') for val in ls ]

		avail = opts.pop('available', None)
		if (avail):
			self.ext_available = avail

		Extension.__init__(self, modname, ls, **opts)

	def ext_available(self, headerlist):
		return True
		
# The list of driver extensions.
all_extensions = [

	BooExtension('file'),
	
	BooExtension('oss',
		available = check_header_available('sys/soundcard.h'),
	),
	
	BooExtension('esd',
		libraries = ['esd'],
		available = check_header_available('esd.h'),
	),
	
	BooExtension('alsa',
		libraries = ['asound'],
		available = check_header_available('sys/asoundlib.h'),
	),
	
	BooExtension('macosx',
		extra_link_args = ['-framework', 'Carbon', '-framework', 'Python'],
		available = (lambda ls : (sys.platform == 'darwin')),
	),
]

class local_build_ext(build_ext):
	"""local_build_ext: A customization of the distutils build_ext
	command.

	This command understands an additional boolean argument:
	
		--intmath (use integer math for audio mixing)
		--floatmath (use floating-point math for audio mixing)
		
	The default is --floatmath. You can pass these arguments on
	the command line, or modify setup.cfg.

	This command also checks each extension before building, to make
	sure the appropriate headers are available. (Or whatever test
	the extension provides.)
	"""
	
	user_options = (build_ext.user_options + [
		('intmath', None, 'audio mixing uses integer math'),
		('floatmath', None, 'audio mixing uses floating-point math (default)'),
	])
	boolean_options = (build_ext.boolean_options + [ 'intmath' ])
	negative_opt = {'floatmath' : 'intmath'}
	
	def initialize_options(self):
		build_ext.initialize_options(self)
		self.intmath = None

	def finalize_options(self):
		if (self.intmath):
			# Add BOODLER_INTMATH to the compiler macros.
			if (not self.define):
				self.define = 'BOODLER_INTMATH'
			else:
				self.define = self.define + ',BOODLER_INTMATH'
		
		build_ext.finalize_options(self)

	def build_extension(self, ext):
		# First check whether the extension is buildable. Mostly this
		# involves looking at the available headers, so put together
		# a list of include dirs.
		
		ls = [ '/usr/include', '/usr/local/include' ]
		ls = ls + self.include_dirs + ext.include_dirs

		if (not ext.ext_available(ls)):
			distutils.log.info("skipping '%s' extension", ext.name)
			return
		
		build_ext.build_extension(self, ext)

class local_build_scripts(build_scripts):
	"""local_build_scripts: A customization of the distutils 
	build_scripts command.

	This command understands an additional argument:

		--default-driver KEY (default Boodler output driver)

	This modifies the boodler.py script as it is built, to use
	the given value as a default driver. You can pass this argument 
	on the command line, or modify setup.cfg.

	If you do not set --default-driver, the default default driver
	will be 'macosx' (on MacOS) or 'oss' (otherwise).
	"""

	user_options = (build_scripts.user_options + [
		('default-driver=', None, 'default Boodler output driver'),
	])

	def initialize_options(self):
		build_scripts.initialize_options(self)
		self.default_driver = None

	def finalize_options(self):
		build_scripts.finalize_options(self)

	def copy_scripts(self):
		build_scripts.copy_scripts(self)
		if (self.default_driver):
			# If a driver was configured in, modify the boodler.py script.
			for script in self.scripts:
				if (script != 'boodler.py'):
					continue
				script = convert_path(script)
				outfile = os.path.join(self.build_dir, os.path.basename(script))
				distutils.log.info('modifying %s to have %s as the default driver', outfile, self.default_driver)
				try:
					fl = open(outfile, 'r')
					val = fl.read()
					fl.close()
					if ('CONFIGUREDDRIVER' in val):
						srcpat = "'[^']*'\\s*#\\s*CONFIGUREDDRIVER"
						destpat = "'" + self.default_driver + "' # CONFIGUREDDRIVER"
						val = re.sub(srcpat, destpat, val)
						fl = open(outfile, 'w')
						fl.write(val)
						fl.close()
				except IOError:
					pass

class local_generate_source(Command):
	"""local_generate_source: A special command to generate cboodle-*.c
	source files.

	Every driver module needs a different cboodle-*.c source file. They
	are nearly identical; the only difference is a few symbol names.
	It is therefore convenient to generate them from a template, called
	cboodle.c.

	The generate_source command is not in the "build" or "install" pipeline,
	because I ran it before I distributed the source. You should already
	have a bunch of cboodle-*.c files. If you run this command, they'll
	be rewritten, but they won't be any different.
	"""
	
	description = "generate extra source files (not needed for build/install)"
	user_options = []
	
	def initialize_options(self):
		pass
	def finalize_options(self):
		pass
	def run(self):
		# Generate all the extensions, not just the available ones.
		for ext in all_extensions:
			key = ext.boodler_key
			barename = 'cboodle-'+key+'.c'
			destfile = None
			for val in ext.sources:
				if (val.endswith(barename)):
					destfile = val
					break
			if (not destfile):
				raise DistutilsSetupError('Boodler extension ' + key + ' does not have a ' + barename + ' source.')
			srcfile = destfile[ : -len(barename) ] + 'cboodle.c'

			distutils.log.info("building '%s' extension at '%s'", key, destfile)

			infl = open(srcfile, 'rU')
			outfl = open(destfile, 'wU')
			while True:
				ln = infl.readline()
				if (not ln):
					break
				ln = ln.replace('$MODBASE$', key)
				outfl.write(ln)
			outfl.close()
			infl.close()
				

setup(name = 'Boodler',
	version = '1.6.0',
	description = 'Programmable soundscape tool',
	author = 'Andrew Plotkin',
	author_email = 'erkyrath@eblong.com',
	url = 'http://boodler.org/',
	packages = ['boodle'],
	scripts = ['boodler.py', 'boomsg.py'],
	ext_modules = list(all_extensions),
	cmdclass = {
		'build_ext': local_build_ext,
		'build_scripts': local_build_scripts,
		'generate_source': local_generate_source,
	},
)
