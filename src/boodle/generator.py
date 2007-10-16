# Boodler: a programmable soundscape tool
# Copyright 2002-7 by Andrew Plotkin <erkyrath@eblong.com>
# <http://eblong.com/zarf/boodler/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

import sys
import logging
import traceback
import types
import bisect
import StringIO

#### clean up:
# types.*
####


class Generator:
	"""Generator: A class that stores the internal state of boodler
	sound generation.

	Everything in this class is private to boodler.

	"""

	def __init__(self, basevolume=0.5, dolisten=0, listenport=None):
		self.logger = logging.getLogger()
		self.logger.info('generator setting up')

		self.queue = []
		self.postpool = {}
		self.channels = {}
		self.stoplist = []
		self.postqueue = []
		self.listener = None
		self.event_registry = {}
		self.lastunload = 0
		self.verbose_errors = False
		self.stats_interval = None
		self.statslogger = None
		if dolisten:
			lfunc = lambda val, gen=self: receive_event(gen, val)
			self.listener = listen.Listener(lfunc, listenport)

		self.rootchannel = Channel(None, self, None, basevolume, None)

	def close(self):
		if (self.listener):
			self.listener.close()
		self.logger.info('generator shut down')

	def set_stats_interval(self, val):
		self.statslogger = logging.getLogger('stats')
		self.stats_interval = val
		self.last_stats_dump = 0

	def addagent(self, ag, chan, runtime):
		if (ag.queued):
			raise ScheduleError('"' + ag.getname() + '"' + ' is already scheduled')

		ag.generator = self
		ag.runtime = runtime
		ag.channel = chan
		chan.agentcount = chan.agentcount+1
		ag.queued = True

		bisect.insort(self.queue, ag)

		ag.logger.info('scheduled at depth-%d', chan.depth)

	def remagent(self, ag):
		ag.logger.info('unscheduled')
		
		ag.queued = False
		ag.channel.agentcount = ag.channel.agentcount-1
		self.queue.remove(ag)

	def addeventagent(self, ag, chan):
		if (self.listener is None):
			raise ScheduleError('event listening disabled -- cannot post '
				+ '"' + ag.getname() + '"')
		if (ag.posted):
			raise ScheduleError('"' + ag.getname() + '"' + ' is already posted')

		ag.generator = self
		ag.channel = chan
		chan.agentcount = chan.agentcount+1
		ag.posted = True
		self.postpool[ag] = ag

		try:
			ls = ag.watch_events
			if (ls is None):
				raise NotImplementedError('"' + ag.getname() + '"' + ' has no watch_events')
			if callable(ls):
				ls = ls()
			if (type(ls) == types.StringType):
				ls = [ls]
			if (type(ls) != types.ListType):
				raise TypeError('"' + ag.getname() + '"' + ' has invalid watch_events')
			for dat in ls:
				if (type(dat) != types.StringType):
					raise TypeError('"' + ag.getname() + '"' + ' has invalid entry in watch_events')
		except:
			ag.posted = False
			chan.agentcount = chan.agentcount-1
			del self.postpool[ag]
			raise
		
		ag.real_watch_events = ls
		evreg = self.event_registry
		for el in ls:
			if (evreg.has_key(el)):
				evreg[el].append(ag)
			else:
				evreg[el] = [ag]

	def remeventagent(self, ag):
		evreg = self.event_registry
		for el in ag.real_watch_events:
			ags = evreg.get(el)
			if ((ags) and (ag in ags)):
				ags.remove(ag)
		ag.real_watch_events = []
		ag.posted = False
		ag.channel.agentcount = ag.channel.agentcount-1
		del self.postpool[ag]

	def dump_stats(self, fl=None):
		if (fl is None):
			fl = sys.stdout
		write = fl.write

		write('...\n')
		numagent = len(self.queue)
		if (self.listener):
			numagentpost = len(self.postpool)
			write(str(numagent+numagentpost) + ' agents (' + str(numagent) + ' scheduled, ' + str(numagentpost) + ' posted)\n')
		else:
			write(str(numagent) + ' agents\n')
		numchan = len(self.channels)
		write(str(numchan) + ' channels\n')
		numsamp = len(sample.cache)
		numsamploaded = 0
		numsampunloaded = 0
		numsampvirt = 0
		numnotes = 0
		for samp in sample.cache.values():
			numnotes = numnotes + samp.refcount
			if (samp.csamp is None):
				numsampvirt = numsampvirt+1
			elif (cboodle.is_sample_loaded(samp.csamp)):
				numsamploaded = numsamploaded+1
			else:
				numsampunloaded = numsampunloaded+1
		write(str(numsamp) + ' samples (' + str(numsamploaded) 
			+ ' loaded, ' + str(numsampunloaded) + ' unloaded, '
			+ str(numsampvirt) + ' virtual)\n')
		write(str(numnotes) + ' notes\n')

class Channel:
	"""Channel: a class for creating hierarchical trees of sounds and
	agents.

	Channel objects should be created via Agent.new_channel() and
	destroyed with the channel.stop() method.

	Public methods and fields:

	parent -- the parent of the channel (None if root)
	get_root_channel() -- return the root channel of the tree
	set_volume() -- change the volume of the channel
	stop() -- stop the channel immediately

	Class method:

	compare() -- compare two channels in deepest-to-root order
	"""

	logger = None

	def __init__(self, parent, gen, createagent, startvol, pan):
		self.active = True
		self.generator = gen
		if (not Channel.logger):
			Channel.logger = logging.getLogger('channel')
		self.volume = (0, 0, startvol, startvol)
		self.stereo = stereo.cast(pan)
		self.lastvolume = startvol
		self.notecount = 0
		self.agentcount = 0
		self.childcount = 0
		self.parent = parent
		
		if (parent is None):
			self.depth = 0
			self.ancestors = {}
			self.rootchannel = self
		else:
			self.depth = parent.depth+1
			parent.childcount = parent.childcount+1
			self.ancestors = parent.ancestors.copy()
			self.ancestors[parent] = parent
			self.rootchannel = parent.rootchannel
			
		if (createagent is None):
			self.creatorname = '<boodler>'
		else:
			### use the Boodler package name here, if possible
			self.creatorname = createagent.__class__.__name__
			
		gen.channels[self] = self
		self.logger.info('opened %s', self)

	def __str__(self):
		return 'depth-%d (out of %s)' % (self.depth, self.creatorname)

	def close(self):
		if (not self.active):
			return
		if (self.childcount > 0):
			raise BoodleInternalError('channel has children at close')
		if (self.agentcount > 0):
			raise BoodleInternalError('channel has agents at close')
		if (self.notecount > 0):
			raise BoodleInternalError('channel has notes at close')
		if (self.parent):
			self.parent.childcount = self.parent.childcount-1
			if (self.parent.childcount < 0):
				raise BoodleInternalError('channel childcount negative')
				
		self.logger.info('closed %s', self)
		gen = self.generator
		self.active = False
		self.generator = None
		self.depth = None
		self.ancestors.clear()
		self.ancestors = None
		self.parent = None
		del gen.channels[self]

	def stop(self):
		"""stop()

		Stop the channel immediately. All sounds playing in the channel 
		(or any subchannels) are cut off; all sounds and agents scheduled
		to run are discarded.

		If any notes are playing with non-zero volume, their termination
		may cause undesirable clicks and pops. It is best to set the volume
		of a channel to zero before stopping it. (The FadeOutAgent class
		can be used for this.)

		Due to the way sound generation is buffered, when an agent calls
		channel.stop(), the channel may be stopped slightly later than
		it ought to be.

		"""
		self.generator.stoplist.append(self)

	def realstop(self):
		if (not self.active):
			raise ChannelError('cannot stop an inactive channel')
		cboodle.stop_notes(self)
		
		agents = [ ag for ag in self.generator.queue
			if (ag.channel is self or ag.channel.ancestors.has_key(self)) ]
		for ag in agents:
			self.generator.remagent(ag)
			
		agents = [ ag for ag in self.generator.postpool
			if (ag.channel is self or ag.channel.ancestors.has_key(self)) ]
		for ag in agents:
			self.generator.remeventagent(ag)
			
		chans = [ ch for ch in self.generator.channels
			if (ch is self or ch.ancestors.has_key(self)) ]
		chans.sort(Channel.compare)
		for ch in chans:
			ch.close()

	def addnote(self):
		self.notecount = self.notecount + 1

	def remnote(self):
		self.notecount = self.notecount - 1
		if (self.notecount < 0):
			raise BoodleInternalError('channel notecount negative')

	def get_root_channel(self):
		"""get_root_channel() -> channel

		Return the root channel of the tree.

		"""
		return self.rootchannel

	def set_volume(self, newvol, interval=0.005):
		"""set_volume(newvolume [, interval=0.005])

		Change the volume of the channel to a new level (0 means silence,
		1 means full volume). This affects all notes in the channel and
		any subchannels.

		The volume change begins immediately, and occurs smoothly over
		the interval given (in seconds). If no value is given, the interval
		defaults to 0.005 (five milliseconds), which is short enough that
		it will sound instantaneous. (You should not use an interval
		shorter than 0.005; it can cause undesirable clicks and pops.)

		Due to the way the volume code is written (a cheap and dirty hack),
		two volume changes scheduled too close together on the same channel
		(within about one second) can interfere with each other. The earlier
		one may be ignored entirely in favor of the later. Therefore, you
		should not rely on rapid sequences of set_volume() calls for your
		sound effects. Set volumes on individual notes instead, or else
		create several channels.

		"""
		starttm = self.generator.agentruntime
		endtm = starttm + int(interval * cboodle.framespersec())
		if (endtm >= self.volume[1]):
			self.volume = (starttm, endtm, self.lastvolume, newvol)

	def compare(ch1, ch2):
		"""compare(ch1, ch2) -> int

		Compare two channels in depth order. Sorting a list of channels
		with this comparison function will put the deepest ones first,
		the root last.
		"""
		return cmp(ch2.depth, ch1.depth)
	compare = staticmethod(compare)

TRIMTIME   = 317520000   # two hours
TRIMOFFSET = 158760000   # one hour
UNLOADTIME =  13230000   # five minutes
UNLOADAGE  = 100000000   # 40-ish minutes

####
TRIMTIME   =  80000
TRIMOFFSET =  50000
UNLOADTIME =  50000
UNLOADAGE  = 110000

def run_agents(starttime, gen):
	if (starttime >= TRIMTIME):
		starttime = starttime - TRIMOFFSET
		cboodle.adjust_timebase(TRIMOFFSET)
		gen.lastunload = gen.lastunload - TRIMOFFSET
		sample.adjust_timebase(TRIMOFFSET, UNLOADAGE)
		for ag in gen.queue:
			ag.runtime = ag.runtime - TRIMOFFSET
		for chan in gen.channels:
			(starttm, endtm, startvol, endvol) = chan.volume
			if (endtm <= starttime):
				continue
			starttm = starttm - TRIMOFFSET
			endtm = endtm - TRIMOFFSET
			chan.volume = (starttm, endtm, startvol, endvol)
		if (not (gen.stats_interval is None)):
			gen.last_stats_dump = gen.last_stats_dump - TRIMOFFSET

	if (gen.lastunload + UNLOADTIME < starttime):
		gen.lastunload = starttime
		sample.unload_unused(starttime-UNLOADAGE)

	if (not (gen.stats_interval is None)):
		if (gen.last_stats_dump + int(gen.stats_interval * cboodle.framespersec()) < starttime):
			gen.last_stats_dump = starttime
			fl = StringIO.StringIO()
			gen.dump_stats(fl)
			gen.statslogger.warning(fl.getvalue())
			fl.close()

	nexttime = starttime + cboodle.framesperbuf()

	if (gen.stoplist):
		for chan in gen.stoplist:
			if (chan.active):
				chan.realstop()
		gen.stoplist = []

	if (gen.listener):
		gen.listener.poll()

	gen.agentruntime = starttime
	while (len(gen.postqueue) > 0):
		(ag, ev) = gen.postqueue.pop(0)
		ag.logger.info('running on %s', ev)
		try:
			if (not ag.channel.active):
				raise BoodleInternalError('posted agent not in active channel')
			ag.receive(ev)
		except Exception, ex:
			ag.logger.error('"%s" %s: %s',
				ag.getname(), ex.__class__.__name__, ex,
				exc_info=True)

	while (gen.queue and gen.queue[0].runtime < nexttime):
		ag = gen.queue.pop(0)
		ag.queued = False
		ag.channel.agentcount = ag.channel.agentcount-1
		ag.logger.info('running')
		try:
			if (not ag.channel.active):
				raise BoodleInternalError('queued agent not in active channel')
			gen.agentruntime = ag.runtime
			ag.run()
		except Exception, ex:
			ag.logger.error('"%s" %s: %s',
				ag.getname(), ex.__class__.__name__, ex,
				exc_info=True)

	for chan in gen.channels:
		(starttm, endtm, startvol, endvol) = chan.volume
		if (nexttime >= endtm):
			chan.lastvolume = endvol
		elif (nexttime >= starttm):
			chan.lastvolume = (nexttime - starttm) / float(endtm - starttm) * (endvol - startvol) + startvol
		else:
			chan.lastvolume = startvol

	ls = [ chan for chan in gen.channels
		if (chan.notecount == 0
			and chan.agentcount == 0
			and chan.childcount == 0)
	]
	for chan in ls:
		chan.close()

	if (not gen.channels):
		raise StopGeneration()


def receive_event(gen, val):
	if (type(val) == types.StringType):
		event = tuple(val.split())
	else:
		event = tuple(val)
	if (len(event) == 0):
		return
	watchers = gen.event_registry.get(event[0])
	if (not watchers):
		return
	for ag in watchers:
		gen.postqueue.append((ag, event))


# Late imports.

import boodle
from boodle import stereo, sample, listen
from boodle import BoodlerError, StopGeneration
# cboodle may be updated later, by a set_driver() call.
cboodle = boodle.cboodle

class ScheduleError(BoodlerError):
	"""ScheduleError: Represents an invalid use of the scheduler.
	"""
	pass
class ChannelError(BoodlerError):
	"""ChannelError: Represents an invalid use of a channel.
	"""
	pass
class BoodleInternalError(BoodlerError):
	"""BoodleInternalError: Represents an internal sanity check going
	wrong.
	"""
	pass
