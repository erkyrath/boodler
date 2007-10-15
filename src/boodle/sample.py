# Boodler: a programmable soundscape tool
# Copyright 2002-7 by Andrew Plotkin <erkyrath@eblong.com>
# <http://eblong.com/zarf/boodler/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

import string
import fileinput
import os
import os.path
import aifc
import wave
import sunau
import struct
import types

cache = {}

sound_dirs = os.environ.get('BOODLER_SOUND_PATH', os.curdir)
sound_dirs = string.split(sound_dirs, ':')

if struct.pack("h", 1) == "\000\001":
	big_endian = 1
else:
	big_endian = 0

class SampleError(Exception):
	pass

class Sample:
	reloader = None

	def __init__(self, filename, csamp):
		self.filename = filename
		self.refcount = 0
		self.lastused = 0
		self.csamp = csamp

	def queue_note(self, pitch, volume, panscale, panshift, starttime, chan):
		if (cboodle.is_sample_error(self.csamp)):
			raise SampleError('sample is unplayable')
		if (not cboodle.is_sample_loaded(self.csamp)):
			if (not (self.reloader is None)):
				self.reloader.reload(self)
			if (not cboodle.is_sample_loaded(self.csamp)):
				raise SampleError('sample is unloaded')
		def closure(samp=self, chan=chan):
			samp.refcount = samp.refcount - 1
			chan.remnote()
		dur = cboodle.create_note(self.csamp, pitch, volume, panscale, panshift, starttime, chan, closure)
		chan.addnote()
		self.refcount = self.refcount + 1
		if (self.lastused < starttime + dur):
			self.lastused = starttime + dur
		return dur

	def queue_note_duration(self, pitch, volume, panscale, panshift, starttime, duration, chan):
		if (cboodle.is_sample_error(self.csamp)):
			raise SampleError('sample is unplayable')
		if (not cboodle.is_sample_loaded(self.csamp)):
			if (not (self.reloader is None)):
				self.reloader.reload(self)
			if (not cboodle.is_sample_loaded(self.csamp)):
				raise SampleError('sample is unloaded')
		def closure(samp=self, chan=chan):
			samp.refcount = samp.refcount - 1
			chan.remnote()
		dur = cboodle.create_note_duration(self.csamp, pitch, volume, panscale, panshift, starttime, duration, chan, closure)
		chan.addnote()
		self.refcount = self.refcount + 1
		if (self.lastused < starttime + dur):
			self.lastused = starttime + dur
		return dur

	def get_info(self, pitch=1.0):
		if (cboodle.is_sample_error(self.csamp)):
			raise SampleError('sample is unplayable')
		res = cboodle.sample_info(self.csamp)
		ratio = float(res[0]) * float(pitch) * float(cboodle.framespersec())
		if (len(res) == 2):
			return (float(res[1]) / ratio, None)
		else:
			return (float(res[1]) / ratio, 
				(float(res[2]) / ratio, float(res[3]) / ratio))

class MixinSample(Sample):
	def __init__(self, filename, ranges, defval):
		self.filename = filename
		self.ranges = ranges
		self.defval = defval
		self.lastused = 0
		self.refcount = 0
		self.csamp = None

	def find(self, pitch):
		for (startval, endval, pair) in self.ranges:
			if (pitch >= startval and pitch <= endval):
				return pair
		if (not (self.defval is None)):
			return self.defval
		raise SampleError(str(pitch) + ' is outside mixin ranges')

	def queue_note(self, pitch, volume, panscale, panshift, starttime, chan):
		(realsamp, ratio) = self.find(pitch)
		realpitch = pitch * ratio
		return realsamp.queue_note(realpitch, volume, panscale, panshift, starttime, chan)

	def queue_note_duration(self, pitch, volume, panscale, panshift, starttime, duration, chan):
		(realsamp, ratio) = self.find(pitch)
		realpitch = pitch * ratio
		return realsamp.queue_note_duration(realpitch, volume, panscale, panshift, starttime, duration, chan)

	def get_info(self, pitch=1.0):
		(realsamp, ratio) = self.find(pitch)
		realpitch = pitch * ratio
		return realsamp.get_info(realpitch)

def unload_unused(deathtime):
	for samp in list(cache.values()):
		if (samp.refcount == 0
			and (not (samp.csamp is None))
			and deathtime >= samp.lastused
			and cboodle.is_sample_loaded(samp.csamp)):
				cboodle.unload_sample(samp.csamp)

def adjust_timebase(trimoffset, maxage):
	for samp in cache.values():
		if (samp.lastused >= -maxage):
			samp.lastused = samp.lastused - trimoffset

def get(sname):
	"""get(sample) -> soundobject

	Load a sample object, given a filename. (If the filename is relative,
	$BOODLER_SOUND_PATH is searched.) The module maintains a cache of
	sample objects, so if you load the same filename twice, the second
	get() call will be fast.

	This function is not useful, since agent.sched_note() and such methods
	call it for you -- they accept filenames as well as sample objects. 
	This function is available nevertheless.

	"""
	sname = intern(sname)
	samp = cache.get(sname)
	if (not (samp is None)):
		return samp
	
	if (os.path.isabs(sname)):
		filename = sname
		if (not os.access(filename, os.R_OK)):
			raise SampleError('file not readable: ' + filename)
	else:
		for dir in sound_dirs:
			filename = os.path.join(dir, sname)
			if (os.access(filename, os.R_OK)):
				break
		else:
			raise SampleError('file not readable: ' + sname)

	dotpos = string.rfind(sname, '.')
	if (dotpos >= 0):
		suffix = sname[dotpos : ]
	else:
		suffix = ''
	suffix = string.lower(suffix)
	
	loader = find_loader(suffix)
	samp = loader.load(filename, suffix)

	cache[sname] = samp
	return samp

def get_info(samp, pitch=1):
	"""get_info(sample [,pitch=1]) -> tuple

	Measure the expected running time and looping parameters of a sound.
	The argument can be either a filename, or a sample object (as 
	returned by get()).

	The result is a 2-tuple. The first member is the duration of the
	sound (in seconds, if played with the given pitch -- by default,
	the sound's original pitch). The second member is None, if the
	sound has no looping parameters, or a 2-tuple (loopstart, loopend).

	The result of this function may not be precisely accurate, due
	to rounding annoyances. In particular, the duration may not be
	exactly equal to the value returned by agent.sched_note(), when
	the note is actually played.
	"""
	if (type(samp) == types.StringType):
		samp = get(samp)
	return samp.get_info(pitch)

class SampleLoader:
	suffixmap = {}

	def __init__(self):
		self.register_suffixes()

	def register_suffixes(self):
		for val in self.suffixlist:
			SampleLoader.suffixmap[val] = self

	def load(self, filename, suffix):
		csamp = cboodle.new_sample()
		try:
			self.raw_load(filename, csamp)
		except Exception, ex:
			cboodle.delete_sample(csamp)
			raise ex
		samp = Sample(filename, csamp)
		samp.reloader = self
		return samp

	def reload(self, samp):
		#print 'reloading', samp.filename
		self.raw_load(samp.filename, samp.csamp)

def find_loader(suffix):
	clas = SampleLoader.suffixmap.get(suffix)
	if (clas is None):
		raise SampleError('unknown sound file extension \'' 
			+ suffix + '\'')
	return clas

class AifcLoader(SampleLoader):
	suffixlist = ['.aifc', '.aiff', '.aif']
	def raw_load(self, filename, csamp):
		fl = aifc.open(filename, 'r')
		numframes = fl.getnframes()
		dat = fl.readframes(numframes)
		numchannels = fl.getnchannels()
		samplebits = fl.getsampwidth()*8
		framerate = fl.getframerate()
		markers = fl.getmarkers()
		fl.close()
		loopstart = -1
		loopend = -1
		if (not (markers is None)):
			for (mark, pos, name) in markers:
				if (mark == 1):
					loopstart = pos
				elif (mark == 2):
					loopend = pos
		if (loopstart < 0 or loopend < 0):
			loopstart = -1
			loopend = -1
		params = (framerate, numframes, dat, loopstart, loopend, numchannels, samplebits, 1, 1)
		res = cboodle.load_sample(csamp, params)
		if (not res):
			raise SampleError('unable to load aiff data')

aifc_loader = AifcLoader()

class WavLoader(SampleLoader):
	suffixlist = ['.wav']
	def raw_load(self, filename, csamp):
		fl = wave.open(filename, 'r')
		numframes = fl.getnframes()
		dat = fl.readframes(numframes)
		numchannels = fl.getnchannels()
		samplebits = fl.getsampwidth()*8
		framerate = fl.getframerate()
		fl.close()
		params = (framerate, numframes, dat, -1, -1, numchannels, samplebits, 1, big_endian)
		res = cboodle.load_sample(csamp, params)
		if (not res):
			raise SampleError('unable to load wav data')

wav_loader = WavLoader()

class SunAuLoader(SampleLoader):
	suffixlist = ['.au']
	def raw_load(self, filename, csamp):
		fl = sunau.open(filename, 'r')
		numframes = fl.getnframes()
		dat = fl.readframes(numframes)
		numchannels = fl.getnchannels()
		samplebits = fl.getsampwidth()*8
		framerate = fl.getframerate()
		fl.close()
		params = (framerate, numframes, dat, -1, -1, numchannels, samplebits, 1, 1)
		res = cboodle.load_sample(csamp, params)
		if (not res):
			raise SampleError('unable to load au data')

sunau_loader = SunAuLoader()

class MixinLoader(SampleLoader):
	suffixlist = ['.mixin']

	def load(self, filename, suffix):
		ranges = []
		defval = None
		dirname = os.path.dirname(filename)

		for line in fileinput.input(filename):
			tok = string.split(line)
			if len(tok) == 0:
				continue
			if (tok[0][0:1] == '#'):
				continue
			if (tok[0] == 'range'):
				if (len(tok) < 4):
					raise SampleError('range and filename required after range')
				pair = self.parsepair(dirname, tok[3:])
				if (tok[1] == '-'):
					if (len(ranges) == 0):
						startval = 0.0
					else:
						startval = ranges[-1][1]
				else:
					startval = float(tok[1])
				if (tok[2] == '-'):
					endval = 1000000.0
				else:
					endval = float(tok[2])
				ranges.append( (startval, endval, pair) )
			elif (tok[0] == 'else'):
				if (len(tok) < 2):
					raise SampleError('filename required after else')
				defval = self.parsepair(dirname, tok[1:])
			else:
				raise SampleError('unknown statement in mixin: ' + tok[0])
		return MixinSample(filename, ranges, defval)

	def parsepair(self, dirname, tok):
		newname = os.path.join(dirname, tok[0])
		newname = os.path.normpath(newname)
		samp = get(newname)
		if (len(tok) > 1):
			ratio = float(tok[1])
		else:
			ratio = 1.0
		return (samp, ratio)

	def reload(self, samp):
		pass

mixin_loader = MixinLoader()


# Late imports.

import boodle
# cboodle may be updated later, by a set_driver() call.
cboodle = boodle.cboodle
