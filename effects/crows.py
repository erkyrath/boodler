from boodle.agent import *
import random

soundlist = ['bird/crow1.aiff', 'bird/crow2.aiff', 'bird/crow3.aiff', 'bird/crow4.aiff']

class ParliamentOfCrows(Agent):
	name = 'treeful of crows'
	def run(self):
		chan = self.new_channel()
		ag = SomeCrows()
		self.sched_agent(ag, 0.0, chan)
		ag = SomeCrows()
		self.sched_agent(ag, 1.0, chan)
		chan2 = self.new_channel()
		chan2.set_volume(0.3)
		ag = SomeCrows()
		self.sched_agent(ag, 2.0, chan2)
		ag = SomeCrows()
		self.sched_agent(ag, 3.0, chan2)

class SomeCrows(Agent):
	name = 'a crow'
	def run(self):
		numsquawks = random.randint(2, 5)
		pitch = random.uniform(0.76, 1.2)
		pan = random.uniform(-1, 1)
		interval = random.uniform(0.4, 0.7)
		time = 0.0
		for ix in range(numsquawks):
			sound = random.choice(soundlist)
			pitchs = pitch * random.uniform(0.95, 1.05)
			self.sched_note_pan(sound, pan, pitchs, 1.0, time)
			time = time + interval + random.uniform(-0.1, 0.1)
		self.resched(time + random.uniform(0.75, 3.5))
