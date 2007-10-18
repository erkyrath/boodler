# Boodler: a programmable soundscape tool
# Copyright 2002-7 by Andrew Plotkin <erkyrath@eblong.com>
# <http://eblong.com/zarf/boodler/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

import logging

class Agent:
	"""Agent: base class for Boodler agents.

	Agents compare (<, >) based on their runtime field. (This lets the
	generator sort its queue more efficiently.) If the runtime fields are
	equal, the comparison is arbitrary (but consistent; the objects compare
	based on id().)

	Comparing (agent == None) will raise an exception. Use (agent is None)
	instead.

	Methods and fields to be overridden:

	run() -- perform the agent's action
	receive() -- perform the agent's action
	name -- a string which describes the agent
	getname() -- return a string which describes the agent

	Publically readable fields:

	channel -- the channel in which this agent is running
	firsttime -- True the first time the run() method is called

	Methods which can be called from a run() method:

	sched_note() -- schedule a note to be played
	sched_note_duration() -- schedule a note to be played for an extended time
	sched_note_pan() -- schedule a note to be played at a stereo position
	sched_note_params() -- schedule a note, allowing all parameters
	sched_agent() -- schedule another agent to run
	resched() -- schedule self to run again
	post_agent() -- post another agent to listen for events
	send_event() -- create an event, which posted agents may receive
	new_channel() -- create a channel
	new_channel_pan() -- create a channel at a stereo position
	get_root_channel() -- return the root channel of the channel tree
	get_prop() -- get a property from the agent's channel
	has_prop() -- see whether the agent's channel has a given property
	set_prop() -- set a property on the agent's channel
	del_prop() -- delete a property from the agent's channel
	"""

	name = None
	inited = False
	event = None
	selected_event = None

	def __init__(self): ###push other args into an init()
		self.inited = True
		self.queued = False
		self.handlers = {}
		self.firsttime = True
		self.generator = None
		self.runtime = 0
		self.channel = None
		self.origdelay = None
		
		### use the Boodler package name here, if possible
		cla = self.__class__
		self.logger = logging.getLogger('pkg.'+cla.__module__+'.'+cla.__name__)

	def __cmp__(self, other):
		return (cmp(self.runtime, other.runtime) or cmp(id(self), id(other)))

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

		if (self.generator is None or self.channel is None):
			raise generator.ScheduleError('scheduler has never been scheduled')
		if (chan is None):
			chan = self.channel
		if (not chan.active):
			raise generator.ChannelError('cannot schedule note to inactive channel')
		gen = self.generator
		if (not isinstance(samp, sample.Sample)):
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
		if (pan is None):
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

		if (self.generator is None or self.channel is None):
			raise generator.ScheduleError('scheduler has never been scheduled')
		if (chan is None):
			chan = self.channel
		if (not chan.active):
			raise generator.ChannelError('cannot schedule note to inactive channel')
		gen = self.generator
		if (not isinstance(samp, sample.Sample)):
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
		if (pan is None):
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

	def listen(self, event=None, handle=None, hold=None, chan=None):
		###
		
		if (not self.inited):
			raise generator.ScheduleError('agent is uninitialized')
		if (self.generator is None or self.channel is None):
			raise generator.ScheduleError('listener has never been scheduled')
		if (chan is None):
			chan = self.channel
		if (not chan.active):
			raise generator.ChannelError('cannot listen to inactive channel')
			
		if (event is None):
			event = self.selected_event
		if (event is None):
			raise generator.ScheduleError('must specify event to listen for')
		if (callable(event)):
			event = event()
			if (event is None):
				raise generator.ScheduleError('must return event to listen for')
		if (event != ''):
			event = boodle.check_prop_name(event)

		if (handle is None):
			handle = self.receive

		gen = self.generator
		han = Handler(self, handle, event, chan, hold)
		gen.addhandler(han)
		
		return han

	def unlisten(self, event=None):
		###
		
		if (self.generator is None or self.channel is None):
			raise generator.ScheduleError('listener has never been scheduled')

		if (event is None):
			ls = [ han for han in self.handlers ]
		else:
			event = boodle.check_prop_name(event)
			ls = [ han for han in self.handlers if (han.event == event) ]

		if (not ls):
			return
			
		gen = self.generator
		gen.remhandlers(ls)
		
	def post_agent(self, ag, hold=None, chan=None, listenchan=None): #### 
		"""post_agent(agent [, chan=self.channel])

		Post an agent to listen for events ###

		"""

		#### only for freshly-created agents
		if (not isinstance(ag, EventAgent)):
			raise generator.ScheduleError('not an EventAgent instance')
		if (not (ag.inited and ag.subinited)):
			raise generator.ScheduleError('agent is uninitialized')
		if (self.generator is None or self.channel is None):
			raise generator.ScheduleError('poster has never been scheduled')
		if (chan is None):
			chan = self.channel
		if (not chan.active):
			raise generator.ChannelError('cannot post agent to inactive channel')
		gen = self.generator
		gen.addeventagent(ag, chan)

	def send_event(self, evname, *args, **kwargs):
		"""send_event(event)

		Send an event. ###
		"""

		chan = kwargs.pop('chan', None)
		if (kwargs):
			raise TypeError('invalid keyword argument for this function')

		if (self.generator is None or self.channel is None):
			raise generator.ScheduleError('sender has never been scheduled')
		if (chan is None):
			chan = self.channel
		if (not chan.active):
			raise generator.ChannelError('cannot send event to inactive channel')
		gen = self.generator

		evname = boodle.check_prop_name(evname)
		ev = (evname,) + args

		gen.sendevent(ev, chan)

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
		if (self.generator is None or self.channel is None):
			raise generator.ScheduleError('scheduler has never been scheduled')
		if (chan is None):
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

		if (delay is None):
			delay = self.origdelay
			if (delay is None):
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

		if (self.channel is None):
			raise generator.ChannelError('creator is not in a channel')
		if (parent is None):
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

		if (self.channel is None):
			raise generator.ChannelError('creator is not in a channel')
		if (parent is None):
			parent = self.channel
		chan = generator.Channel(parent, self.generator, self, startvolume, pan)
		return chan

	def get_root_channel(self):
		"""get_root_channel() -> channel

		Return the root channel of the channel tree.

		"""
		return self.generator.rootchannel

	def get_prop(self, key, default=None):
		"""get_prop(key, default=None) -> any

		Get a property from the agent's channel. If none is set, see if 
		one is inherited from the parent. If there is no inherited value 
		either, return None, or the given default.

		Note that None is a legal property value. To distinguish between
		no property and a property set to None, use has_prop().
		"""
		return self.channel.get_prop(key, default)
			
	def has_prop(self, key):
		"""has_prop(key) -> bool

		See whether the agent's channel has a given property. If none is 
		set, see if one is inherited from the parent.
		"""
		return self.channel.has_prop(key)
			
	def set_prop(self, key, val):
		"""set_prop(key, val) -> None

		Set a property on the agent's channel.
		"""
		return self.channel.set_prop(key, val)
			
	def del_prop(self, key):
		"""del_prop(key) -> None

		Delete a property from the agent's channel. If none is set, this 
		has no effect.

		Note that this does not affect parent channels. So get_prop(key)
		may still return a value after del_prop(key).
		"""
		return self.channel.del_prop(key)
			
	def run(self):
		"""run()

		Perform the agent's action. Each subclass of Agent must override
		this method.

		"""
		raise NotImplementedError('"' + self.getname() + '" has no run() method')

	def receive(self, event):
		"""receive()

		Perform the agent's action when an appropriate event arrives. 
		Each subclass of Agent which listens for events must override this
		method (or provide an alternative handler).
		
		The event is a tuple, starting with a string, followed (possibly)
		by more values

		"""
		raise NotImplementedError('"' + self.getname() + '" has no receive() method')
		
	def getname(self):
		"""getname() -> string

		Return the name of the agent. This defaults to returning 
		self.name, if that is defined.

		"""
		nm = self.name
		if (nm):
			return nm
		return 'unnamed agent'

# Constants for the hold parameter of Agent.listen()
HoldRun = 'run'
HoldListen = 'listen'
HoldBoth = True
		
class Handler:
	###
	def __init__(self, ag, func, event, chan, hold):
		self.alive = False
		self.agent = ag
		self.func = func
		self.generator = ag.generator
		self.event = event
		self.listenchannel = chan
		self.runchannel = ag.channel
		self.holdlisten = False
		self.holdrun = False

		if (hold is HoldListen):
			self.holdlisten = True
			hold = None
		if (hold is HoldRun):
			self.holdrun = True
			hold = None
		if (hold):
			self.holdlisten = True
			self.holdrun = True

	def finalize(self):
		### only called by remhandlers
		self.alive = False
		self.agent = None
		self.generator = None
		self.event = None
		self.listenchannel = None
		self.runchannel = None

	def cancel(self):
		if (not self.alive):
			return
		self.generator.remhandlers([self])

				
# And now, a bunch of agents which everybody will want to use.
### Add UnlistenAgent? SendEventAgent?

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
		if (fadeoutinterval is None):
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

	fullname = name.split('.')
	[classname] = fullname[-1 : ]
	modname = fullname[ : -1]
	
	if (len(modname) == 0):
		raise ValueError('argument must be of the form module.Class')
	
	mod = __import__('.'.join(modname))
	try:
		for comp in modname[1:]:
			mod = getattr(mod, comp)
		clas = getattr(mod, classname)
	except AttributeError, ex:
		raise ValueError('unable to load ' + name + ' (' + str(ex) + ')')
	
	if (type(clas) != type(Agent)):
		raise TypeError(name + ' is not a class')
	if (not issubclass(clas, Agent)):
		raise TypeError(name + ' is not an Agent class')

	return clas



# Late imports.

import boodle
from boodle import generator, sample, stereo
# cboodle may be updated later, by a set_driver() call.
cboodle = boodle.cboodle
