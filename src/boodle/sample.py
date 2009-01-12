# Boodler: a programmable soundscape tool
# Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

"""sample: A module containing the Sample class; also the SampleLoader
classes, which know how to load data from various sound files (AIFF,
WAV, etc).

Public functions:

get() -- load a sample object, given a filename or File object
get_info() -- measure the expected running time and looping params of a sound
"""

import fileinput
import os
import os.path
import aifc
import wave
import sunau
import struct
import bisect

# Maps File objects, and also str/unicode pathnames, to Samples.
cache = {}

# We still support $BOODLER_SOUND_PATH, for old times' sake.
# But packaged modules should not rely on it.
sound_dirs = os.environ.get('BOODLER_SOUND_PATH', os.curdir)
sound_dirs = sound_dirs.split(':')

if struct.pack("h", 1) == "\000\001":
    big_endian = 1
else:
    big_endian = 0

class Sample:
    """Sample: represents a sound file, held in memory.

    This is really just a container for a native object (csamp), which
    is used by the cboodle native module. Samples may only be created
    by the SampleLoader classes in this module.
    """
    
    reloader = None

    def __init__(self, filename, csamp):
        self.filename = filename
        self.refcount = 0
        self.lastused = 0
        self.csamp = csamp

    def __repr__(self):
        return '<Sample at ' + str(self.filename) + '>'
        
    def queue_note(self, pitch, volume, pan, starttime, chan):
        if (cboodle.is_sample_error(self.csamp)):
            raise SampleError('sample is unplayable')
        if (not cboodle.is_sample_loaded(self.csamp)):
            if (not (self.reloader is None)):
                self.reloader.reload(self)
            if (not cboodle.is_sample_loaded(self.csamp)):
                raise SampleError('sample is unloaded')
        (panscx, panshx, panscy, panshy) = stereo.extend_tuple(pan)
        def closure(samp=self, chan=chan):
            samp.refcount -= 1
            chan.remnote()
        dur = cboodle.create_note(self.csamp, pitch, volume,
            panscx, panshx, panscy, panshy,
            starttime, chan, closure)
        chan.addnote()
        self.refcount += 1
        if (self.lastused < starttime + dur):
            self.lastused = starttime + dur
        return dur

    def queue_note_duration(self, pitch, volume, pan, starttime, duration, chan):
        if (cboodle.is_sample_error(self.csamp)):
            raise SampleError('sample is unplayable')
        if (not cboodle.is_sample_loaded(self.csamp)):
            if (not (self.reloader is None)):
                self.reloader.reload(self)
            if (not cboodle.is_sample_loaded(self.csamp)):
                raise SampleError('sample is unloaded')
        (panscx, panshx, panscy, panshy) = stereo.extend_tuple(pan)
        def closure(samp=self, chan=chan):
            samp.refcount -= 1
            chan.remnote()
        dur = cboodle.create_note_duration(self.csamp, pitch, volume,
            panscx, panshx, panscy, panshy,
            starttime, duration, chan, closure)
        chan.addnote()
        self.refcount += 1
        if (self.lastused < starttime + dur):
            self.lastused = starttime + dur
        return dur

    def get_info(self, pitch=1.0):
        if (cboodle.is_sample_error(self.csamp)):
            raise SampleError('sample is unplayable')
        res = cboodle.sample_info(self.csamp)
        ratio = float(res[0]) * float(pitch) * float(cboodle.framespersec())
        if (len(res) == 2):
            return (float(res[1]) / ratio, None)
        else:
            return (float(res[1]) / ratio, 
                (float(res[2]) / ratio, float(res[3]) / ratio))

class MixinSample(Sample):
    def __init__(self, filename, ranges, default, modname=None):
        self.ranges = ranges
        self.minvals = [ rn.min for rn in ranges ]
        self.default = default

        if (filename is None):
            filename = '<constructed>'
        self.filename = filename
        
        if (modname):
            self.__module__ = modname
        
        self.lastused = 0
        self.refcount = 0
        self.csamp = None

    def find(self, pitch):
        pos = bisect.bisect(self.minvals, pitch)
        pos -= 1
        
        while (pos >= 0):
            rn = self.ranges[pos]
            if (pitch <= rn.max):
                return rn
            pos -= 1
            
        if (not (self.default is None)):
            return self.default
            
        raise SampleError(str(pitch) + ' is outside mixin ranges')

    def queue_note(self, pitch, volume, pan, starttime, chan):
        rn = self.find(pitch)
        if (not (rn.pitch is None)):
            pitch *= rn.pitch
        if (not (rn.volume is None)):
            volume *= rn.volume
        samp = get(rn.sample)
        return samp.queue_note(pitch, volume, pan, starttime, chan)

    def queue_note_duration(self, pitch, volume, pan, starttime, duration, chan):
        rn = self.find(pitch)
        if (not (rn.pitch is None)):
            pitch *= rn.pitch
        if (not (rn.volume is None)):
            volume *= rn.volume
        samp = get(rn.sample)
        return samp.queue_note_duration(pitch, volume, pan, starttime, duration, chan)

    def get_info(self, pitch=1.0):
        rn = self.find(pitch)
        if (not (rn.pitch is None)):
            pitch *= rn.pitch
        samp = get(rn.sample)
        return samp.get_info(pitch)

def unload_unused(deathtime):
    for samp in list(cache.values()):
        if (samp.refcount == 0
            and (not (samp.csamp is None))
            and deathtime >= samp.lastused
            and cboodle.is_sample_loaded(samp.csamp)):
                cboodle.unload_sample(samp.csamp)

def adjust_timebase(trimoffset, maxage):
    for samp in cache.values():
        if (samp.lastused >= -maxage):
            samp.lastused = samp.lastused - trimoffset

def get(sname):
    """get(sample) -> Sample

    Load a sample object, given a filename or File object. (You can also
    pass a Sample object; it will be returned back to you.)

    (If the filename is relative, $BOODLER_SOUND_PATH is searched.)

    The module maintains a cache of sample objects, so if you load the
    same filename twice, the second get() call will be fast.

    This function is not useful, since agent.sched_note() and such methods
    call it for you -- they accept filenames as well as sample objects. 
    This function is available nevertheless.
    """

    # If the argument is a Sample in the first place, return it.
    if (isinstance(sname, Sample)):
        return sname

    # If we've seen it before, it's in the cache.
    samp = cache.get(sname)
    if (not (samp is None)):
        return samp

    suffix = None
        
    if (isinstance(sname, boopak.pinfo.MemFile)):
        filename = sname
        suffix = sname.suffix
    elif (isinstance(sname, boopak.pinfo.File)):
        filename = sname
        if (not os.access(sname.pathname, os.R_OK)):
            raise SampleError('file not readable: ' + sname.pathname)
        (dummy, suffix) = os.path.splitext(sname.pathname)
    elif (not (type(sname) in [str, unicode])):
        raise SampleError('not a File or filename')
    elif (os.path.isabs(sname)):
        filename = sname
        if (not os.access(filename, os.R_OK)):
            raise SampleError('file not readable: ' + filename)
        (dummy, suffix) = os.path.splitext(filename)
    else:
        for dir in sound_dirs:
            filename = os.path.join(dir, sname)
            if (os.access(filename, os.R_OK)):
                (dummy, suffix) = os.path.splitext(filename)
                break
        else:
            raise SampleError('file not readable: ' + sname)

    suffix = suffix.lower()
    
    loader = find_loader(suffix)
    samp = loader.load(filename, suffix)

    # Cache under the original key (may be File, str, or unicode)
    cache[sname] = samp
    return samp

def get_info(samp, pitch=1):
    """get_info(sample, pitch=1) -> tuple

    Measure the expected running time and looping parameters of a sound.
    The argument can be either a filename, or a sample object (as 
    returned by get()).

    The result is a 2-tuple. The first member is the duration of the
    sound (in seconds, if played with the given pitch -- by default,
    the sound's original pitch). The second member is None, if the
    sound has no looping parameters, or a 2-tuple (loopstart, loopend).

    The result of this function may not be precisely accurate, due
    to rounding annoyances. In particular, the duration may not be
    exactly equal to the value returned by agent.sched_note(), when
    the note is actually played.
    """
    
    samp = get(samp)
    return samp.get_info(pitch)


class MixIn:
    """MixIn: base class for statically declared mix-in samples.

    To use this, declare a construct:

    class your_sample_name(MixIn):
        ranges = [
            MixIn.range(...),
            MixIn.range(...),
            MixIn.range(...),
        ]
        default = MixIn.default(...)

    A range declaration looks like

        MixIn.range(maxval, sample)
    or
        MixIn.range(minval, maxval, sample)
    or
        MixIn.range(minval, maxval, sample, pitch=1.0, volume=1.0)

    If you don't give a minval, the maxval of the previous range is used.
    You may use the constants MixIn.MIN and MixIn.MAX to represent the
    limits of the range. The pitch and volume arguments are optional.

    A default declaration looks like

        MixIn.default(sample)
    or
        MixIn.default(sample, pitch=1.0, volume=1.0)

    The default declaration is option. (As are, again, the pitch and
    volume arguments.)

    When your declaration is complete, your_sample_name will magically
    be a MixinSample instance (not a class).
    """
    
    MIN = 0.0
    MAX = 1000000.0

    def default(samp, pitch=None, volume=None):
        if (samp is None):
            raise SampleError('default must have a sample')
        return MixIn.range(MixIn.MIN, MixIn.MAX, samp,
            pitch=pitch, volume=volume)
    default = staticmethod(default)

    class range:
        def __init__(self, arg1, arg2, arg3=None, pitch=None, volume=None):
            if (arg3 is None):
                (min, max, samp) = (None, arg1, arg2)
            else:
                (min, max, samp) = (arg1, arg2, arg3)
            if (samp is None):
                raise SampleError('range must have a sample')
            if (max is None):
                raise SampleError('range must have a maximum value')
                
            (self.min, self.max) = (min, max)
            self.sample = samp
            self.pitch = pitch
            self.volume = volume

        def __repr__(self):
            return '<range %s, %s>' % (self.min, self.max)

        def __cmp__(self, other):
            if (not (self.min is None or other.min is None)):
                res = cmp(self.min, other.min)
                if (res):
                    return res
            if (not (self.max is None or other.max is None)):
                res = cmp(self.max, other.max)
                if (res):
                    return res
            return 0

    def __class__(name, bases, dic):
        ranges = dic['ranges']
        default = dic.get('default', None)
        modname = dic['__module__']

        MixIn.sort_mixin_ranges(ranges)
        return MixinSample('<'+name+'>', ranges, default, modname)
    __class__ = staticmethod(__class__)

    def sort_mixin_ranges(ranges):
        ranges.sort()
        
        lastmin = 0.0
        for rn in ranges:
            if (rn.min is None):
                rn.min = lastmin
            if (rn.min > rn.max):
                raise SampleError('range\'s min must be less than its max')
            lastmin = rn.max
    sort_mixin_ranges = staticmethod(sort_mixin_ranges)
    
class SampleLoader:
    """SampleLoader: Base class for the facility to load a particular
    form of sound sample from a file.

    Subclasses of this are defined and instantiated later in the module.
    """
    
    suffixmap = {}

    def __init__(self):
        self.register_suffixes()

    def register_suffixes(self):
        for val in self.suffixlist:
            SampleLoader.suffixmap[val] = self

    def load(self, filename, suffix):
        csamp = cboodle.new_sample()
        try:
            self.raw_load(filename, csamp)
        except Exception, ex:
            cboodle.delete_sample(csamp)
            raise
        samp = Sample(filename, csamp)
        samp.reloader = self
        return samp

    def reload(self, samp):
        self.raw_load(samp.filename, samp.csamp)

def find_loader(suffix):
    """find_loader(suffix) -> SampleLoader

    Locate the SampleLoader instance which handles the given file
    suffix. (The suffix should be given as a dot followed by lower-case
    characters.)
    """
    
    clas = SampleLoader.suffixmap.get(suffix)
    if (clas is None):
        raise SampleError('unknown sound file extension \'' 
            + suffix + '\'')
    return clas

class AifcLoader(SampleLoader):
    suffixlist = ['.aifc', '.aiff', '.aif']
    
    def raw_load(self, filename, csamp):
        if (isinstance(filename, boopak.pinfo.File)):
            afl = filename.open(True)
        else:
            afl = open(filename, 'rb')
        try:
            fl = aifc.open(afl)
            numframes = fl.getnframes()
            dat = fl.readframes(numframes)
            numchannels = fl.getnchannels()
            samplebits = fl.getsampwidth()*8
            framerate = fl.getframerate()
            markers = fl.getmarkers()
            fl.close()
        finally:
            afl.close()
            
        loopstart = -1
        loopend = -1
        if (not (markers is None)):
            for (mark, pos, name) in markers:
                if (mark == 1):
                    loopstart = pos
                elif (mark == 2):
                    loopend = pos
        if (loopstart < 0 or loopend < 0):
            loopstart = -1
            loopend = -1
        params = (framerate, numframes, dat, loopstart, loopend, numchannels, samplebits, 1, 1)
        res = cboodle.load_sample(csamp, params)
        if (not res):
            raise SampleError('unable to load aiff data')

aifc_loader = AifcLoader()

class WavLoader(SampleLoader):
    suffixlist = ['.wav']
    
    def raw_load(self, filename, csamp):
        if (isinstance(filename, boopak.pinfo.File)):
            afl = filename.open(True)
        else:
            afl = open(filename, 'rb')
        try:
            fl = wave.open(afl)
            numframes = fl.getnframes()
            dat = fl.readframes(numframes)
            numchannels = fl.getnchannels()
            samplebits = fl.getsampwidth()*8
            framerate = fl.getframerate()
            fl.close()
        finally:
            afl.close()
        
        params = (framerate, numframes, dat, -1, -1, numchannels, samplebits, 1, big_endian)
        res = cboodle.load_sample(csamp, params)
        if (not res):
            raise SampleError('unable to load wav data')

wav_loader = WavLoader()

class SunAuLoader(SampleLoader):
    suffixlist = ['.au']
    
    def raw_load(self, filename, csamp):
        if (isinstance(filename, boopak.pinfo.File)):
            afl = filename.open(True)
        else:
            afl = open(filename, 'rb')
        try:
            fl = sunau.open(afl, 'r')
            numframes = fl.getnframes()
            dat = fl.readframes(numframes)
            numchannels = fl.getnchannels()
            samplebits = fl.getsampwidth()*8
            framerate = fl.getframerate()
            fl.close()
        finally:
            afl.close()
            
        params = (framerate, numframes, dat, -1, -1, numchannels, samplebits, 1, 1)
        res = cboodle.load_sample(csamp, params)
        if (not res):
            raise SampleError('unable to load au data')

sunau_loader = SunAuLoader()

class MixinLoader(SampleLoader):
    suffixlist = ['.mixin']

    def load(self, filename, suffix):
        dirname = None
        modname = None
        
        if (isinstance(filename, boopak.pinfo.File)):
            afl = filename.open(True)
            modname = filename.package.encoded_name
        else:
            dirname = os.path.dirname(filename)
            afl = open(filename, 'rb')
        linelist = afl.readlines()
        afl.close()
        
        ranges = []
        defval = None

        for line in linelist:
            tok = line.split()
            if len(tok) == 0:
                continue
            if (tok[0].startswith('#')):
                continue
            if (tok[0] == 'range'):
                if (len(tok) < 4):
                    raise SampleError('range and filename required after range')
                tup = self.parseparam(filename, dirname, tok[3:])
                if (tok[1] == '-'):
                    startval = None
                else:
                    startval = float(tok[1])
                if (tok[2] == '-'):
                    endval = MixIn.MAX
                else:
                    endval = float(tok[2])
                rn = MixIn.range(startval, endval, tup[0], pitch=tup[1], volume=tup[2])
                ranges.append(rn)
            elif (tok[0] == 'else'):
                if (len(tok) < 2):
                    raise SampleError('filename required after else')
                tup = self.parseparam(filename, dirname, tok[1:])
                rn = MixIn.default(tup[0], pitch=tup[1], volume=tup[2])
                defval = rn
            else:
                raise SampleError('unknown statement in mixin: ' + tok[0])

        MixIn.sort_mixin_ranges(ranges)
        return MixinSample(filename, ranges, defval, modname)

    def parseparam(self, filename, dirname, tok):
        if (dirname is None):
            pkg = filename.package
            samp = pkg.loader.load_item_by_name(tok[0], package=pkg)
        else:
            newname = os.path.join(dirname, tok[0])
            newname = os.path.normpath(newname)
            samp = get(newname)
            
        pitch = None
        volume = None
        
        if (len(tok) > 2):
            if (tok[2] != '-'):
                volume = float(tok[2])
        if (len(tok) > 1):
            if (tok[1] != '-'):
                pitch = float(tok[1])

        return (samp, pitch, volume)

    def reload(self, samp):
        pass

mixin_loader = MixinLoader()


# Late imports.

import boodle
from boodle import stereo
# cboodle may be updated later, by a set_driver() call.
cboodle = boodle.cboodle

import boopak

class SampleError(boodle.BoodlerError):
    """SampleError: Represents problems encountered while finding or
    loading sound files.
    """
    pass
