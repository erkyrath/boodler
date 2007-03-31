from boodle.agent import *
import types
import random

class OneSound(Agent):
	name = 'one sound'
	def __init__(self, sound):
		Agent.__init__(self)
		self.sound = sound
	def run(self):
		self.sched_note(self.sound)

class OneSoundOpts(Agent):
	name = 'one sound with options'
	def __init__(self, sound, pitch=1.0, volume=1.0, pan=0.0):
		Agent.__init__(self)
		self.sound = sound
		self.pitch = float(pitch)
		self.volume = float(volume)
		self.pan = float(pan)
	def run(self):
		self.sched_note_pan(self.sound, self.pan, self.pitch, self.volume)

class RepeatSound(Agent):
	name = 'play sound repeated forever'
	def __init__(self, sound):
		Agent.__init__(self)
		self.sound = sound
	def run(self):
		len = self.sched_note(self.sound)
		self.resched(len)

class ExtendSound(Agent):
	name = 'play sound extended over interval'
	def __init__(self, sound, duration=10.0):
		Agent.__init__(self)
		self.sound = sound
		self.duration = float(duration)
	def run(self):
		self.sched_note_duration(self.sound, self.duration)

class SoundSequence(Agent):
	name = 'sequence of sounds'
	def __init__(self, *sounds):
		Agent.__init__(self)
		self.sounds = sounds
	def run(self):
		pos = 0
		for snd in self.sounds:
			dur = self.sched_note(snd, 1, 1, pos)
			pos = pos+dur

class RepeatSoundSequence(Agent):
	name = 'repeat sequence of sounds'
	def __init__(self, *sounds):
		Agent.__init__(self)
		self.sounds = sounds
	def run(self):
		pos = 0
		for snd in self.sounds:
			dur = self.sched_note(snd, 1, 1, pos)
			pos = pos+dur
		self.resched(pos)

class SoundShuffle(Agent):
	name = 'unending random sequence of sounds'
	def __init__(self, *sounds):
		Agent.__init__(self)
		self.sounds = sounds
	def run(self):
		snd = random.choice(self.sounds)
		dur = self.sched_note(snd)
		self.resched(dur)

def flatten(seq, el=None):
	if (type(el) == types.ListType):
		return reduce(flatten, el, seq)
	elif (type(el) == types.TupleType):
		return reduce(flatten, list(el), seq)
	elif (el == None):
		return flatten([], seq)
	else:
		return seq + [el]

# RepeatSoundShuffle, IntermittentSounds et al from ideas by Peter Williams

class RepeatSoundShuffle(Agent):
	name = 'repeat a sound for a time, then fade to another, forever'
	def __init__(self, mindelay, maxdelay, fadetime, *sounds):
		Agent.__init__(self)
		self.mindelay = float(mindelay)
		self.maxdelay = float(maxdelay)
		self.fadetime = float(fadetime)
		self.sounds = flatten(sounds)
	def run(self):
		snd = random.choice(self.sounds)
		ag = RepeatSound(snd)
		dur = random.uniform(self.mindelay, self.maxdelay)
		fader = FadeInOutAgent(ag, dur, self.fadetime)
		self.sched_agent(fader)
		self.resched(dur + self.fadetime)

class IntermittentSounds(Agent):
	name = 'intermittent random sounds'
	def __init__(self, mindelay, maxdelay, *sounds):
		Agent.__init__(self)
		self.mindelay = float(mindelay)
		self.maxdelay = float(maxdelay)
		self.sounds = flatten(sounds)
	def run(self):
		snd = random.choice(self.sounds)
		self.sched_note(snd)
		self.resched(random.uniform(self.mindelay, self.maxdelay))

class IntermittentSoundsOpts(Agent):
	name = 'intermittent random sounds with options'
	def __init__(self, mindelay, maxdelay, minpitch, maxpitch, minvol, maxvol, *sounds):
		Agent.__init__(self)
		self.mindelay = float(mindelay)
		self.maxdelay = float(maxdelay)
		self.minpitch = float(minpitch)
		self.maxpitch = float(maxpitch)
		self.minvol = float(minvol)
		self.maxvol = float(maxvol)
		self.sounds = flatten(sounds)
	def run(self):
		snd = random.choice(self.sounds)
		vol = random.uniform(self.minvol, self.maxvol)
		pitch = random.uniform(self.minpitch, self.maxpitch)
		self.sched_note(snd, pitch, vol)
		self.resched(random.uniform(self.mindelay, self.maxdelay))

class IntermittentSoundsPanOpts(IntermittentSoundsOpts):
	name = 'intermittent random sounds with more options'
	def __init__(self, mindelay, maxdelay, minpitch, maxpitch, minvol, maxvol, maxpan, *sounds):
		IntermittentSoundsOpts.__init__(self, mindelay, maxdelay, minpitch, maxpitch, minvol, maxvol, sounds)
		self.maxpan = float(maxpan)
	def run(self):
		snd = random.choice(self.sounds)
		pan = random.uniform(-self.maxpan, self.maxpan)
		vol = random.uniform(self.minvol, self.maxvol)
		pitch = random.uniform(self.minpitch, self.maxpitch)
		self.sched_note_pan(snd, pan, pitch, vol)
		self.resched(random.uniform(self.mindelay, self.maxdelay))

