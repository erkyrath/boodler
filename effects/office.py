from boodle.agent import *
import random

keyboardsounds = [
	'mech/keyboard-1.aiff',
	'mech/keyboard-2.aiff',
	'mech/keyboard-3.aiff',
	'mech/keyboard-4.aiff',
	'mech/keyboard-5.aiff'
]

typewritersounds = [
	'mech/typewriter-elec-1.aiff',
	'mech/typewriter-elec-2.aiff',
	'mech/typewriter-elec-3.aiff',
	'mech/typewriter-elec-4.aiff'
]

typewriterroller = 'mech/typewriter-elec-5.aiff'

class Keyboard(Agent):
	name = 'typing on a keyboard'
	def run(self):
		snd = random.choice(keyboardsounds)
		pitch = random.uniform(0.8, 1.2)
		len = self.sched_note(snd, pitch)
		if (random.uniform(0, 1) < 0.25):
			len = len + random.uniform(0.1, 0.5)
		if (random.uniform(0, 1) < 0.1):
			len = len + random.uniform(0.5, 1.0)
		self.resched(len)

class Typewriter(Agent):
	name = 'typing on an electric typewriter'
	def __init__(self):
		Agent.__init__(self)
		self.counter = 10
	def run(self):
		self.counter = self.counter - 1
		if (self.counter <= 0):
			self.counter = random.randint(10, 20)
			snd = typewriterroller
		else:
			snd = random.choice(typewritersounds)
		pitch = random.uniform(0.97, 1.03)
		len = self.sched_note(snd, pitch)
		if (random.uniform(0, 1) < 0.5):
			len = len + random.uniform(0.1, 0.5)
		if (random.uniform(0, 1) < 0.1):
			len = len + random.uniform(0.25, 0.75)
		self.resched(len)
