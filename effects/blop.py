from boodle.agent import *
import random

#sound = 'environ/droplet-bloink.aiff'
#sound = 'environ/droplet-plink.aiff'
#sound = 'percussion/wood-tap-hollow.aiff'

class BlopEchoes(Agent):
	name = 'a single echoing sequence of blop noises'
	def run(self):
		delay = random.uniform(0.3, 0.5)
		pitch = random.uniform(0.5, 1.8)
		pan = random.uniform(-1, 1)
		steps = 12
		sound = 'environ/droplet-bloink.aiff'
		for ix in range(steps):
			volume = float(steps-ix) / steps;
			self.sched_note_pan(sound, pan, pitch, volume, ix*delay)
			pitch = pitch * 0.99

class BlopSpace(Agent):
	name = 'blop noises everywhere'
	def run(self):
		self.sched_agent(BlopEchoes())
		delay = random.uniform(3.0, 5.0)
		self.resched(delay)

class TapEchoes(Agent):
	name = 'a single echoing sequence of taps'
	def run(self):
		delay = random.uniform(0.3, 0.5)
		pitch = random.uniform(0.33, 1.7)
		pan = random.uniform(-1, 1)
		steps = 12
		sound = 'percussion/wood-tap-hollow.aiff'
		for ix in range(steps):
			volume = float(steps-ix) / steps;
			self.sched_note_pan(sound, pan, pitch, volume, ix*delay)
			pitch = pitch * 0.995

class TapSpace(Agent):
	name = 'tap noises everywhere'
	def run(self):
		self.sched_agent(TapEchoes())
		delay = random.uniform(2.5, 5.0)
		self.resched(delay)

class OccasionalGong(Agent):
	name = 'come the gongen'
	def run(self):
		pitch = random.uniform(0.25, 0.8)
		self.sched_note('percussion/chinese-gong.aiff', pitch)
		delay = random.uniform(30, 120)
		self.resched(delay)

class TonkEchoes(Agent):
	name = 'a single echoing sequence of tonks'
	def run(self):
		delay = random.uniform(0.3, 0.5)
		pitch = random.uniform(0.66, 2.0)
		pan = random.uniform(-1, 1)
		steps = 12
		sound = 'percussion/drum-echoey.aiff'
		for ix in range(steps):
			volume = float(steps-ix) / steps;
			self.sched_note_pan(sound, pan, pitch, volume, ix*delay)
			pitch = pitch * 0.995

class TonkSpace(Agent):
	name = 'tonk noises everywhere'
	def run(self):
		self.sched_agent(TonkEchoes())
		delay = random.uniform(2.5, 5.0)
		self.resched(delay)

class EchoWorld(Agent):
	name = 'tock, tock, whoosha'
	def run(self):
		self.sched_agent(TapSpace())
		self.sched_agent(TonkSpace(), 7)
		chan = self.new_channel(0.4)
		self.sched_agent(OccasionalGong(), 15, chan)

