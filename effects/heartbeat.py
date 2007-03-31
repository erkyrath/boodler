from boodle.agent import *
import random

sounds = [ 'environ/heartbeat.aiff', 'environ/heartbeat-low.aiff' ]

class OneBeat(Agent):
	name = 'a heartbeat'
	def __init__(self, pitch=1.0):
		Agent.__init__(self)
		self.pitch = float(pitch)
		self.pan = random.uniform(-0.5, 0.5)
	def run(self):
		len = self.sched_note_pan(sounds[0], self.pan, self.pitch)
		self.resched(len)

class OneSoftBeat(Agent):
	name = 'a soft heartbeat'
	def __init__(self, pitch=1.0):
		Agent.__init__(self)
		self.pitch = float(pitch)
		self.pan = random.uniform(-0.5, 0.5)
	def run(self):
		len = self.sched_note_pan(sounds[1], self.pan, self.pitch)
		self.resched(len)

class OneRandomBeat(Agent):
	name = 'a random heartbeat'
	def __init__(self, pitch=1.0):
		Agent.__init__(self)
		self.pitch = float(pitch)
	def run(self):
		if (random.uniform(0.0, 1.0) < 0.6):
			ag = OneBeat(self.pitch)
		else:
			ag = OneSoftBeat(self.pitch)
		self.sched_agent(ag)

class ManyBeats(Agent):
	name = 'several heartbeats'
	def __init__(self, numbeats=4):
		Agent.__init__(self)
		self.numbeats = int(numbeats)
	def run(self):
		for ix in range(self.numbeats):
			pitch = random.uniform(0.5, 1.5)
			delay = random.uniform(0.0, 1.0)
			ag = OneRandomBeat(pitch)
			self.sched_agent(ag, delay)

class ComeGoBeat(Agent):
	name = 'heartbeat fades in and out'
	def __init__(self, fadetime=4.0, livetime=10.0):
		Agent.__init__(self)
		self.fadetime = fadetime
		self.livetime = livetime
	def run(self):
		chan = self.new_channel(0)
		pitch = random.uniform(0.5, 1.5)
		self.sched_agent(OneRandomBeat(pitch), 0, chan)
		chan.set_volume(1, self.fadetime)
		ag = FadeOutAgent(self.fadetime)
		self.sched_agent(ag, self.livetime, chan)

class ComingAndGoing(Agent):
	name = 'heartbeats coming and going'
	def run(self):
		interval = 15.0
		numbeats = 4
		total = (2 * numbeats - 1) * interval + 4 + 2
		for ix in range(numbeats):
			ag = ComeGoBeat(4, numbeats * interval)
			self.sched_agent(ag, ix * interval)
		self.resched(total)
