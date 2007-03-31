from boodle.agent import *
import play
import random

long_sounds = [
	'insect/complex_trilling_trig.aiff',
	'insect/everglades_conehead.aiff',
	'insect/fastcalling_tree_cricket.aiff',
	'insect/melodious_ground_cricket.aiff',
	'insect/pine_tree_cricket.aiff',
	'insect/seashore_meadow_katydid.aiff',
	'insect/texas_meadow_katydid.aiff',
	'insect/tinking_trig.aiff',
]

short_sounds = [
	'insect/house_cricket.aiff',
	'insect/jamaican_field_cricket.aiff',
	'insect/japanese_burrowing_cricket.aiff',
	'insect/robust_shieldback.aiff',
	'insect/sand_field_cricket.aiff',
	'insect/slightly_musical_conehead.aiff',
	'insect/southern_ground_cricket.aiff',
	'insect/syncopated_scaly_cricket.aiff',
	'insect/tinkling_ground_cricket.aiff',
	'insect/tropical_house_cricket.aiff',
	'insect/vocal_field_cricket.aiff',
]

class VaryingContinuo(Agent):
	name = 'continuous cricket sounds, changing occasionally'
	def run(self):
		snd = random.choice(long_sounds)
		dur = random.uniform(30, 60)
		ag = FadeInOutAgent(play.RepeatSound(snd), dur, 8)
		self.sched_agent(ag)
		self.resched(dur+8)

class VaryingChirps(Agent):
	name = 'cricket chirps, changing occasionally'
	def run(self):
		snd = random.choice(short_sounds)
		dur = random.uniform(20, 40)
		ag = FadeInOutAgent(play.RepeatSound(snd), dur, 4)
		self.sched_agent(ag)
		self.resched((dur+8) / 2)

class OccasionallyVaryingChirps(Agent):
	name = 'cricket chirps, overlapping or changing occasionally'
	def __init__(self):
		Agent.__init__(self)
		self.newsound()
	def newsound(self):
		self.snd = random.choice(short_sounds)
		self.numreps = random.randint(5, 10)
	def run(self):
		self.numreps = self.numreps - 1
		if (self.numreps < 0):
			self.newsound()
		dur = random.uniform(10, 20)
		ag = FadeInOutAgent(play.RepeatSound(self.snd), dur, 4)
		self.sched_agent(ag)
		self.resched(dur+4)

class CricketMeadow(Agent):
	name = 'Texas Meadow Katydid and friends'
	def run(self):
		chan = self.new_channel(0.25)
		self.sched_agent(play.RepeatSound('insect/texas_meadow_katydid.aiff'), 0, chan)
		chan = self.new_channel(1)
		self.sched_agent(OccasionallyVaryingChirps(), 3, chan)

class ManyCrickets(Agent):
	name = 'several kinds of crickets at once'
	def __init__(self, numbugs=3):
		Agent.__init__(self)
		self.numbugs = int(numbugs)
	def run(self):
		chan = self.new_channel(0.3)
		self.sched_agent(VaryingContinuo(), 0, chan)
		for ix in range(self.numbugs-1):
			chan = self.new_channel(1)
			self.sched_agent(OccasionallyVaryingChirps(), 2*ix, chan)
