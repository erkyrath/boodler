from boodle.agent import *
import random
import manager

motorsounds = [
	('mech/motor-clunk-start.aiff', 'mech/motor-clunk-run.aiff', 0.5, 2),
	('mech/motor-whine-start.aiff', 'mech/motor-whine-run.aiff', 0.25, 1.75)
]

class PileDriver(Agent):
	name = 'piledriver, random parameters'
	def __init__(self):
		Agent.__init__(self)
		self.pitch = random.uniform(0.666, 1.5)
		self.pan = random.uniform(-0.5, 0.5)
	def run(self):
		dur = self.sched_note_pan('mech/piledriver.aiff', self.pan, self.pitch)
		self.resched(dur)

class PileDriverInOut(Agent):
	name = 'piledriver fades in, out, and stops'
	def __init__(self, duration=3):
		Agent.__init__(self)
		self.duration = float(duration)
	def run(self):
		ag = PileDriver()
		ag2 = FadeInOutAgent(ag, self.duration, 3)
		self.sched_agent(ag2)

class OccasionalPileDriver(Agent):
	name = 'piledriver every so often'
	def run(self):
		dur = random.uniform(3, 15)
		volume = random.uniform(0.3, 0.9)
		chan = self.new_channel(volume)
		ag = PileDriverInOut(dur)
		self.sched_agent(ag, 0, chan)
		delay = random.uniform(30, 90)
		self.resched(delay)

class MotorRun(Agent):
	name = 'motor starts and runs, random parameters'
	def __init__(self):
		Agent.__init__(self)
		(self.startsnd, self.runsnd, minpitch, maxpitch) = random.choice(motorsounds)
		self.firsttime = 1
		self.pitch = random.uniform(minpitch, maxpitch)
		self.pan = random.uniform(-0.5, 0.5)
	def run(self):
		if (self.firsttime):
			snd = self.startsnd
			self.firsttime = 0
		else:
			snd = self.runsnd
		dur = self.sched_note_pan(snd, self.pan, self.pitch)
		self.resched(dur)

class MotorRunFade(Agent):
	name = 'motor runs, fades out, and stops'
	def __init__(self, duration=3, fadetime=7):
		Agent.__init__(self)
		self.duration = float(duration)
		self.fadetime = float(fadetime)
	def run(self):
		chan = self.new_channel()
		ag = MotorRun()
		self.sched_agent(ag, 0, chan)
		ag2 = FadeOutAgent(self.fadetime)
		self.sched_agent(ag2, self.duration, chan)

class ManyMotors(Agent):
	name = 'layers of motors'
	def run(self):
		ag = MotorRunFade(6, random.uniform(12, 20))
		self.sched_agent(ag)
		delay = random.uniform(7, 13)
		self.resched(delay)

class Site(Agent):
	name = 'construction zone'
	def run(self):
		ag = ManyMotors()
		self.sched_agent(ag)
		ag = OccasionalPileDriver()
		self.sched_agent(ag, 10)

class GlassForest(Agent):
	name = 'a guy with a mallet running through a glass forest'
	def __init__(self, snd=None, mindelay=0.25, maxdelay=0.4):
		Agent.__init__(self)
		if (snd == None):
			snd = 'mech/glass-breaking-reverb.aiff'
		self.snd = snd
		self.pitch = 1.0
		self.mindelay = float(mindelay)
		self.maxdelay = float(maxdelay)
	def run(self):
		self.sched_note(self.snd, self.pitch)
		pitch = self.pitch + random.uniform(-0.05, 0.05)
		if (random.uniform(0.0, 1.0) < 0.1):
			if (pitch < 1.0):
				pitch = pitch + random.uniform(0.2, 0.3)
			else:
				pitch = pitch - random.uniform(0.2, 0.3)
		if (pitch < 0.5):
			pitch = pitch + 0.05
		if (pitch > 1.5):
			pitch = pitch - 0.05
		self.pitch = pitch
		delay = random.uniform(self.mindelay, self.maxdelay)
		self.resched(delay)

class OccasionalGlass(Agent):
	name = 'series of windows breaking'
	def run(self):
		pitch = random.uniform(0.5, 1.1)
		self.sched_note('mech/glass-breaking.aiff', pitch)
		delay = random.uniform(5.0, 10.0)
		self.resched(delay)

class GlassDisaster(Agent):
	name = 'a glass castle being destroyed'
	def run(self):
		ag = GlassForest()
		ag2 = manager.VolumeModulate(ag, 0.5, 0.2, 4, 8, 12, 16)
		self.sched_agent(ag2, 0.3)
		ag = GlassForest('mech/glass-breaking-short-reverb.aiff', 0.15, 0.33)
		ag2 = manager.VolumeModulate(ag, 0.75, 0.25, 4, 8, 12, 16)
		self.sched_agent(ag2)
		ag = OccasionalGlass()
		self.sched_agent(ag, 5)
