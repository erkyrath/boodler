from boodle.agent import *
import random

class Sounds(EventAgent):
	name = 'play sounds by command'
	watch_events = 'sound'
	def receive(self, event):
		sndlist = event[1:]
		pos = 0.0
		for snd in sndlist:
			dur = self.sched_note(snd, 1, 1, pos)
			pos = pos + dur

class Agents(EventAgent):
	name = 'run agents by command'
	def __init__(self, fadetime=2.0):
		EventAgent.__init__(self)
		self.fadetime = float(fadetime)
		self.prevchannel = None
	watch_events = 'agent'
	def receive(self, event):
		clas = load_class_by_name(event[1])
		clasargs = event[2:]
		ag = apply(clas, clasargs)
		if (self.prevchannel != None and self.prevchannel.active):
			self.sched_agent(FadeOutAgent(self.fadetime), 0, self.prevchannel)
		self.prevchannel = self.new_channel(0)
		self.prevchannel.set_volume(1, self.fadetime)
		self.sched_agent(ag, 0, self.prevchannel)

class Volume(EventAgent):
	name = 'set an agent\'s volume by command'
	def __init__(self, ag, initvol=1.0):
		EventAgent.__init__(self)
		if (type(ag) == types.StringType):
			clas = load_class_by_name(ag)
			ag = clas()
		self.runagent = ag
		self.initvol = float(initvol)
		self.lastvol = self.initvol
		self.ismute = 0
	def run(self):
		chan = self.new_channel(self.initvol)
		self.sched_agent(self.runagent, 0, chan)
		self.post_agent(self, chan)
	watch_events = ['volume', 'mute', 'unmute', 'flipmute']
	def receive(self, event):
		dur = None
		if (event[0] == 'volume'):
			if (event[1] == 'up'):
				vol = self.lastvol + 0.1
				vol = min(vol, 1.0)
			elif (event[1] == 'down'):
				vol = self.lastvol - 0.1
				vol = max(vol, 0.0)
			else:
				vol = float(event[1])
			if (len(event) > 2):
				dur = float(event[2])
			self.lastvol = vol
			self.ismute = 0
			if (dur == None):
				self.channel.set_volume(vol)
			else:
				self.channel.set_volume(vol, dur)
		elif (event[0] == 'mute' 
				or (event[0] == 'flipmute' and self.ismute == 0)):
			vol = 0.0
			if (len(event) > 1):
				dur = float(event[1])
			self.ismute = 1
			if (dur == None):
				self.channel.set_volume(vol)
			else:
				self.channel.set_volume(vol, dur)
		elif (event[0] == 'unmute' 
				or (event[0] == 'flipmute' and self.ismute == 1)):
			vol = self.lastvol
			if (len(event) > 1):
				dur = float(event[1])
			self.ismute = 0
			if (dur == None):
				self.channel.set_volume(vol)
			else:
				self.channel.set_volume(vol, dur)

class RemoteVolume(Volume):
	name = 'set an agent\'s volume by remote control'
	def run(self):
		Volume.run(self)
		ag = RemoteTranslateVolume()
		self.post_agent(ag)

class RemoteTranslateVolume(EventAgent):
	name = 'set an agent\'s volume by command'
	watch_events = 'remote'
	def receive(self, event):
		if (event[1] == 'volup'):
			self.send_event( ('volume', 'up') )
		elif (event[1] == 'voldown'):
			self.send_event( ('volume', 'down') )
		elif (event[1] == 'mute'):
			self.send_event( ('flipmute',) )

class Shutdown(EventAgent):
	name = 'shut down Boodler by command'
	watch_events = 'shutdown'
	def receive(self, event):
		if (len(event) >= 2):
			fadetime = float(event[1])
			fadeagent = FadeOutAgent(fadetime)
		else:
			fadeagent = FadeOutAgent()
		self.sched_agent(fadeagent, 0, self.get_root_channel())

class TimeSpeak(EventAgent):
	name = 'speak time upon command'
	watch_events = 'time'
	def receive(self, event):
		clas = load_class_by_name('timespeak.Now')
		self.sched_agent(clas())

class Catalog(EventAgent):
	name = 'remote-control soundscape menu'
	def __init__(self, *arglist):
		EventAgent.__init__(self)
		self.classlist = []
		self.fadetime = 2.0
		for arg in arglist:
			self.classlist.append(arg)
		self.pos = 0
	def run(self):
		ag = Agents(self.fadetime)
		self.post_agent(ag)
		self.post_agent(self)
		self.send_event( ('agent', self.classlist[self.pos]) )
	watch_events = 'remote'
	def receive(self, event):
		newpos = self.pos
		count = len(self.classlist)
		if (event[1] == 'chanup'):
			newpos = ((self.pos+1) % count)
		elif (event[1] == 'chandown'):
			newpos = ((self.pos+count-1) % count)
		elif (event[1] in ['1', '2', '3', '4', '5', '6', '7', '8', '9']):
			val = int(event[1]) - 1
			if (val >= 0 and val < count):
				newpos = val
		if (newpos != self.pos):
			self.pos = newpos
			self.send_event( ('agent', self.classlist[self.pos]) )

class Leash(Agent):
	name = 'leash user interface'
	def run(self):
		ag = Agents()
		self.post_agent(ag)
		ag = TimeSpeak()
		self.post_agent(ag)

