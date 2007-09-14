# Boodler: a programmable soundscape tool
# Copyright 2002 by Andrew Plotkin <erkyrath@eblong.com>
# <http://www.eblong.com/zarf/boodler/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

__all__ = ['agent', 'generator', 'listen', 'sample', 'stereo', 'music']

class DummyDriver:
	"""A dummy driver class.

	This class exists only so that boodle.cboodle can have a default
	value. The behavior of the dummy is to throw an exception when
	any method is called.
	"""
	def __repr__(self):
		return '<boodle.DummyDriver>'
	def __str__(self):
		return '<boodle.DummyDriver>'
	def __getattr__(self, key):
		raise Exception('No Boodler output driver has been selected.')

# Create the default dummy driver object.
cboodle = DummyDriver()

def set_driver(key):
	"""set_driver(key) -> module

	Select a Boodler driver. The key must be one of the installed driver
	keys ('file', etc). This returns the selected driver. It also
	sets boodle.cboodle, and the cboodle property in the other Boodler
	classes that make use of it.

	If the driver is not available, this raises ImportError.
	"""
	global cboodle
	
	print '### setting driver to', key
	modname = 'cboodle_'+key
	selfmod = __import__('boodle.'+modname)
	driver = getattr(selfmod, modname)

	import boodle.agent, boodle.generator, boodle.sample
	cboodle = driver
	agent.cboodle = driver
	generator.cboodle = driver
	sample.cboodle = driver
	return driver
