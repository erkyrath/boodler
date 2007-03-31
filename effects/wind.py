from boodle.agent import *
import random

wind_sounds = ['environ/wind-steady.aiff', 'environ/wind-far.aiff']
wind_gust_sounds = [
	'environ/wind-gust-1.aiff', 
	'environ/wind-gust-2.aiff', 
	'environ/wind-gust-3.aiff',
]

class SteadyWind(Agent):
	name = 'steady monotonous wind'
	def __init__(self, pitch=1.0):
		Agent.__init__(self)
		self.pitch = float(pitch)
		self.pan = random.uniform(-0.5, 0.5)
		self.snd = random.choice(wind_sounds)
	def run(self):
		dur = self.sched_note_pan(self.snd, self.pan, self.pitch)
		self.resched(dur)

class VaryingWind(Agent):
	name = 'layers of wind fading in and out'
	def run(self):
		pitch = random.uniform(0.35, 1.5)
		self.sched_agent(FadeInOutAgent(SteadyWind(pitch), 1, 4))
		delay = random.uniform(2, 4)
		self.resched(delay)

class HeavyVaryingWind(Agent):
	name = 'more layers of wind fading in and out'
	def run(self):
		pitch = random.uniform(0.35, 1.5)
		self.sched_agent(FadeInOutAgent(SteadyWind(pitch), 1, 4))
		delay = random.uniform(1.5, 2.0)
		self.resched(delay)

class SteadyGale(Agent):
	name = 'hard winds'
	def __init__(self, pitch=1):
		Agent.__init__(self)
		self.pitch = float(pitch)
	def run(self):
		dur = self.sched_note('environ/wind-heavy.aiff', self.pitch)
		self.resched(dur)

class VaryingGale(Agent):
	name = 'successive hard winds'
	def run(self):
		pitch = random.uniform(0.6, 1.3)
		len = random.uniform(3, 6)
		ag = SteadyGale(pitch)
		self.sched_agent(FadeInOutAgent(ag, len-2, 2))
		self.resched(len)

class IntermittentGale(Agent):
	name = 'sequences of hard winds, fading in and out'
	def __init__(self, mindelay=9, maxdelay=12):
		Agent.__init__(self)
		self.mindelay = float(mindelay)
		self.maxdelay = float(maxdelay)
	def run(self):
		self.sched_agent(FadeInOutAgent(VaryingGale(), 2, 5))
		delay = random.uniform(self.mindelay, self.maxdelay)
		self.resched(delay)

class GustyWind(Agent):
	name = 'occasional gusts'
	def __init__(self, mindelay=2, maxdelay=4):
		Agent.__init__(self)
		self.mindelay = float(mindelay)
		self.maxdelay = float(maxdelay)
	def run(self):
		pitch = random.uniform(0.3, 1.25)
		snd = random.choice(wind_gust_sounds)
		self.sched_note(snd, pitch)
		delay = random.uniform(self.mindelay, self.maxdelay)
		self.resched(delay)

class Windstorm(Agent):
	name = 'many winds'
	def run(self):
		self.sched_agent(VaryingWind())
		chan = self.new_channel(0.66)
		self.sched_agent(GustyWind(6, 15), 5, chan)
		chan = self.new_channel(0.75)
		self.sched_agent(IntermittentGale(15, 30), 2, chan)

class GentleWindstorm(Agent):
	name = 'many winds, gentler'
	def run(self):
		self.sched_agent(VaryingWind())
		chan = self.new_channel(0.66)
		self.sched_agent(GustyWind(15, 60), 5, chan)
		chan = self.new_channel(0.75)
		self.sched_agent(IntermittentGale(30, 120), 2, chan)
