from boodle.agent import *
import random

chimesounds = [
	'mech/clock-clang.aiff',
	'mech/clock-bong.aiff',
	'mech/clock-chime.aiff'
]

class Tick(Agent):
	name = 'steady tick'
	def __init__(self, pitch=1.0):
		Agent.__init__(self)
		self.pitch = float(pitch)
		self.pan = random.uniform(-0.5, 0.5)
	def run(self):
		dur = self.sched_note_pan('mech/clock-tick.aiff', self.pan, self.pitch)
		self.resched(dur)

class ManyTicks(Agent):
	name = 'many clocks fading in and out'
	def run(self):
		pitch = random.uniform(0.333, 1.666)
		self.sched_agent(FadeInOutAgent(Tick(pitch), 2, 8))
		delay = random.uniform(5, 7)
		self.resched(delay)

class VaryingTick(Agent):
	name = 'clocks fading in and out'
	def run(self):
		pitch = random.uniform(0.333, 1.666)
		delay = random.uniform(8, 24)
		self.sched_agent(FadeInOutAgent(Tick(pitch), delay-2, 2))
		self.resched(delay)

class SteadyRandomChime(Agent):
	name = 'repeating clock chime, random parameters'
	def __init__(self):
		Agent.__init__(self)
		self.pitch = random.uniform(0.5, 2)
		self.pan = random.uniform(-0.5, 0.5)
		self.snd = random.choice(chimesounds)
	def run(self):
		dur = self.sched_note_pan(self.snd, self.pan, self.pitch)
		self.resched(dur)

class ChimeFadesOut(Agent):
	name = 'chime fades out and stops'
	def run(self):
		ag = SteadyRandomChime()
		dur = random.uniform(5, 12)
		chan = self.new_channel()
		self.sched_agent(ag, 0, chan)
		ag = FadeOutAgent(3)
		self.sched_agent(ag, dur-3, chan)

class ChimeFadesInOut(Agent):
	name = 'chime fades in, out, and stops'
	def run(self):
		ag = SteadyRandomChime()
		dur = random.uniform(8, 15)
		chan = self.new_channel(0.20)
		chan.set_volume(1, 3)
		self.sched_agent(ag, 0, chan)
		ag = FadeOutAgent(3)
		self.sched_agent(ag, dur-3, chan)

class OccasionalChimes(Agent):
	name = 'chiming every so often'
	def __init__(self, mindelay=15, maxdelay=90, useinout=0):
		Agent.__init__(self)
		self.mindelay = float(mindelay)
		self.maxdelay = float(maxdelay)
		self.useinout = int(useinout)
	def run(self):
		if (self.useinout):
			ag = ChimeFadesInOut()
		else:
			ag = ChimeFadesOut()
		self.sched_agent(ag)
		delay = random.uniform(self.mindelay, self.maxdelay)
		self.resched(delay)

class TimeSpace(Agent):
	name = 'layers of clocks and chimes'
	def run(self):
		ag = ManyTicks()
		self.sched_agent(ag)
		ag = OccasionalChimes(90, 150, 1)
		self.sched_agent(ag, 15)
		ag = OccasionalChimes(90, 150, 0)
		self.sched_agent(ag, 45)
