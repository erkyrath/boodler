from boodle.agent import *
import play
import manager
import random

# Contributed by Peter Williams (peter@newton.cx)
# Some code cleanup by Andrew Plotkin

rainsounds = [
	'environ/rain-heavy.aiff',
	'environ/rain-med.aiff',
	'environ/rain-on-leaves.aiff',
	'environ/rain-splashy.aiff',
	'environ/rain-splashy-low.aiff',
	'environ/rain-thin.aiff'
]

watersounds = [
	'environ/water-pouring.aiff',
	'environ/water-rapids.aiff',
	'environ/water-rushing.aiff',
	'environ/water-trickle.aiff'
]

thundersounds = [
	'environ/thunder-low.aiff',
	'environ/thunder-low-1.aiff',
	'environ/thunder-low-2.aiff'
]

insectsounds = [
	'insect/bee-swarm.aiff',
	'insect/complex_trilling_trig.aiff',
	'insect/everglades_conehead.aiff',
	'insect/fastcalling_tree_cricket.aiff',
	'insect/house_cricket.aiff',
	'insect/jamaican_field_cricket.aiff',
	'insect/japanese_burrowing_cricket.aiff',
	'insect/melodious_ground_cricket.aiff',
	'insect/pine_tree_cricket.aiff',
	'insect/robust_shieldback.aiff',
	'insect/sand_field_cricket.aiff',
	'insect/seashore_meadow_katydid.aiff',
	'insect/slightly_musical_conehead.aiff',
	'insect/southern_ground_cricket.aiff',
	'insect/syncopated_scaly_cricket.aiff',
	'insect/texas_meadow_katydid.aiff',
	'insect/tinking_trig.aiff',
	'insect/tinkling_ground_cricket.aiff',
	'insect/tropical_house_cricket.aiff',
	'insect/vocal_field_cricket.aiff',
]

frogsounds = [
	'animal/frog-bullfrog1.aiff',
	'animal/frog-bullfrog2.aiff',
	'animal/frog-bullfrog3.aiff',
	'animal/frog-cheep.aiff'
]

class Rainforest(Agent):
	name = 'rain in the rainforest'
	def run(self):
		self.sched_agent (RainSounds ())
		self.sched_agent (WaterSounds ())
		self.sched_agent (LightWind (0.1))
		ag = play.IntermittentSoundsOpts(15, 40, 0.6, 1.4, 0.15, 0.45, insectsounds)
		self.sched_agent(ag, random.uniform(3, 30))
		ag = play.IntermittentSoundsOpts(30, 70, 0.6, 1.4, 0.35, 0.65, insectsounds)
		self.sched_agent(ag, random.uniform(3, 30))
		ag = play.IntermittentSoundsOpts(10, 40, 0.6, 1.4, 0.15, 0.45, frogsounds)
		self.sched_agent(ag, random.uniform(3, 30))
		ag = play.IntermittentSoundsOpts(30, 50, 0.6, 1.4, 0.35, 0.65, frogsounds)
		self.sched_agent(ag, random.uniform(3, 30))
		ag = play.IntermittentSoundsOpts(10, 50, 0.6, 1.4, 0.35, 0.65, thundersounds)
		self.sched_agent(ag, random.uniform(3, 30))

class RainSounds(Agent):
	name = 'simple quiet rain sounds'
	def run(self):
		ag = play.RepeatSoundShuffle(30, 90, 12, rainsounds)
		ag2 = manager.VolumeModulate(ag, 0.5)
		self.sched_agent(ag2)
		
class WaterSounds(Agent):
	name = 'simple quiet water sounds'
	def run(self):
		ag = play.RepeatSoundShuffle(30, 90, 12, watersounds)
		ag2 = manager.VolumeModulate(ag, 0.3)
		self.sched_agent(ag2)

class LightWind(Agent):
	name = 'light wind'
	def __init__ (self, vol=0.075, delta=0.05):
		Agent.__init__(self)
		self.vol = float(vol)
		self.delta = float(delta)
	def run(self):
		ag = manager.VolumeModulate(play.RepeatSound('environ/wind-far.aiff'),
			self.vol, self.delta)
		self.sched_agent(ag)

