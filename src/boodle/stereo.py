# Boodler: a programmable soundscape tool
# Copyright 2002-7 by Andrew Plotkin <erkyrath@eblong.com>
# <http://eblong.com/zarf/boodler/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

"""Utility functions for stereo panning.

These functions return a stereo object -- an object which represents a 
range of stereo positions for a soundscale. Stereo objects can be passed
to new_channel_pan() or sched_note_pan().

default() -- return the default stereo position
shift() -- return a simple stereo shift
scale() -- return a stretched or compressed stereo effect
fixed() -- return a stereo effect which is compressed to a point
compose() -- apply one stereo effect on top of another
cast() -- convert an object to a stereo effect
"""

import types

def default():
	"""default() -> stereo

	Return a stereo object which describes the default stereo position --
	no shift, no contraction.

	"""
	return None

def shift(pos):
	"""shift(pos) -> stereo

	Return a simple stereo shift. If pos is zero, there is no shift in
	origin; this returns the default stereo position. -1 means all the
	way left; 1 means all the way right.

	"""
	if (pos == 0):
		return None
	return (1.0, float(pos))

def scale(size):
	"""scale(size) -> stereo

	Return a stereo effect which is not shifted left or right, but is
	compressed or stretched from the center. If size is less than 1,
	the channels are compressed; zero causes every sound to be perfectly
	centered. If size is greater than 1, the channels are spread apart.
	Negative values cause the left and right channels to swap.

	"""
	if (size == 1):
		return None
	return (float(size), 0.0)

def fixed(pos):
	"""shift(pos) -> stereo

	Return a stereo effect which is compressed to a point. All sounds
	contained in this effect, no matter how shifted, will come from a
	single point. If pos is zero, this will be the center; if -1, the
	left side; if 1, the right.

	"""
	return (0.0, float(pos))

def compose(stereo1, stereo2):
	"""compose(stereo1, stereo2):

	Return a stereo effect which is the result of applying of stereo1
	on top of stereo2. This is the equivalent of a channel set to
	stereo1, containing a channel stereo2.

	"""
	if (stereo1 == None):
		stereo1 = (1.0, 0.0)
	(chscale, chshift) = stereo1
	if (stereo2 == None):
		stereo2 = (1.0, 0.0)
	(stereoscale, stereoshift) = stereo2
	stereoscale = stereoscale * chscale
	stereoshift = (stereoshift * chscale) + chshift
	return (stereoscale, stereoshift)

def cast(obj):
	"""cast(obj) -> stereo

	Convert obj into a stereo object. If obj is None, this returns the
	default stereo position. If obj is a number, this returns a simple
	stereo shift -- no scaling. If obj is a stereo object, this returns
	it (or an equivalent object).

	"""
	if (obj == None):
		return obj
	objtyp = type(obj)
	if (objtyp == types.TupleType):
		if (len(obj) == 2):
			return (float(obj[0]), float(obj[1]))
		raise TypeError('stereo tuple not 2-tuple')
	if (objtyp == types.IntType or objtyp == types.LongType or objtyp == types.FloatType):
		if (obj == 0):
			return None
		return (1.0, float(obj))
	raise TypeError('object can\'t be converted to stereo')
