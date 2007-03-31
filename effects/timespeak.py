from boodle.agent import *
from boodle import sample
import os.path
import types
import time

SAY_TIME_IS  = 1
SAY_SECONDS  = 2
SAY_MERIDIAN = 4
DEFAULT_OPTS = (SAY_TIME_IS | SAY_SECONDS | SAY_MERIDIAN)

#default_voice = ['voice/timespeak/male-harsh']
default_voice = ['voice/timespeak/zarf']

units = [
	'oh.aiff', '1.aiff', '2.aiff', '3.aiff', '4.aiff', 
	'5.aiff', '6.aiff', '7.aiff', '8.aiff', '9.aiff',
	'10.aiff', '11.aiff', '12.aiff', '13.aiff', '14.aiff', 
	'15.aiff', '16.aiff', '17.aiff', '18.aiff', '19.aiff', '20.aiff' 
]

tens = [ 
	'oh.aiff', '10.aiff', '20.aiff', 
	'30.aiff', '40.aiff', '50.aiff', 'oh.aiff' 
]

voices = {}

class Voice:
	def __init__(self, name):
		self.name = name
		self.cache = {}
	def __repr__(self):
		return '<timespeak.Voice: ' + str(self.cache) + '>'
	def join(self, base, var):
		key = (base, var)
		samp = self.cache.get(key)
		if (samp != None):
			return samp
		if (var != None):
			try:
				sampname = os.path.join(self.name, var+'-'+base)
				samp = sample.get(sampname)
			except sample.SampleError:
				samp = None
		if (samp == None):
			try:
				sampname = os.path.join(self.name, base)
				samp = sample.get(sampname)
			except sample.SampleError:
				samp = sample.get('pure/null.aiff')
		self.cache[key] = samp
		return samp

def set_voice(dir):
	default_voice[0] = dir

def get_current_voice(name=None):
	if (name == None):
		name = default_voice[0]
	voice = voices.get(name)
	if (voice == None):
		voice = Voice(name)
		voices[name] = voice
	return voice

class Time(Agent):
	name = 'speak a given time'
	def __init__(self, timeval, opts=DEFAULT_OPTS):
		Agent.__init__(self)
		if (type(opts) == types.StringType):
			opts = int(opts)
		if (type(opts) == types.TupleType):
			val = 0
			for opt in opts:
				val = val | opt
			opts = val
		if (type(timeval) != types.TupleType):
			timeval = time.localtime(timeval)
		self.timeval = timeval
		self.opts = opts
		self.voice = get_current_voice()
	def append(self, base, var, pos):
		samp = self.voice.join(base, var)
		pos = pos + self.sched_note(samp, 1, 1, pos)
		return pos
	def run(self):
		pos = 0.0
		if (self.opts & SAY_TIME_IS):
			pos = self.append('the_time_is.aiff', None, pos)
		hour = (self.timeval[3] % 12)
		halfday = (self.timeval[3] >= 12)
		if (hour == 0):
			hour = 12
		pos = self.append(units[hour], None, pos)
		min = self.timeval[4]
		if (min == 0):
			pos = self.append('oclock.aiff', None, pos)
		elif (min < 10):
			pos = self.append('oh.aiff', None, pos)
			pos = pos + 0.05
			pos = self.append(units[min], None, pos)
		elif (min <= 20):
			pos = self.append(units[min], None, pos)
		else:
			pos = self.append(tens[min / 10], None, pos)
			ix = min % 10
			if (ix != 0):
				pos = self.append(units[ix], None, pos)
		if (self.opts & SAY_MERIDIAN):
			if (halfday):
				pos = self.append('pm.aiff', None, pos)
			else:
				pos = self.append('am.aiff', None, pos)
		if (self.opts & SAY_SECONDS):
			sec = self.timeval[5]
			if (sec == 0):
				pos = self.append('exactly.aiff', None, pos)
			else:
				pos = self.append('and.aiff', None, pos)
				if (sec < 20):
					pos = self.append(units[sec], None, pos)
				else:
					pos = self.append(tens[sec / 10], None, pos)
					ix = sec % 10
					if (ix != 0):
						pos = self.append(units[ix], None, pos)
				if (sec == 1):
					pos = self.append('second.aiff', None, pos)
				else:
					pos = self.append('seconds.aiff', None, pos)

class Now(Agent):
	name = 'speak the current time'
	def __init__(self, opts=DEFAULT_OPTS):
		Agent.__init__(self)
		self.opts = opts
	def run(self):
		ag = Time(time.time(), self.opts)
		self.sched_agent(ag)

class TemporalFugue(Agent):
	name = 'chant the current time rhythmically'
	def run(self):
		ag = Time(time.time(), SAY_SECONDS)
		self.sched_agent(ag)
		self.resched(1)

class Periodic(Agent):
	name = 'speak time periodically'
	def __init__(self, period=15):
		Agent.__init__(self)
		period = int(period)
		if (60 % period != 0):
			raise ValueError('period must be a divisor of 60')
		self.period = period
		self.firsttime = 1
	def run(self):
		now = time.time()
		timeval = time.localtime(now)
		if (self.firsttime == 1):
			self.firsttime = 0
		else:
			(hour, min, sec) = timeval[3:6]
			if (sec < 30):
				sec = 0
			else:
				sec = 0
				min = min+1
				if (min >= 60):
					min = 0
					hour = hour+1
					if (hour >= 24):
						hour = 0
			neartimeval = timeval[0:3] + (hour, min, sec) + timeval[6:]
			#near = time.mktime(neartimeval)
			ag = Time(neartimeval, SAY_TIME_IS | SAY_MERIDIAN)
			self.sched_agent(ag)
		min = timeval[4]
		min = min - (min % self.period)
		prevtimeval = timeval[0:4] + (min, 0) + timeval[6:]
		prev = time.mktime(prevtimeval)
		delay = self.period*60.0 - (now-prev)
		if (delay < 1.0):
			delay = delay + self.period*60.0
		self.resched(delay)
