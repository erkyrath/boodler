from boodle.agent import *
import random

snd = 'environ/fire-small.aiff'

class Steady(Agent):
	name = 'steady fire-noise'
	def __init__(self, pitch=1.0):
		Agent.__init__(self)
		self.pitch = float(pitch)
		self.pan = random.uniform(-0.5, 0.5)
	def run(self):
		dur = self.sched_note_pan(snd, self.pan, self.pitch)
		self.resched(dur)

class Bonfire(Agent):
	name = 'varying bonfire'
	def run(self):
		pitch = random.uniform(0.333, 2.0)
		self.sched_agent(FadeInOutAgent(Steady(pitch), 1, 6))
		delay = random.uniform(3, 5)
		self.resched(delay)
