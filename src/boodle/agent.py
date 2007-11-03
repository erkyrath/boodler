# Boodler: a programmable soundscape tool
# Copyright 2002-7 by Andrew Plotkin <erkyrath@eblong.com>
# <http://eblong.com/zarf/boodler/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

import logging

class Agent:
	"""Agent: base class for Boodler agents.

	Methods and fields to be overridden:

	init() -- set the agent up
	run() -- perform the agent's action
	receive() -- perform the agent's action

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
	new_channel() -- create a channel
	new_channel_pan() -- create a channel at a stereo position
	listen() -- begin listening for events
	unlisten() -- stop listening
	get_root_channel() -- return the root channel of the channel tree
	post_listener_agent() -- post another agent to listen for events
	send_event() -- create an event, which posted agents may receive
	get_prop() -- get a property from the agent's channel
	has_prop() -- see whether the agent's channel has a given property
	set_prop() -- set a property on the agent's channel
	del_prop() -- delete a property from the agent's channel

	Class methods:
	
	get_title() -- return a string which describes the agent
	get_class_name() -- ###
	"""

	# Class members:

	# The default inited flag; instances set this true in __init__().
	inited = False
	# Another default value; subclasses can override this.
	selected_event = None

	# Maps Agent subclasses to (pkgname, resname) pairs; see get_class_name().
	# (This does not get wiped during loader.clear_cache(), which means
	# obsolete classes stay alive forever, at least in an importing
	# environment. If we really cared, we'd use weak key refs.)
	cached_class_names = {}
	
	def __init__(self, *args, **kwargs):
		self.inited = True
		self.queued = False
		self.handlers = {}
		self.firsttime = True
		self.generator = None
		self.channel = None
		self.origdelay = None
		
		tup = self.get_class_name()
		self.logger = logging.getLogger('.'.join(tup))

		try:
			self.init(*args, **kwargs)
		except TypeError, ex:
			raise boodle.BoodlerError(str(ex))

	def sched_note(self, samp, pitch=1.0, volume=1.0, delay=0, chan=None):
		"""sched_note(sample, pitch=1, volume=1, delay=0, chan=self.channel)
			-> duration

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

	def sched_note_pan(self, samp, pan=None, pitch=1.0, volume=1.0, delay=0,
		chan=None):
		"""sched_note_pan(sample, pan=0, pitch=1, volume=1, delay=0,
			chan=self.channel) -> duration

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

	def sched_note_duration(self, samp, duration, pitch=1.0, volume=1.0,
		delay=0, chan=None):
		"""sched_note_duration(sample, duration, pitch=1, volume=1, delay=0,
			chan=self.channel) -> duration
		
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
		"""sched_note_duration_pan(sample, duration, pan=0, pitch=1, volume=1,
			delay=0, chan=self.channel) -> duration

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

		This extends the original sound sample to a longer period of time. 
		The duration is given in seconds. This returns the expected duration 
		of the sound, in seconds. Due to the way sounds are looped, this may 
		be slightly longer than the given duration.
		"""

		if (self.generator is None or self.channel is None):
			raise generator.ScheduleError('scheduler has never been scheduled')
		if (chan is None):
			chan = self.channel
		if (not chan.active):
			raise generator.ChannelError('cannot schedule note to inactive channel')
		gen = self.generator
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
		"""sched_note_params(sample, param=value, param=value...) -> duration
		
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
		"""listen(event=self.selected_event, handle=self.receive, hold=None, 
			chan=self.channel) -> Handler

		Begin listening for events. The event should be a string, or a
		function which returns a string. (If no event is given, the
		agent.selected_event field will be consulted.) The agent will
		listen on the given channel, or (if none is given) on the
		agent's own channel.

		The agent will react whenever a matching event is seen on the
		channel. An event matches if it is equal to the selected event
		string, or begins with it; and if it is in the listening channel,
		or a subchannel of it. (So event "foo.bar" will trigger agents
		listening for event "foo.bar", "foo", or "".)

		When an agent is triggered, its receive() method is run. (If you
		pass a different function as handle, that function will be run.)

		The hold value indicates whether the agent's channel will be kept
		alive for as long as it listens. If this is False/None, the channel
		will follow the usual rule and expire as soon as nothing is scheduled 
		on it. (A listening agent does not automatically count as scheduled!)
		If the listening channel is not the same as the agent's own channel,
		you may pass one of the constants HoldRun or HoldListen, to keep
		just one of them alive. A True value will keep both.

		The listen() method returns a Handler object. You may store this
		for later use; it has a cancel() method which may be used to stop
		listening.
		"""
		
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
		"""unlisten(event=None) -> None

		Stop listening. If no event argument is given, stop listening to
		all events. If an event is given, stop listening for that specific
		event.
		"""
		
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
		
	def post_listener_agent(self, ag, chan=None, event=None, handle=None, 
		hold=None, listenchan=None):
		"""post_listener_agent(agent, chan=self.channel, 
			event=ag.selected_event, handle=ag.receive, hold=None, 
			listenchan=chan)

		Post an agent to listen for events. This is equivalent to 
			sched_agent(ag, handle=ag.listen(...))

		That is, the agent must not currently be scheduled. It runs
		immediately, but only to call its listen() method, with any
		arguments you pass in.
		"""

		# Define a closure to call the agent's listen function with the
		# appropriate arguments.
		def func():
			ag.listen(event=event, handle=handle, hold=hold, chan=listenchan)

		self.sched_agent(ag, 0, chan=chan, handle=func)

	def send_event(self, evname, *args, **kwargs):
		"""send_event(event, ..., chan=self.channel)

		Send an event. The event consists of the given name, followed by
		zero or more arguments (which may be any Python object). The
		event is sent on the given channel, or (if none given) on the
		agent's own channel.
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

	def sched_agent(self, ag, delay=0, chan=None, handle=None):
		"""sched_agent(agent, delay=0, chan=self.channel, handle=self.run)

		Schedule an agent to run. This may be the current agent (self) or 
		a newly-created agent. The delay is a time (in seconds) to delay
		before the agent runs. The channel, if None or not supplied,
		defaults to the same channel that self is running in. The agent's
		run() method will be called, unless you specify a different
		function.
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
		if (handle is None):
			handle = ag.run
		gen = self.generator

		if (delay < 0):
			raise generator.ScheduleError('negative delay time')
		if (delay > 3605): 
			# about one hour
			raise generator.ScheduleError('delay too long')
		ag.origdelay = delay
		fdelay = int(delay * cboodle.framespersec())
		starttime = gen.agentruntime + fdelay
		gen.addagent(ag, chan, starttime, handle)

	def resched(self, delay=None, chan=None, handle=None):
		"""resched([delay, chan=self.channel, handle=self.run])

		Reschedule the current agent (self). The delay is a time (in
		seconds) to delay before the agent runs again. The channel, if
		None or not supplied, defaults to the same channel that self is
		running in.

		If delay is not supplied, it defaults to the delay used when this
		agent was first scheduled. Note that if this value was zero, 
		you will probably cause an infinite loop.

		The agent's run() method will be called, unless you specify a 
		different function.
		"""

		if (delay is None):
			delay = self.origdelay
			if (delay is None):
				raise generator.ScheduleError('resched with no prior delay')
		self.sched_agent(self, delay, chan, handle)

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
			
	def init(self):
		"""init(...)

		Set the agent up. The arguments are passed along from the 
		constructor call. Each subclass of Agent may override
		this method; if it wants to accept constructor arguments, it
		must override this.
		"""
		pass

	def run(self):
		"""run()

		Perform the agent's action. Each subclass of Agent must override
		this method.
		"""
		raise NotImplementedError('agent has no run() method')

	def receive(self, event):
		"""receive()

		Perform the agent's action when an appropriate event arrives. 
		Each subclass of Agent which listens for events must override this
		method (or provide an alternative handler).
		
		The event is a tuple, starting with a string, followed (possibly)
		by more values
		"""
		raise NotImplementedError('agent has no receive() method')

	def get_class_name(cla):
		### dot-separated names for class and name
		res = Agent.cached_class_names.get(cla)
		if (res):
			return res

		# Default value
		res = (cla.__module__, cla.__name__)
		
		loader = pload.PackageLoader.global_loader
		if (loader):
			try:
				(pkg, resource) = loader.find_item_resources(cla)
				res = ('pkg.'+pkg.name, resource.key)
			except:
				pass
			
		Agent.cached_class_names[cla] = res
		return res
			
	get_class_name = classmethod(get_class_name)
	
	def get_title(cla):
		"""get_title() -> string

		Return the name of the agent. This defaults to returning the
		title value from the agent's metadata.
		"""

		loader = pload.PackageLoader.global_loader
		if (loader):
			try:
				(pkg, resource) = loader.find_item_resources(cla)
				res = resource.get_one('dc.title')
				if (res):
					return res
			except:
				pass

		# Default value
		return 'unnamed agent'

	get_title = classmethod(get_title)

# Constants for the hold parameter of Agent.listen()
HoldRun = 'run'
HoldListen = 'listen'
HoldBoth = True
		
class Handler:
	"""Handler: Represents the state of one agent listening for one event.

	This is mostly a data object; the generator module uses its fields.
	It does export one method, cancel(), for Agent code to make use of.

	Public methods:

	cancel() -- stop listening

	Internal methods:

	finalize() -- shut down the object
	"""

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
		"""finalize() -> None

		Shut down the Handler object and drop all references.

		This is an internal call. It should only be called by 
		Generator.remhandlers(), and only after the listen has been
		cancelled.
		"""

		self.alive = False
		self.agent = None
		self.generator = None
		self.event = None
		self.listenchannel = None
		self.runchannel = None

	def cancel(self):
		"""cancel() -> None

		Stop listening. It is safe to call this more than once.
		"""

		if (not self.alive):
			return
		self.generator.remhandlers([self])

				
# And now, a bunch of agents which everybody will want to use.
### Add UnlistenAgent? SendEventAgent?

class NullAgent(Agent):
	"""NullAgent:

	This agent does nothing. 
	"""
	
	def run(self):
		pass
	def get_title(self):
		return 'Null Agent'

class StopAgent(Agent):
	"""StopAgent:

	This agent causes a channel to stop playing. (See Channel.stop.)
	All notes and agents in the channel (and subchannels) will be
	discarded.
	"""

	def run(self):
		self.channel.stop()
	def get_title(self):
		return 'Stop Channel'

class FadeOutAgent(Agent):
	"""FadeOutAgent(interval):

	This agent causes a channel to fade down to zero volume over a
	given interval, and then stop.
	"""

	def __init__(self, duration=0.005):
		Agent.__init__(self)
		self.duration = float(duration)
	def run(self):
		self.channel.set_volume(0, self.duration)
		self.sched_agent(StopAgent(), self.duration)
	def get_title(self):
		return 'Fade Out and Stop Channel'

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
	def get_title(self):
		return 'Fade In, Fade Out, Stop Channel'


### What is this in the new system? Certainly moving elsewhere. Maybe
### loading a resource, rather than an agent class per se.
### And how do we pull agents off sys.path?

def load_class_by_name(loader, name):
	"""load_class_by_name(str) -> class

	###
	Given a string that names a class in a module -- for example, 
	'agent.StopAgent' -- import the module and return the class. The 
	class must be a subclass of Agent. The module may be nested (for 
	example, 'reptile.snake.PythonHiss'). This does not instantiate the 
	class; the result is a class, not an agent instance.
	"""

	if (name == ''):
		return NullAgent ###?

	clas = loader.load_item_by_name(name)
	
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

from boopak import version, pload
