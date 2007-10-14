# Boodler: a programmable soundscape tool
# Copyright 2002-7 by Andrew Plotkin <erkyrath@eblong.com>
# <http://eblong.com/zarf/boodler/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

import logging
import types ###
import string ###

class Agent:
	"""Agent: base class for Boodler agents.

	Methods and fields to be overridden:

	run() -- perform the agent's action
	name -- a string which describes the agent
	getname() -- return a string which describes the agent

	Publically readable fields:

	channel -- the channel in which this agent is running

	Methods which can be called from a run() method:

	sched_note() -- schedule a note to be played
	sched_note_duration() -- schedule a note to be played for an extended time
	sched_note_pan() -- schedule a note to be played at a stereo position
	sched_note_params() -- schedule a note, allowing all parameters
	sched_agent() -- schedule another agent to run
	resched() -- schedule self to run again
	post_agent() -- post another agent to watch for events
	send_event() -- create an event, which posted agents may receive
	new_channel() -- create a channel
	new_channel_pan() -- create a channel at a stereo position
	get_root_channel() -- return the root channel of the channel tree

	"""

	name = None
	inited = False
	event = None
	real_watch_events = []

	def __init__(self): ###push other args into an init()
		self.inited = True
		self.queued = False
		self.posted = False
		self.generator = None
		self.runtime = 0
		self.channel = None
		self.origdelay = None
		
		### use the Boodler package name here, if possible
		cla = self.__class__
		self.logger = logging.getLogger('pkg.'+cla.__module__+'.'+cla.__name__)

	def __cmp__(self, other):
		return cmp(self.runtime, other.runtime)

	def sched_note(self, samp, pitch=1.0, volume=1.0, delay=0, chan=None):
		"""sched_note(sample [, pitch=1, volume=1, delay=0, chan=self.channel]) -> duration

		Schedule a note to play. The sound is loaded from the file sample
		(which is relative to $BOODLER_SOUND_PATH). The pitch is given as a
		multiple of the sound's original frequency; the volume is given
		as a fraction of the sound's original volume. The delay is a time
		(in seconds) to delay before the note is played. The channel,
		if None or not supplied, defaults to the same channel the agent is
		running in.

		This returns the expected duration of the sound, in seconds.

		"""

		return self.sched_note_pan(samp, None, pitch, volume, delay, chan)

	def sched_note_pan(self, samp, pan=None, pitch=1.0, volume=1.0, delay=0, chan=None):
		"""sched_note_pan(sample [, pan=0, pitch=1, volume=1, delay=0, chan=self.channel]) -> duration

		Schedule a note to play, panning the stereo origin of the sound.
		The pan value defaults to 0, meaning no shift in origin;
		-1 means all the way left; 1 means all the way right. The value
		may also be an object created by the stereo module.

		The sound is loaded from the file sample (which is relative to 
		$BOODLER_SOUND_PATH). The pitch is given as a multiple of the
		sound's original frequency; the volume is given as a fraction
		of the sound's original volume. The delay is a time (in seconds)
		to delay before the note is played. The channel, if None or not
		supplied, defaults to the same channel the agent is running in.

		This returns the expected duration of the sound, in seconds.

		"""

		if (self.generator == None or self.channel == None):
			raise generator.ScheduleError('scheduler has never been scheduled')
		if (chan == None):
			chan = self.channel
		if (not chan.active):
			raise generator.ChannelError('cannot schedule note to inactive channel')
		gen = self.generator
		if (type(samp) == types.StringType):
			samp = sample.get(samp)

		if (delay < 0):
			raise generator.ScheduleError('negative delay time')
		if (delay > 3605): 
			# about one hour
			raise generator.ScheduleError('delay too long')
		fps = cboodle.framespersec()
		fdelay = int(delay * fps)
		starttime = gen.agentruntime + fdelay

		pan = stereo.cast(pan)
		if (pan == None):
			panscale = 1.0
			panshift = 0.0
		else:
			(panscale, panshift) = pan

		dur = samp.queue_note(pitch, volume, panscale, panshift, starttime, chan)
		return float(dur) / float(fps)

	def sched_note_duration(self, samp, duration, pitch=1.0, volume=1.0, delay=0, chan=None):
		"""sched_note_duration(sample, duration [, pitch=1, volume=1, delay=0, chan=self.channel]) -> duration
		
		Schedule a note to play, extending the original sound sample to a
		longer period of time. The duration is given in seconds. 

		The sound is loaded from the file sample (which is relative to 
		$BOODLER_SOUND_PATH). The pitch is given as a multiple of the
		sound's original frequency; the volume is given as a fraction
		of the sound's original volume. The delay is a time (in seconds)
		to delay before the note is played. The channel, if None or not
		supplied, defaults to the same channel the agent is running in.

		This returns the expected duration of the sound, in seconds. Due to
		the way sounds are looped, this may be slightly longer than the
		given duration.

		"""

		return self.sched_note_duration_pan(samp, duration, None, pitch, volume, delay, chan)

	def sched_note_duration_pan(self, samp, duration, pan=None, pitch=1.0, volume=1.0, delay=0, chan=None):

		if (self.generator == None or self.channel == None):
			raise generator.ScheduleError('scheduler has never been scheduled')
		if (chan == None):
			chan = self.channel
		if (not chan.active):
			raise generator.ChannelError('cannot schedule note to inactive channel')
		gen = self.generator
		if (type(samp) == types.StringType):
			samp = sample.get(samp)

		if (delay < 0):
			raise generator.ScheduleError('negative delay time')
		if (delay > 3605): 
			# about one hour
			raise generator.ScheduleError('delay too long')
		if (duration < 0):
			raise generator.ScheduleError('negative duration')
		if (duration > 3605): 
			# about one hour
			raise generator.ScheduleError('duration too long')
		fps = cboodle.framespersec()
		fdelay = int(delay * fps)
		starttime = gen.agentruntime + fdelay
		fduration = int(duration * fps)

		pan = stereo.cast(pan)
		if (pan == None):
			panscale = 1.0
			panshift = 0.0
		else:
			(panscale, panshift) = pan

		dur = samp.queue_note_duration(pitch, volume, panscale, panshift, starttime, fduration, chan)
		return float(dur) / float(fps)

	def sched_note_params(self, samp, **args):
		"""sched_note_params(sample [, param=value, param=value...]) -> duration
		
		Schedule a note to play. This method understands all the arguments
		used by the other sched_note methods, but they must be supplied as
		named keywords. The arguments may be in any order.
		For example: "self.sched_note_params(snd, volume=0.5, pitch=2)"

		The valid arguments, and their default values:
			pitch = 1     (original pitch)
			volume = 1    (full volume)
			delay = 0     (play immediately)
			pan = None    (no stereo shift)
			duration = 0  (exactly once through the sound)
			chan = None   (play in agent's own channel)

		"""

		duration = args.get('duration', 0.0)
		pan = args.get('pan', None)
		pitch = args.get('pitch', 1.0)
		volume = args.get('volume', 1.0)
		delay = args.get('delay', 0.0)
		chan = args.get('chan', None)
		return self.sched_note_duration_pan(samp, duration, pan, pitch, volume, delay, chan)

	def post_agent(self, ag, chan=None):
		"""post_agent(agent [, chan=self.channel])

		Post an agent to watch for events; the agent will be scheduled to
		run whenever an appropriate event occurs. The channel, if None
		or not supplied, defaults to the same channel that self is running
		in.

		The posted agent must have a watch_events field, which lists the
		events which it is interested in. This field must be a string,
		a list of strings, or a function such that agent.watch_events()
		return a string or list of strings.

		"""

		if (not isinstance(ag, EventAgent)):
			raise generator.ScheduleError('not an EventAgent instance')
		if (not (ag.inited and ag.subinited)):
			raise generator.ScheduleError('agent is uninitialized')
		if (self.generator == None or self.channel == None):
			raise generator.ScheduleError('poster has never been scheduled')
		if (chan == None):
			chan = self.channel
		if (not chan.active):
			raise generator.ChannelError('cannot post agent to inactive channel')
		gen = self.generator
		gen.addeventagent(ag, chan)

	def send_event(self, ev):
		"""send_event(event)

		Send an event. Boodler interprets the event just as if it had
		been received from the outside world. Any agents that are posted
		watching for that type of event will run. (Due to the way the
		scheduler works, there may be a short delay before they run.
		The delay is *not* predictable. For reliable scheduling, use
		sched_agent(), not send_event().)

		The event should be a tuple of strings, or a string (which will
		be split into a tuple at whitespace).

		"""

		generator.receive_event(self.generator, ev)

	def sched_agent(self, ag, delay=0, chan=None):
		"""sched_agent(agent [, delay=0, chan=self.channel])

		Schedule an agent to run. This may be the current agent (self) or 
		a newly-created agent. The delay is a time (in seconds) to delay
		before the agent runs. The channel, if None or not supplied,
		defaults to the same channel that self is running in.

		"""

		if (not isinstance(ag, Agent)):
			raise generator.ScheduleError('not an Agent instance')
		if (not ag.inited):
			raise generator.ScheduleError('agent is uninitialized')
		if (self.generator == None or self.channel == None):
			raise generator.ScheduleError('scheduler has never been scheduled')
		if (chan == None):
			chan = self.channel
		if (not chan.active):
			raise generator.ChannelError('cannot schedule agent to inactive channel')
		gen = self.generator

		if (delay < 0):
			raise generator.ScheduleError('negative delay time')
		if (delay > 3605): 
			# about one hour
			raise generator.ScheduleError('delay too long')
		ag.origdelay = delay
		fdelay = int(delay * cboodle.framespersec())
		starttime = gen.agentruntime + fdelay
		gen.addagent(ag, chan, starttime)

	def resched(self, delay=None, chan=None):
		"""resched([delay, chan=self.channel])

		Reschedule the current agent (self). The delay is a time (in
		seconds) to delay before the agent runs again. The channel, if
		None or not supplied, defaults to the same channel that self is
		running in.

		If delay is not supplied, it defaults to the delay used when this
		agent was first scheduled. Note that if this value was zero, 
		you will probably cause an infinite loop.

		"""

		if (delay == None):
			delay = self.origdelay
			if (delay == None):
				raise generator.ScheduleError('resched with no prior delay')
		self.sched_agent(self, delay, chan)

	def new_channel(self, startvolume=1.0, parent=None):
		"""new_channel([startvolume=1, parent=self.channel]) -> channel

		Create a new channel. The startvolume is the volume the channel
		is initially set to; this will affect all sounds played in the
		channel and any subchannels. The new channel will be a subchannel
		of parent -- if None or not supplied, it will be a subchannel of
		the channel that the agent (self) is running in.

		"""

		if (self.channel == None):
			raise generator.ChannelError('creator is not in a channel')
		if (parent == None):
			parent = self.channel
		chan = generator.Channel(parent, self.generator, self, startvolume, None)
		return chan

	def new_channel_pan(self, pan=None, startvolume=1.0, parent=None):
		"""new_channel_pan([pan=stereo.default(), startvolume=1, parent=self.channel]) -> channel

		Create a new channel, panning the stereo origin of its sounds.
		(See the stereo module.) The startvolume is the volume the channel
		is initially set to; this will affect all sounds played in the
		channel and any subchannels. The new channel will be a subchannel
		of parent -- if None or not supplied, it will be a subchannel of
		the channel that the agent (self) is running in.

		"""

		if (self.channel == None):
			raise generator.ChannelError('creator is not in a channel')
		if (parent == None):
			parent = self.channel
		chan = generator.Channel(parent, self.generator, self, startvolume, pan)
		return chan

	def get_root_channel(self):
		"""get_root_channel() -> channel

		Return the root channel of the channel tree.

		"""
		return self.generator.rootchannel

	def run(self):
		"""run()

		Perform the agent's action. Each subclass of Agent must override
		this method.

		"""
		raise NotImplementedError('"' + self.getname() + '" has no run() method')

	watch_events = None

	def getname(self):
		"""getname() -> string

		Return the name of the agent. This defaults to returning 
		self.name, if that is defined.

		"""
		nm = self.name
		if (nm != None):
			return nm
		return 'unnamed agent'

class EventAgent(Agent):
	"""EventAgent: base class for Boodler agents that listen for events.
	See Agent class definition for inherited methods and fields.

	Methods and fields to be overridden:

	run() -- defaults to post_agent(self)
	receive() -- perform the agent's action
	watch_events -- events to watch for (this may be a string, a list of 
	  strings, or a method that returns a string or list of strings)

	Methods which can be called:

	unpost() -- remove self from event-watching post

	"""

	subinited = False

	def __init__(self):
		Agent.__init__(self)
		self.subinited = True

	def run(self):
		"""run()

		By default, this calls post_agent(self). In most cases, you will
		not want to override this.		

		"""
		self.post_agent(self)

	def receive(self, event):
		"""receive()

		Perform the agent's action when an appropriate event arrives. 
		Each subclass of EventAgent must override this method.
		The event is a tuple of one or more strings.

		"""
		raise NotImplementedError('"' + self.getname() + '" has no receive() method')

	def unpost(self):
		"""unpost()

		Remove self from event-watching post.

		"""

		if (not (self.inited and self.subinited)):
			raise generator.ScheduleError('agent is uninitialized')
		if (not self.posted):
			raise generator.ScheduleError('agent is not posted')

		gen = self.generator
		gen.remeventagent(self)


class NullAgent(Agent):
	"""NullAgent:

	This agent does nothing. 

	"""
	name = 'null agent'
	def run(self):
		pass

class StopAgent(Agent):
	"""StopAgent:

	This agent causes a channel to stop playing. (See Channel.stop.)
	All notes and agents in the channel (and subchannels) will be
	discarded.

	"""
	name = 'stop channel'
	def run(self):
		self.channel.stop()

class FadeOutAgent(Agent):
	"""FadeOutAgent(interval):

	This agent causes a channel to fade down to zero volume over a
	given interval, and then stop.

	"""
	name = 'fade out and stop channel'
	def __init__(self, duration=0.005):
		Agent.__init__(self)
		self.duration = float(duration)
	def run(self):
		self.channel.set_volume(0, self.duration)
		self.sched_agent(StopAgent(), self.duration)

class FadeInOutAgent(Agent):
	"""FadeInOutAgent(agent, liveinterval, fadeinterval, fadeoutinterval=fadeinterval):

	This agent creates a channel with an agent, and causes that channel
	to fade up from zero volume, remain at full volume, and then fade out
	and stop.

	The fadeinterval is the time the channel takes to fade in or out.
	The liveinterval is the duration of maximum volume (from the end
	of fade-in to the beginning of fade-out).

	If two intervals are given, the first is the fade-in time, and the
	second is the fade-out time.

	"""
	name = 'fade in, fade out, stop channel'
	def __init__(self, agentinst, liveinterval=10.0, fadeinterval=1.0, fadeoutinterval=None):
		Agent.__init__(self)
		self.agentinst = agentinst
		self.fadeininterval = float(fadeinterval)
		self.liveinterval = float(liveinterval)
		if (fadeoutinterval == None):
			self.fadeoutinterval = self.fadeininterval
		else:
			self.fadeoutinterval = float(fadeoutinterval)
	def run(self):
		chan = self.new_channel(0)
		self.sched_agent(self.agentinst, 0, chan)
		chan.set_volume(1, self.fadeininterval)
		ag = FadeOutAgent(self.fadeoutinterval)
		self.sched_agent(ag, self.liveinterval+self.fadeininterval, chan)

def load_class_by_name(name):
	"""load_class_by_name(str) -> class

	Given a string that names a class in a module -- for example, 
	'agent.StopAgent' -- import the module and return the class. The 
	class must be a subclass of Agent. The module may be nested (for 
	example, 'reptile.snake.PythonHiss'). This does not instantiate the 
	class; the result is a class, not an agent instance.

	"""
	if (name == ''):
		return NullAgent

	fullname = string.split(name, '.')
	[classname] = fullname[-1 : ]
	modname = fullname[ : -1]
	
	if (len(modname) == 0):
		raise ValueError('argument must be of the form module.Class')
	
	mod = __import__(string.join(modname, '.'))
	try:
		for comp in modname[1:]:
			mod = getattr(mod, comp)
		clas = getattr(mod, classname)
	except AttributeError, ex:
		raise ValueError('unable to load ' + name + ' (' + str(ex) + ' missing)')
	
	if (type(clas) != type(Agent)):
		raise TypeError(name + ' is not a class')
	if (not issubclass(clas, Agent)):
		raise TypeError(name + ' is not an Agent class')

	return clas


def list_module_by_name(name):
	"""list_module_by_name(str)

	Given a string that names a module -- for example, 'play' -- import 
	the module, and list all its members that are subclasses of Agent.
	
	### probably can be yanked at this point
	"""
	mod = __import__(name)
	for key in mod.__dict__.keys():
		obj = mod.__dict__[key]
		if (type(obj) == type(Agent) and issubclass(obj, Agent) and not(obj in [Agent, FadeOutAgent, FadeInOutAgent, StopAgent, NullAgent, EventAgent])):
			print (name + '.' + key)


# Late imports.

import boodle
from boodle import generator, sample, stereo
# cboodle may be updated later, by a set_driver() call.
cboodle = boodle.cboodle
