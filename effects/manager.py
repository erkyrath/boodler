from boodle.agent import *
import random
import types

class Simultaneous(Agent):
	name = 'start several agents simultaneously'
	def __init__(self, *arglist):
		Agent.__init__(self)
		self.agentlist = []
		for arg in arglist:
			if (type(arg) == types.StringType):
				clas = load_class_by_name(arg)
				arg = clas()
			self.agentlist.append(arg)
	def run(self):
		for ag in self.agentlist:
			chan = self.new_channel()
			self.sched_agent(ag, 0, chan)

class SimultaneousVolume(Agent):
	name = 'start several agents simultaneously at different volumes'
	def __init__(self, *arglist):
		Agent.__init__(self)
		self.agentlist = []
		for pos in range(0, len(arglist), 2):
			arg = arglist[pos]
			vol = float(arglist[pos+1])
			if (type(arg) == types.StringType):
				clas = load_class_by_name(arg)
				arg = clas()
			self.agentlist.append( (arg, vol) )
	def run(self):
		for (ag, vol) in self.agentlist:
			chan = self.new_channel(vol)
			self.sched_agent(ag, 0, chan)

class Sequential(Agent):
	name = 'cycle among several agents'
	def __init__(self, mindelay, maxdelay, *arglist):
		Agent.__init__(self)
		self.mindelay = float(mindelay)
		self.maxdelay = float(maxdelay)
		self.fadetime = 2.0
		self.prevchannel = None
		self.classlist = []
		self.pos = 0
		for arg in arglist:
			if (type(arg) == types.StringType):
				arg = load_class_by_name(arg)
			self.classlist.append(arg)
	def run(self):
		if (self.prevchannel != None and self.prevchannel.active):
			self.sched_agent(FadeOutAgent(self.fadetime), 0, self.prevchannel)
		self.prevchannel = self.new_channel(0)
		clas = self.classlist[self.pos]
		self.pos = (self.pos+1) % len(self.classlist)
		ag = clas()
		self.sched_agent(ag, 0, self.prevchannel)
		self.prevchannel.set_volume(1, self.fadetime)
		delay = random.uniform(self.mindelay, self.maxdelay)
		self.resched(delay)

# VolumeModulate and VolumeModulateChannel from ideas by Peter Williams

class VolumeModulate(Agent):
	name = 'adjusts an agent\'s volume randomly'
	def __init__(self, ag, vol=0.8, delta=0.2, minfade=7, maxfade=20, mindelay=30, maxdelay=70):
		Agent.__init__(self)
		if (type(ag) == types.StringType):
			clas = load_class_by_name(ag)
			ag = clas()
		self.agent = ag
		self.vol = float(vol)
		self.delta = float(delta)
		self.minfade = float(minfade)
		self.maxfade = float(maxfade)
		self.mindelay = float(mindelay)
		self.maxdelay = float(maxdelay)
	def run(self):
		chan = self.new_channel(self.vol)
		self.sched_agent(self.agent, 0, chan)
		ag = VolumeModulateChannel(self.vol, self.delta, self.minfade, self.maxfade, self.mindelay, self.maxdelay)
		self.sched_agent(ag, 0, chan)

class VolumeModulateChannel(Agent):
	name = 'adjusts the channel\'s volume slightly'
	def __init__(self, vol=0.8, delta=0.2, minfade=7, maxfade=20, mindelay=30, maxdelay=70):
		Agent.__init__(self)
		self.vol = float(vol)
		self.delta = float(delta)
		self.minfade = float(minfade)
		self.maxfade = float(maxfade)
		self.mindelay = float(mindelay)
		self.maxdelay = float(maxdelay)
	def run(self):
		targ = self.vol + random.uniform(-self.delta, self.delta)
		time = random.uniform(self.minfade, self.maxfade)
		self.channel.set_volume(targ, time)
		delay = random.uniform(self.mindelay, self.maxdelay)
		self.resched(delay)
  
