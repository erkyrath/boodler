#!/usr/bin/env python

from distutils.core import setup, Extension
from distutils.command.build_ext import build_ext

class local_build_ext(build_ext):
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
		
ext_cboodle = Extension('boodle.cboodle',
	['cboodle/audev-file.c', 'cboodle/cboodle.c', 'cboodle/noteq.c', 'cboodle/sample.c']
)

setup(name = 'Boodler',
	version = '1.6.0',
	description = 'Programmable soundscape tool',
	author = 'Andrew Plotkin',
	author_email = 'erkyrath@eblong.com',
	url = 'http://boodler.org/',
	packages = ['boodle'],
	scripts = ['boodler.py', 'boomsg.py'],
	ext_modules = [ext_cboodle],
	cmdclass = {'build_ext':local_build_ext},
)
