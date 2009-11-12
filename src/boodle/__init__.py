# Boodler: a programmable soundscape tool
# Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

__all__ = ['agent', 'builtin', 'generator', 'listen', 'sample', 'stereo', 'music']

driver_list = [
    'file', 'stdout',
    'oss', 'esd', 'alsa', 'pulse', 'jackb',
    'osxaq', 'macosx',
    'vorbis', 'shout', 'lame',
]

driver_map = {
    'file': 'write file containing raw sample output',
    'stdout': 'write raw sample output to stdout',
    'oss': 'Open Sound System',
    'esd': 'Enlightened Sound Daemon',
    'alsa': 'Advanced Linux Sound Architecture',
    'pulse': 'PulseAudio',
    'jackb': 'JACK via Bio2Jack',
    'osxaq': 'MacOSX AudioQueue',
    'macosx': 'MacOSX CoreAudio',
    'vorbis': 'write Ogg Vorbis file',
    'shout': 'Shoutcast or Icecast source',
    'lame': 'write MP3 file with LAME encoder',
}

class DummyDriver:
    """A dummy driver class.

    This class exists only so that boodle.cboodle can have a default
    value. The behavior of the dummy is to throw an exception when
    any method is called.
    """
    def __repr__(self):
        return '<boodle.DummyDriver>'
    def __str__(self):
        return '<boodle.DummyDriver>'
    def __getattr__(self, key):
        raise Exception('No Boodler output driver has been selected.')

# Create the default dummy driver object.
cboodle = DummyDriver()

def set_driver(key):
    """set_driver(key) -> module

    Select a Boodler driver. The key must be one of the installed driver
    keys ('file', etc). This returns the selected driver. It also
    sets boodle.cboodle, and the cboodle property in the other Boodler
    classes that make use of it.

    If the driver is not available, this raises ImportError.
    """
    global cboodle
    
    modname = 'cboodle_'+key
    selfmod = __import__('boodle.'+modname)
    driver = getattr(selfmod, modname)

    import boodle.agent, boodle.generator, boodle.sample
    cboodle = driver
    agent.cboodle = driver
    generator.cboodle = driver
    sample.cboodle = driver

    return driver

def list_drivers():
    """list_drivers() -> list of (str, str)

    List the Boodler drivers which are installed and usable.
    Returns a list of tuples (key, fullname). In each pair, key is a 
    driver key (which can be passed to set_driver()), and fullname
    is a human-readable description of the driver.
    """
    
    ls = []

    for key in driver_list:
        modname = 'cboodle_'+key
        try:
            __import__('boodle.'+modname)
            ls.append(key)
        except Exception:
            pass

    return [ (key, driver_map.get(key, 'unnamed driver')) for key in ls ]


# A few utility definitions, which will be used by several of the
# boodle.* modules

class BoodlerError(Exception):
    """BoodlerError: A parent class for errors encountered during
    Boodler operation. These include violations of internal sanity 
    checks, and sanity checks on imported package code.

    When a BoodlerError is displayed, the last (lowest) stack frame
    can be trimmed out; that information is implicit in the error type
    and message.
    """
    pass

class StopGeneration(Exception):
    """StopGeneration: Raised when the top-level soundscape reaches its
    end -- no more agents or sounds to be run.
    """
    pass

from re import compile as _re_compile

# Regular expression for valid event/property names: one or more elements,
# separated by periods. Each element must contain only letters, digits,
# and underscores. An element may not start with a digit.
_prop_name_regexp = _re_compile('\\A[a-zA-Z_][a-zA-Z_0-9]*(\.([a-zA-Z_][a-zA-Z_0-9]*))*\\Z')

# A cache of valid event/property names. We keep this so that we don't
# have to regexp them every time.
_valid_prop_names = {}

def check_prop_name(val):
    """check_prop_name(val) -> str

    Ensure that the value is a valid event or property name. If it isn't, 
    raise BoodlerError. If it is, return a str version of it (in case it 
    was a unicode object).
    """
    
    res = _valid_prop_names.get(val)
    if (res):
        return res
    res = _prop_name_regexp.match(val)
    if (not res):
        raise BoodlerError('invalid prop/event name: ' + val)
    res = str(val)
    _valid_prop_names[res] = res
    return res
