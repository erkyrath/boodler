from boodle.agent import *
import play
import manager
import random
import pwrain

# Contributed by Owen Williams (ywwg@usa.net)
# Little pieces by Peter Williams (peter@newton.cx)
#   (see also pwrain.py)
# Some code cleanup by Andrew Plotkin

# Rain:  This module simulates a rainstorm on a hot summer's day.
#  Changing the timing would require lots of number twiddling, maybe
#  someone smart can make it cleaner.

watersounds = pwrain.watersounds
thundersounds = pwrain.thundersounds
insectsounds = pwrain.insectsounds
frogsounds = pwrain.frogsounds

class RainForever(Agent):
	name = 'the storm crests and ebbs'
	def run(self):
		#print("begin raining")
		ag = OneStorm()
		fader = FadeInOutAgent(ag, 60*60, 1)
		self.sched_agent(fader)
		self.resched(60*60)

class OneStorm(Agent):
	name = 'a single hour-long rainstorm'
	def run(self):
		raintime = 8*60 + random.uniform(-120, 120)  #for readability: 8 mins +/- 2 min
		totaltime = raintime
		ag = NoStormYet()
		fader = FadeInOutDifAgent (ag, raintime, 3, 10) 
		self.sched_agent (fader)

		ag = Crickets() #they die pretty soon into the storm
		fader = FadeInOutDifAgent (ag, totaltime+random.uniform(0,30), 3, 2*60) 
		self.sched_agent (fader)

		lightstormtime = 9.5*60 + random.uniform(-120,120)
		ag = LightStorm()
		chan = self.new_channel (1)
		fader = FadeInOutDifAgent (ag, lightstormtime, 10, 20)	 
		self.sched_agent(fader, totaltime, chan)  #wait sum of previous channels before going	  
		totaltime = totaltime + lightstormtime	#because of +=, this stays correct

		#now that we know when the medstorm is happening (totaltime), 
		#we know when to get rid of the animals
		ag = Frogs()
		fader = FadeInOutDifAgent (ag, totaltime+random.uniform(0,3*60), 3, 3*60) #crickets chirp til it gets heavy
		self.sched_agent (fader)

		#ok now back to figuring out when the storm changes over
		medstormtime = 9*60 + random.uniform(-120,120)
		ag = MediumStorm()
		chan = self.new_channel (1)
		fader = FadeInOutDifAgent (ag, medstormtime, 10, 20)	 
		self.sched_agent(fader, totaltime, chan)	  
		totaltime = totaltime + medstormtime
		
		heavstormtime = 7*60 + random.uniform(-120,120)
		ag = HeavyStorm()
		chan = self.new_channel (1)
		fader = FadeInOutDifAgent (ag, heavstormtime, 10, 20)   
		self.sched_agent(fader, totaltime, chan)  
		totaltime = totaltime + heavstormtime

		#now that we know when the storm is starting to die, we can
		#talk about the animals Part Two.
		ag = Frogs()
		chan = self.new_channel (1)
		animal2time = totaltime+random.uniform(5*60,7*60)
		fader = FadeInOutDifAgent (ag, 60*60-animal2time, 30, 45) #they do start up again however
										   #note how it works out to 60 like below
		self.sched_agent (fader, animal2time, chan) #post storm animals

		#back to the storm
		medstorm2time = 9*60 + random.uniform(-120,120)
		ag = MediumStorm()
		chan = self.new_channel (1)
		fader = FadeInOutDifAgent (ag, medstorm2time, 10, 20)
		self.sched_agent(fader, totaltime, chan)
		totaltime = totaltime + medstorm2time

		ag = Crickets()
		chan = self.new_channel (1)
		cricket2time = totaltime+random.uniform(15,60)
		fader = FadeInOutDifAgent (ag, 60*60-cricket2time, 30, 45)
		self.sched_agent (fader, cricket2time, chan) #post storm crickets

		lightstorm2time = 9.5*60 + random.uniform(-120,120)
		ag = LightStorm()
		chan = self.new_channel (1)
		fader = FadeInOutDifAgent (ag, lightstorm2time, 10, 30)
		self.sched_agent(fader, totaltime, chan)
		totaltime = totaltime + lightstorm2time

		endstormtime = 60*60 - totaltime #to even things out to 60 always :)
		#not actually necessary because the caller
		#shuts us down at 60, but it's clean
		ag = NoStormYet()
		chan = self.new_channel (1)
		fader = FadeInOutDifAgent (ag, endstormtime, 10, 30)
		self.sched_agent(fader, totaltime, chan)

#various stages of storm		
class NoStormYet(Agent):
	name = 'distant thunder, light plinking'
	def run(self):
		#print("no storm yet")
		self.sched_agent(Wind(0.04))
		self.sched_agent(WaterSounds(0.075))
		self.sched_agent(Thunder(20, 35, 0.4), random.uniform(8,14))
		self.sched_agent(Plink(0.1, 4, 2))


class LightStorm(Agent):
	name = 'light rain'
	def run(self):
		#print("light storm")
		self.sched_agent(Wind(0.05))
		self.sched_agent(WaterSounds(0.1))
		self.sched_agent(Thunder(7, 15, 0.5), random.uniform(7,13))
		self.sched_agent(LightRain(0.3))
		self.sched_agent(Plink(0.15, 1, 0.5))

class MediumStorm(Agent):
	name = 'medium rain'
	def run(self):
		#print("medium storm")
		self.sched_agent(Wind(0.1))
		self.sched_agent(WaterSounds(0.3))
		self.sched_agent(Thunder(7, 15, 0.8), random.uniform(4,10))
		self.sched_agent(IntenseThunder(60, 90, 0.7), random.uniform(1*60,3*60))  #just a touch
		self.sched_agent(LightRain(0.3))
		self.sched_agent(MediumRain(0.65))
		self.sched_agent(Plink(0.2, 0.75, 0.4))

class HeavyStorm(Agent):
	name = 'heavy rain'
	def run(self):
		#print("heavy storm")
		self.sched_agent(Wind(0.15))
		self.sched_agent(WaterSounds(0.5))
		self.sched_agent(Thunder(2, 8, 1), random.uniform(2,5))
		self.sched_agent(MediumRain(0.65))
		self.sched_agent(HeavyRain(0.7))
		self.sched_agent(IntenseThunder(13, 30, 1), random.uniform(5,10))
		self.sched_agent(Plink(0.4, 0.4, 0.3))


# The instruments

class Crickets(Agent):
	name = 'bugs'
	def __init__(self, vol=0.025):
		Agent.__init__(self)
		self.vol = float(vol)
	def run(self):
		ag = play.RepeatSound('insect/melodious_ground_cricket.aiff')
		ag2 = manager.VolumeModulate(ag, self.vol, self.vol, 3, 10, 20, 45)
		self.sched_agent(ag2, 0.00)

		ag = play.RepeatSound('insect/everglades_conehead.aiff')
		ag2 = manager.VolumeModulate(ag, self.vol, self.vol, 3, 10, 20, 45)
		self.sched_agent(ag2, 0.05)

		ag = play.RepeatSound('insect/pine_tree_cricket.aiff')
		ag2 = manager.VolumeModulate(ag, self.vol*0.75, self.vol*0.75, 3, 10, 20, 45)
		self.sched_agent(ag2, 0.10)

		ag = play.RepeatSound('insect/vocal_field_cricket.aiff')
		ag2 = manager.VolumeModulate(ag, self.vol, self.vol*0.5, 3, 10, 20, 45)
		self.sched_agent(ag2, 0.15)

		ag = play.IntermittentSoundsPanOpts(10, 20, 0.8, 1.2, 0, 0.1, 0.9, insectsounds)
		self.sched_agent(ag, random.uniform(3, 20))
		ag = play.IntermittentSoundsPanOpts(20, 40, 0.8, 1.2, 0, 0.2, 0.9, insectsounds)
		self.sched_agent(ag, random.uniform(3, 20))

class Frogs(Agent):
	name = 'frogs'
	def __init__(self, vol=0.05):
		Agent.__init__(self)
		self.vol = float(vol)
	def run(self):
		ag = play.RepeatSound('animal/frog-cheep.aiff')
		ag2 = manager.VolumeModulate(ag, self.vol, self.vol*0.1, 3, 10, 20, 45)
		self.sched_agent(ag2)
		ag = play.IntermittentSoundsPanOpts(3, 8, 0.8, 1.2, 0, self.vol, 0.9, frogsounds)
		self.sched_agent(ag, random.uniform(3, 10))
		ag = play.IntermittentSoundsPanOpts(6, 12, 0.8, 1.2, 0, 2*self.vol, 0.9, frogsounds)
		self.sched_agent(ag, random.uniform(3, 10))

#Peter Williams wrote this too

class WaterSounds(Agent):
	name = 'simple quiet water sounds'
	def __init__(self, vol=0.3):
		Agent.__init__(self)
		self.vol = float(vol)
	def run(self):
		ag = play.RepeatSound('environ/water-rushing.aiff')
		ag2 = manager.VolumeModulate(ag, self.vol, self.vol, 3, 10, 20, 45)
		self.sched_agent(ag2)

class Wind(Agent):
	name = 'light wind'
	def __init__(self, vol=0.05):
		Agent.__init__(self)
		self.vol = float(vol)
	def run(self):
		chan = self.new_channel(self.vol)
		self.sched_agent(play.RepeatSound('environ/wind-far.aiff'), 0, chan)

class Plink(Agent):
	name = 'plinking'
	def __init__(self, vol=0.1, plink_delay=3, plink_deviation=1):
		Agent.__init__(self)
		self.plink_delay = float(plink_delay)
		self.plink_deviation = float(plink_deviation)
		self.vol = float(vol)
	def run(self):
		pan = random.uniform(-.5,.5)
		pitch = random.uniform(0.8, 1.2)
		vol = random.uniform(self.vol-(self.vol*0.1), self.vol+(self.vol*0.1))
		self.sched_note_pan('environ/droplet-plink.aiff', pan, pitch, vol)
		delay = self.plink_delay+random.uniform(0-self.plink_deviation,self.plink_deviation)
		self.resched(delay)	

#thunder levels (2)
class Thunder(Agent):
	name = 'thunder'
	def __init__(self, min=1, max=2, vol=1):
		Agent.__init__(self)
		self.min = float(min)
		self.max = float(max)
		self.vol = float(vol)
	def run(self):
		snd = random.choice(thundersounds)
		pitch = random.uniform(0.75, 1)
		vol = random.uniform(self.vol-.2, self.vol+.2)
		pan = random.uniform(-1, 1)
		self.sched_note_pan(snd, pan, pitch, vol)
		delay = random.uniform(self.min, self.max)
		self.resched(delay)

class IntenseThunder(Agent):
	name = 'thunder'
	def __init__(self, min=5, max=10, vol=1):
		Agent.__init__(self)
		self.min = float(min)
		self.max = float(max)
		self.vol = float(vol)
	def run(self):
		pitch = random.uniform(0.75, 1)
		vol = random.uniform(self.vol-.2, self.vol+.2)
		pan = random.uniform(-1, 1)
		self.sched_note_pan('environ/thunder-tense.aiff', pan, pitch, vol)
		delay = random.uniform(self.min, self.max)
		self.resched(delay)


#rain levels(3)
class LightRain(Agent):
	name = 'light rain'
	def __init__(self, vol=0.05):
		Agent.__init__(self)
		self.vol = float(vol)
	def run(self):
		chan = self.new_channel(self.vol)
		self.sched_agent(play.RepeatSound('environ/rain-thin.aiff'), 0, chan)

class MediumRain(Agent):
	name = 'medium rain'
	def __init__(self, vol=1):
		Agent.__init__(self)
		self.vol = float(vol)
	def run(self):
		chan = self.new_channel(self.vol*1)
		self.sched_agent(play.RepeatSound('environ/rain-med.aiff'), 0, chan)
		chan = self.new_channel(self.vol*0.7)
		self.sched_agent(play.RepeatSound('environ/rain-splatter.aiff'), 0, chan)
		chan = self.new_channel(self.vol*0.6)
		self.sched_agent(play.RepeatSound('environ/rain-on-leaves.aiff'), 0, chan)

class HeavyRain(Agent):
	name = 'heavy rain'
	def __init__(self, vol=1):
		Agent.__init__(self)
		self.vol = float(vol)
	def run(self):
		chan = self.new_channel(self.vol*0.8)
		self.sched_agent(play.RepeatSound('environ/rain-heavy.aiff'), 0, chan)
		chan = self.new_channel(self.vol*1)
		self.sched_agent(play.RepeatSound('environ/rain-on-leaves.aiff'), 0, chan)
		#chan = self.new_channel(self.vol*0.9)
		#self.sched_agent(play.RepeatSound('environ/rain-splashy.aiff'), 0, chan)
		chan = self.new_channel(self.vol*0.9)
		self.sched_agent(play.RepeatSound('environ/rain-splatter.aiff'), 0, chan)




#  USEFUL UTILITIES

# [most utility functions contributed by Peter Williams;
#  replaced with generalized equivalents in the "play" and "manager" modules 
#  --Z]

# oh no wait I wrote this one

class FadeInOutDifAgent(Agent):
	"""FadeInOutAgent(agent, liveinterval, fadeinint, fadeoutint):
fade in at one rate, fade out at another

	"""
	name = 'fade in, fade out, stop channel'
	def __init__(self, agentinst, liveinterval=10.0, fadeinint=1.0, fadeoutint=1.0):
		Agent.__init__(self)
		self.agentinst = agentinst
		self.liveinterval = liveinterval
		self.fadeinint = fadeinint
		self.fadeoutint = fadeoutint
	def run(self):
		chan = self.new_channel(0)
		self.sched_agent(self.agentinst, 0, chan)
		chan.set_volume(1, self.fadeinint)
		ag = FadeOutAgent(self.fadeoutint)
		self.sched_agent(ag, self.liveinterval+self.fadeinint, chan)

