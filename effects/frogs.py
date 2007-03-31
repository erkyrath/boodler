from boodle.agent import *
import random

bullfrogsounds = [
	'animal/frog-bullfrog1.aiff',
	'animal/frog-bullfrog2.aiff', 
	'animal/frog-bullfrog3.aiff'
]

class Bullfrogs(Agent):
	name = 'a frog'
	def __init__(self, mindelay=0.75, maxdelay=3.5):
		Agent.__init__(self)
		self.mindelay = float(mindelay)
		self.maxdelay = float(maxdelay)
	def run(self):
		numsquawks = random.randint(2, 5)
		pitch = random.uniform(0.75, 1.25)
		pan = random.uniform(-0.75, 0.75)
		delay = random.uniform(self.mindelay, self.maxdelay)
		time = 0.0
		for ix in range(numsquawks):
			sound = random.choice(bullfrogsounds)
			pitchs = pitch * random.uniform(0.975, 1.025)
			dur = self.sched_note_pan(sound, pan, pitchs, 1.0, time)
			time = time + dur + random.uniform(0.0, 0.3)
		self.resched(time + delay)

class Cheepers(Agent):
	name = 'cheeping frogs'
	def __init__(self, pitch=1.0):
		Agent.__init__(self)
		self.pitch = float(pitch)
	def run(self):
		dur = self.sched_note('animal/frog-cheep.aiff', self.pitch)
		self.resched(dur)

class VaryingCheepers(Agent):
	name = 'duelling cheeping frogs'
	def run(self):
		pitch = random.uniform(0.8, 1.2)
		delay = random.uniform(24, 60)
		self.sched_agent(FadeInOutAgent(Cheepers(pitch), delay-4, 4))
		self.resched(delay)

class FrogPond(Agent):
	name = 'a pondful of frogs'
	def run(self):
		ag = VaryingCheepers()
		self.sched_agent(ag)
		chan = self.new_channel(1)
		ag = Bullfrogs(10, 20)
		self.sched_agent(ag, 10, chan)
		chan = self.new_channel(0.25)
		ag = Bullfrogs(10, 20)
		self.sched_agent(ag, 2, chan)



