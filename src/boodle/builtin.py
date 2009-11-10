# Boodler: a programmable soundscape tool
# Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

"""builtin: A module containing useful utility Agent classes.

These Agents are too important to be distributed in an optional package;
they need to be available always.

NullAgent -- does nothing
StopAgent -- causes a channel to stop playing
SetVolumeAgent -- causes a channel to change to a given volume
SetPanAgent -- causes a channel to change to a given pan position
FadeOutAgent -- causes a channel to fade down to zero volume over an interval
FadeInOutAgent -- creates a channel that fades up, holds, and fades out
TestSoundAgent -- plays a little test melody
"""

import cStringIO
from boodle import agent

# Declare the imports list, so that "from boodle.builtin import *"
# is practical.
__all__ = [
    'NullAgent', 'StopAgent',
    'SetVolumeAgent', 'SetPanAgent', 
    'FadeOutAgent', 'FadeInOutAgent',
    'TestSoundAgent'
]

### Add UnlistenAgent? SendEventAgent?
### Give these get_argument_list() methods? (Would allow command-line use...)

class NullAgent(agent.Agent):
    """NullAgent:

    This agent does nothing. 
    """
    
    def run(self):
        pass
    def get_title(self):
        return 'Null agent'

class StopAgent(agent.Agent):
    """StopAgent:

    This agent causes a channel to stop playing. (See Channel.stop.)
    All notes and agents in the channel (and subchannels) will be
    discarded.
    """

    def run(self):
        self.channel.stop()
    def get_title(self):
        return 'Stop channel'

class SetVolumeAgent(agent.Agent):
    """SetVolumeAgent:

    This agent causes a channel to change to a given volume. (See
    Channel.set_volume.)
    """

    def __init__(self, newvol, duration=0.005):
        agent.Agent.__init__(self)
        self.newvol = float(newvol)
        self.duration = float(duration)
    def run(self):
        self.channel.set_volume(self.newvol, self.duration)
    def get_title(self):
        return 'Set channel volume'
        
class SetPanAgent(agent.Agent):
    """SetPanAgent:

    This agent causes a channel to change to a given pan position. (See
    Channel.set_pan.)
    """

    def __init__(self, newpan, duration=0.5):
        agent.Agent.__init__(self)
        self.newpan = newpan
        self.duration = float(duration)
    def run(self):
        self.channel.set_pan(self.newpan, self.duration)
    def get_title(self):
        return 'Set channel pan'
        
class FadeOutAgent(agent.Agent):
    """FadeOutAgent(interval):

    This agent causes a channel to fade down to zero volume over a
    given interval, and then stop.
    """

    def __init__(self, duration=0.005):
        agent.Agent.__init__(self)
        self.duration = float(duration)
    def run(self):
        self.channel.set_volume(0, self.duration)
        self.sched_agent(StopAgent(), self.duration)
    def get_title(self):
        return 'Fade out and stop channel'

class FadeInOutAgent(agent.Agent):
    """FadeInOutAgent(agent, liveinterval, fadeinterval, fadeoutinterval=fadeinterval):

    This agent creates a channel with an agent, and causes that channel
    to fade up from zero volume, remain at full volume, and then fade out
    and stop.

    The fadeinterval is the time the channel takes to fade in or out.
    The liveinterval is the duration of maximum volume (from the end
    of fade-in to the beginning of fade-out).

    If two intervals are given, the first is the fade-in time, and the
    second is the fade-out time.
    """

    def __init__(self, agentinst, liveinterval=10.0, fadeinterval=1.0, fadeoutinterval=None):
        agent.Agent.__init__(self)
        self.agentinst = agentinst
        self.fadeininterval = float(fadeinterval)
        self.liveinterval = float(liveinterval)
        if (fadeoutinterval is None):
            self.fadeoutinterval = self.fadeininterval
        else:
            self.fadeoutinterval = float(fadeoutinterval)
    def run(self):
        chan = self.new_channel(0)
        self.sched_agent(self.agentinst, 0, chan)
        chan.set_volume(1, self.fadeininterval)
        ag = FadeOutAgent(self.fadeoutinterval)
        self.sched_agent(ag, self.liveinterval+self.fadeininterval, chan)
    def get_title(self):
        return 'Fade in, fade out, stop channel'

class TestSoundAgent(agent.Agent):
    """TestSoundAgent:

    Plays a little test melody. This does some under-the-cover contortions
    to create a sound sample without loading any Boodler modules from
    the external module collection.
    """
    sound = None
    
    def makesound(fl):
        """makesound(fl) -> None
        Generate AIFF sound data for a short musical note, and write the
        AIFF to the given file.
        """
        import aifc, math
        afl = aifc.open(fl, 'wb')
        afl.setnchannels(2)
        afl.setsampwidth(2)
        afl.setframerate(22050)
        nframes = 5000
        ratio = (0.5 * math.pi / nframes)
        for ix in range(nframes):
            amp = 0.5 * (math.sin(ix * 0.10) + math.sin(ix * 0.166666))
            amp *= math.cos(ix * ratio)
            if (ix < 10):
                amp *= (ix * 0.1)
            amp = int(amp * 0x4000)
            dat = chr((amp >> 8) & 0xFF) + chr(amp & 0xFF)
            amp = amp // 10
            dat += chr((amp >> 8) & 0xFF) + chr(amp & 0xFF)
            afl.writeframes(dat)
        afl.close()
    makesound = staticmethod(makesound)
    
    def getsound():
        """getsound() -> File
        Create a sound sample object for a short musical note. The AIFF
        sound data is kept in memory, not stored in an actual file anywhere.
        This caches the File object; if you call it more than once, you'll
        get the same File.
        """
        if (not TestSoundAgent.sound):
            fl = SafeStringIO()
            TestSoundAgent.makesound(fl)
            dat = fl.getvalue()
            fl.realclose()
            mfile = pinfo.MemFile(dat, '.aiff', 'TestSound')
            TestSoundAgent.sound = mfile
        return TestSoundAgent.sound
    getsound = staticmethod(getsound)
    
    def run(self):
        from boodle import music
        pitches = [-5, -6, -3, -4, -1, -2, 1, 0,
            (-6, -1), -3, -5, (0, 3), (-2, 1) ]
        snd = TestSoundAgent.getsound()
        pos = 0.0
        center = stereo.scale(0)
        leftright = 1
        for val in pitches:
            if (type(val) == tuple):
                for pitch in val:
                    self.sched_note_pan(snd, pitch=music.get_pitch(pitch), pan=center, delay=pos)
            else:
                self.sched_note_pan(snd, pitch=music.get_pitch(val), pan=stereo.scale(leftright), delay=pos)
                leftright = -leftright
            pos += 0.145
    def get_title(self):
        return 'Boodler test sound'

class SafeStringIO:
    """SafeStringIO: a silly wrapper for cStringIO.

    This class exists to work around a feature, or from my point of view
    a bug, in Python 2.6: the aifc module now closes the underlying file
    when you close an aifc object you were writing. Since I want to write
    an AIFF to a cStringIO, which evaporates when closed, this makes my
    life unduly difficult.

    To work around this, we create a wrapper that behaves exactly like
    cStringIO except that the close() method does nothing. Its functionality
    is moved to realclose().
    """
    def __init__(self):
        self.fl = cStringIO.StringIO()
        self.read = self.fl.read
        self.write = self.fl.write
        self.seek = self.fl.seek
        self.tell = self.fl.tell
        self.flush = self.fl.flush
        self.getvalue = self.fl.getvalue
    def close(self):
        pass
    def realclose(self):
        self.fl.close()
        self.fl = None

# Late imports.

from boodle import stereo
from boopak import pinfo
