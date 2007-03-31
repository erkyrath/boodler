from boodle.agent import *
import random

railsounds = [
	'transport/railcar.aiff',
	'transport/railcar-low.aiff'
]

carsounds = [
	'transport/car-pass-1.aiff',
	'transport/car-pass-2.aiff'
]

trucksounds = [
	'transport/airhorn-1.aiff',
	'transport/airhorn-2.aiff'
]

crossingsounds = [
	'transport/railroad-bell.aiff',
	'transport/railroad-bell-soft.aiff'
]

class Track(Agent):
	name = 'steady railroad tracks'
	def __init__(self, pitch=1.0):
		Agent.__init__(self)
		self.pitch = float(pitch)
		self.snd = random.choice(railsounds)
	def run(self):
		dur = self.sched_note(self.snd, self.pitch)
		self.resched(dur)

class VaryingTrack(Agent):
	name = 'railroad tracks changing over time'
	def run(self):
		pitch = random.uniform(0.85, 1.15)
		delay = random.uniform(5, 10)
		self.sched_agent(FadeInOutAgent(Track(pitch), delay-3, 3))
		self.resched(delay)

class BusyRailway(Agent):
	name = 'the rail line'
	def run(self):
		self.sched_agent(VaryingTrack())
		self.sched_agent(OccasionalCrossing(), 20)

class Highway(Agent):
	name = 'steady highway noise'
	def run(self):
		snd = random.choice(carsounds)
		pitch = random.uniform(0.6, 1.5)
		self.sched_note(snd, pitch)
		if (random.uniform(0, 1) < 0.15):
			subdelay = random.uniform(0.15, 0.55)
			pitch = pitch * random.uniform(0.95, 1.05)
			self.sched_note(snd, pitch, 0.9, subdelay)
		delay = random.uniform(0.2, 5.0)
		self.resched(delay)

class BusyHighway(Agent):
	name = 'steady highway noise, with variations'
	def run(self):
		self.sched_agent(Highway())
		self.sched_agent(OccasionalCrossing(), 20)
		chan = self.new_channel(0.80)
		self.sched_agent(OccasionalTruck(), 35, chan)
		chan = self.new_channel(0.40)
		self.sched_agent(OccasionalTruck(), 10, chan)

class OccasionalTruck(Agent):
	name = 'a truck now and then'
	def run(self):
		snd = random.choice(trucksounds)
		pitch = random.uniform(0.75, 1.25)
		vol = random.uniform(0.5, 1)
		pan = random.uniform(-1, 1)
		self.sched_note_pan(snd, pan, pitch, vol)
		delay = random.uniform(0.25, 90)
		self.resched(delay)

class RailroadCrossing(Agent):
	name = 'random railroad crossing'
	def __init__(self):
		Agent.__init__(self)
		self.snd = random.choice(crossingsounds)
		self.pitch = random.uniform(0.8, 1.2)
		self.vol = random.uniform(0.5, 1)
		self.pan = random.uniform(-0.75, 0.75)
	def run(self):
		dur = self.sched_note_pan(self.snd, self.pan, self.pitch, self.vol)
		self.resched(dur)

class OccasionalCrossing(Agent):
	name = 'a railroad crossing now and then'
	def run(self):
		ag = FadeInOutAgent(RailroadCrossing(), 1, 5)
		self.sched_agent(ag)
		delay = random.uniform(30, 120)
		self.resched(delay)

class Transfer(Agent):
	name = 'varying modes of transit'
	def run(self):
		chan0 = self.new_channel(0)
		chan1 = self.new_channel(1)
		self.sched_agent(BusyHighway(), 0, chan0)
		self.sched_agent(BusyRailway(), 0, chan1)
		self.sched_agent(CrossFade(chan0, chan1, 45, 75))

class CrossFade(Agent):
	name = 'fade back and forth between two channels'
	def __init__(self, chan0, chan1, mindelay=5, maxdelay=10):
		Agent.__init__(self)
		self.chans = (chan0, chan1)
		self.mindelay = float(mindelay)
		self.maxdelay = float(maxdelay)
	def run(self):
		delay = random.uniform(self.mindelay, self.maxdelay)
		(chan0, chan1) = self.chans
		chan0.set_volume(1, delay)
		chan1.set_volume(0, delay)
		self.chans = (chan1, chan0)
		self.resched(delay+2)
