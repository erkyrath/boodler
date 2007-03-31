from boodle.agent import *
import random

sounds = [
	'environ/droplet-plink-reverb.aiff',
	'environ/droplet-plink-reverb-2.aiff',
	'environ/droplet-plink-reverb-3.aiff'
]

class Drip(Agent):
	name = 'one dripping stalactite'
	def __init__(self):
		Agent.__init__(self)
		self.delay = random.uniform(2.0, 9.0)
		self.snd = random.choice(sounds)
		self.pitch = random.uniform(0.3, 1.7)
		self.vol = random.uniform(0.3, 1.0)
		self.pan = random.uniform(-0.9, 0.9)
	def run(self):
		ranpitch = random.uniform(0.98, 1.02)
		self.sched_note_pan(self.snd, self.pan, self.pitch * ranpitch, self.vol)
		randelay = random.uniform(0.0, 0.5)
		self.resched(self.delay + randelay)

class Still(Agent):
	name = 'stalactites dripping into a still pool'
	def run(self):
		ag = FadeInOutAgent(Drip(), 2, 45)
		self.sched_agent(ag)
		self.resched(15)

class Water(Agent):
	name = 'lapping water nearby'
	def __init__(self):
		Agent.__init__(self)
		self.pitch = random.uniform(0.6, 1.5)
		self.vol = random.uniform(0.4, 1.0)
	def run(self):
		dur = self.sched_note('environ/waves-floopy.aiff', self.pitch, self.vol)
		self.resched(dur)

class WaterFlow(Agent):
	name = 'soft varying water'
	def run(self):
		ag = FadeInOutAgent(Water(), 2, 20)
		self.sched_agent(ag)
		self.resched(30)

class Cavern(Agent):
	name = 'rockpool at mountain\'s root'
	def run(self):
		self.sched_agent(Still())
		chan = self.new_channel(0.25)
		self.sched_agent(WaterFlow(), 0, chan)
