# Boodler: a programmable soundscape tool
# Copyright 2002-7 by Andrew Plotkin <erkyrath@eblong.com>
# <http://eblong.com/zarf/boodler/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

import sys
import logging
import traceback
import string
import types
import bisect

#### clean up:
# for x in map.keys()
# filter
# map
# lambda
# string.*
# types.*
# == None
####

### can these live in Generator?
queue = []
postpool = {}
channels = {}

class ScheduleError(Exception):
	pass
class ChannelError(Exception):
	pass
class StopGeneration(Exception):
	pass
class BoodleInternalError(Exception):
	pass

class Generator:
	"""Generator: A class that stores the internal state of boodler
	sound generation.

	Everything in this class is private to boodler.

	"""

	def __init__(self, basevolume=0.5, dolisten=0, listenport=None):
		self.logger = logging.getLogger()
		self.logger.info('generator setting up')
		
		self.rootchannel = Channel(None, self, None, basevolume, None)
		self.stoplist = []
		self.postqueue = []
		self.listener = None
		self.event_registry = {}
		self.lastunload = 0
		self.verbose_errors = False
		self.stats_interval = None
		if dolisten:
			lfunc = lambda val, gen=self: receive_event(gen, val) ###?
			self.listener = listen.Listener(lfunc, listenport)

	def close(self):
		if (self.listener != None):
			self.listener.close()
		self.logger.info('generator shut down')

	def set_verbose_errors(self, val):
		### necessary?
		self.verbose_errors = val

	def set_stats_interval(self, val):
		self.stats_interval = val
		self.last_stats_dump = 0

	def addagent(self, ag, chan, runtime):
		# move to agent, maybe?
		if (ag.queued):
			raise ScheduleError('"' + ag.getname() + '"' + ' is already scheduled')

		ag.generator = self
		ag.runtime = runtime
		ag.channel = chan
		chan.agentcount = chan.agentcount+1
		ag.queued = True

		bisect.insort(queue, ag)

		ag.logger.info('scheduled at depth-%d', chan.depth)

	def remagent(self, ag):
		ag.logger.info('unscheduled')
		
		ag.queued = False
		ag.channel.agentcount = ag.channel.agentcount-1
		queue.remove(ag)

	def addeventagent(self, ag, chan):
		if (self.listener == None):
			raise ScheduleError('event listening disabled -- cannot post '
				+ '"' + ag.getname() + '"')
		if (ag.posted):
			raise ScheduleError('"' + ag.getname() + '"' + ' is already posted')

		ag.generator = self
		ag.channel = chan
		chan.agentcount = chan.agentcount+1
		ag.posted = True
		postpool[ag] = ag

		try:
			ls = ag.watch_events
			if (ls == None):
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
			del postpool[ag]
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
			if ((ags != None) and (ag in ags)):
				ags.remove(ag)
		ag.real_watch_events = []
		ag.posted = False
		ag.channel.agentcount = ag.channel.agentcount-1
		del postpool[ag]

	def dump_stats(self, fl=None):
		if (fl == None):
			fl = sys.stdout
		write = fl.write

		write('* boodler runtime stats\n')
		numagent = len(queue)
		if (self.listener != None):
			numagentpost = len(postpool)
			write(str(numagent+numagentpost) + ' agents (' + str(numagent) + ' scheduled, ' + str(numagentpost) + ' posted)\n')
		else:
			write(str(numagent) + ' agents\n')
		numchan = len(channels)
		write(str(numchan) + ' channels\n')
		numsamp = len(sample.cache)
		numsamploaded = 0
		numsampunloaded = 0
		numsampvirt = 0
		numnotes = 0
		for samp in sample.cache.values():
			numnotes = numnotes + samp.refcount
			if (samp.csamp == None):
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
			
		channels[self] = self
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
		if (self.parent != None):
			self.parent.childcount = self.parent.childcount-1
			if (self.parent.childcount < 0):
				raise BoodleInternalError('channel childcount negative')
				
		self.logger.info('closed %s', self)
		self.active = False
		self.generator = None
		self.depth = None
		self.ancestors.clear()
		self.ancestors = None
		self.parent = None
		del channels[self]

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
		agentfunc = (lambda ag, key=self: (ag.channel == key or ag.channel.ancestors.has_key(key)))
		agents = filter(agentfunc, queue)
		for ag in agents:
			ag.generator.remagent(ag)
		agents = filter(agentfunc, postpool.keys())
		for ag in agents:
			ag.generator.remeventagent(ag)
		channelfunc = (lambda ch, key=self: (ch == key or ch.ancestors.has_key(key)))
		chans = filter(channelfunc, channels.keys())
		chans.sort(lambda c1, c2: (c2.depth - c1.depth)) ### __cmp__
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
		#print 'adjust timebase:', starttime, '-', TRIMOFFSET, '=', (starttime - TRIMOFFSET)
		starttime = starttime - TRIMOFFSET
		cboodle.adjust_timebase(TRIMOFFSET)
		gen.lastunload = gen.lastunload - TRIMOFFSET
		sample.adjust_timebase(TRIMOFFSET, UNLOADAGE)
		for ag in queue:
			ag.runtime = ag.runtime - TRIMOFFSET
		for chan in channels.keys():
			(starttm, endtm, startvol, endvol) = chan.volume
			if (endtm <= starttime):
				continue
			starttm = starttm - TRIMOFFSET
			endtm = endtm - TRIMOFFSET
			chan.volume = (starttm, endtm, startvol, endvol)
		if (gen.stats_interval != None):
			gen.last_stats_dump = gen.last_stats_dump - TRIMOFFSET

	if (gen.lastunload + UNLOADTIME < starttime):
		#print 'unload samples:', starttime
		gen.lastunload = starttime
		sample.unload_unused(starttime-UNLOADAGE)

	if (gen.stats_interval != None):
		if (gen.last_stats_dump + int(gen.stats_interval * cboodle.framespersec()) < starttime):
			gen.last_stats_dump = starttime
			gen.dump_stats()

	nexttime = starttime + cboodle.framesperbuf()
	#print 'generating:', starttime, 'to', nexttime, '(queue', len(queue), ', channels', len(channels), ')'

	if (gen.stoplist):
		for chan in gen.stoplist:
			if (chan.active):
				chan.realstop()
		gen.stoplist = []

	#print map((lambda samp: (string.split(samp.filename, '/')[-1], samp.refcount, samp.lastused)), sample.cache.values())
	#print map((lambda ch: sys.getrefcount(ch)), channels.keys())
	#print map((lambda ch: (ch.notecount, ch.agentcount, ch.childcount)), channels.keys())
	#print map((lambda ch: (ch.volume, ch.lastvolume)), channels.keys())
	#print gen.event_registry

	if (gen.listener != None):
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
			ag.logger.exception('"%s" %s: %s',
				ag.getname(), ex.__class__.__name__, ex)

	while (len(queue) > 0 and queue[0].runtime < nexttime):
		ag = queue.pop(0)
		ag.queued = False
		ag.channel.agentcount = ag.channel.agentcount-1
		ag.logger.info('running')
		try:
			if (not ag.channel.active):
				raise BoodleInternalError('queued agent not in active channel')
			gen.agentruntime = ag.runtime
			ag.run()
		except Exception, ex:
			ag.logger.exception('"%s" %s: %s',
				ag.getname(), ex.__class__.__name__, ex)

	for chan in channels.keys():
		vol = chan.volume     ### break out tuple
		if (nexttime >= vol[1]):
			chan.lastvolume = vol[3]
		elif (nexttime >= vol[0]):
			chan.lastvolume = (nexttime - vol[0]) / float(vol[1] - vol[0]) * (vol[3] - vol[2]) + vol[2]
		else:
			chan.lastvolume = vol[2]

	for chan in channels.keys():
		if (chan.notecount == 0 and chan.agentcount == 0 and chan.childcount == 0):
			chan.close()

	if (len(channels) == 0):
		raise StopGeneration()


def receive_event(gen, val):
	if (type(val) == types.StringType):
		event = tuple(string.split(val))
	else:
		event = tuple(val)
	if (len(event) == 0):
		return
	watchers = gen.event_registry.get(event[0])
	if (watchers == None):
		return
	for ag in watchers:
		gen.postqueue.append((ag, event))


# Late imports.

import boodle
from boodle import stereo, sample, listen
# cboodle may be updated later, by a set_driver() call.
cboodle = boodle.cboodle
