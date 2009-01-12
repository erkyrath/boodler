# Boodler: a programmable soundscape tool
# Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

"""version: A module which manages version numbers and version number
requirements.

Classes:

VersionNumber -- represents a structured version number
VersionSpec -- represents a requirement for certain version numbers
VersionFormatError -- ValueError representing a bad VersionNumber/Spec

Internal class:

VersionPattern -- represents one PATTERN element of a VersionSpec
"""

import re

class VersionFormatError(ValueError):
    """VersionFormatError: A ValueError produced when trying to create
    an illegal VersionNumber or VersionSpec.
    """
    pass

# Match one or more digits.
all_digits_regexp = re.compile('\\A[0-9]+\\Z')
# Match the characters that can be in a release value element (between
# periods).
release_element_regexp = re.compile('\\A[a-zA-Z0-9_+-]*\\Z')

class VersionNumber:
    """VersionNumber: represents a structured version number.

    A VersionNumber has the form "MAJOR", "MAJOR.MINOR", or
    "MAJOR.MINOR.RELEASE". MAJOR must be a positive integer (not zero).
    MINOR must be a non-negative integer (zero is allowed). RELEASE,
    if present, must be a string of letters, digits, plus, minus,
    underscore, dot.

    The version numbers "3" and "3.0" are considered equal (the
    minor value is assumed to be zero if not given). However, this
    is not true of the release value; "3.0" and "3.0.0" are considered
    different. (This is a quirk of the version-matching algorithm, which
    requires a major and minor value but ignores the release value.)

    VersionNumbers are immutable, and may be used as dict keys. You can
    compare them with ==, !=, <, >, and so on.

    Constructors:
    
    VersionNumber() -- default version "1.0"
    VersionNumber(int) -- construct "X.0"
    VersionNumber(int, int) -- construct "X.Y"
    VersionNumber(int, int, val, val, ...) -- construct "X.Y.val.val..."
        (the release values may be int or str)
    VersionNumber(str) -- parse a string into a VersionNumber

    Publicly readable fields:

    major -- the major value (int)
    minor -- the minor value (int)
    release -- the release string (may be None)

    Public methods:

    match() -- compare to a VersionSpec
    
    """
    
    def __init__(self, *args):
        self.major = 1
        self.minor = 0
        self.release = None

        self.tuple = None
        self.string = None

        if (len(args) == 0):
            self.init_num(1)
            return
        if (len(args) == 1 and type(args[0]) in [str, unicode]):
            self.init_str(args[0])
            return
        if (len(args) == 1 and type(args[0]) in [int, long]):
            self.init_num(args[0])
            return
        if (len(args) > 1 and type(args[0]) in [int, long]
            and type(args[1]) in [int, long]):
            self.init_num(args[0], args[1], args[2:])
            return
        raise VersionFormatError('VersionNumber requires a string, int, or (int, int, ...)')

    def init_str(self, arg):
        """init_str(arg)

        Utility function for constructor. (Do not call.)
        """
        
        if (not arg):
            self.init_num(1)
            return

        ls = arg.split('.')

        val = ls.pop(0)
        res = all_digits_regexp.match(val)
        if (not res):
            raise VersionFormatError('VersionNumber major number must be a positive number')
        major = int(val)

        minor = None
        if (ls):
            val = ls.pop(0)
            res = all_digits_regexp.match(val)
            if (not res):
                raise VersionFormatError('VersionNumber minor number must be a non-negative number')
            minor = int(val)

        self.init_num(major, minor, ls)

    def init_num(self, major, minor=None, release=()):
        """init_num(major, minor=None, release=())

        Utility function for constructor. (Do not call.)
        """
        
        if (major < 1):
            raise VersionFormatError('VersionNumber major number must be positive')
        self.major = major

        if (minor is None):
            self.minor = 0
            release = ()
        else:
            self.minor = minor
            if (minor < 0):
                raise VersionFormatError('VersionNumber minor number must be non-negative')

        self.tuple = (self.major, self.minor)
        self.sorttuple = self.tuple

        self.string = str(self.major) + '.' + str(self.minor)

        if (release):
            for val in release:
                if (val is None):
                    val = ''
                if (type(val) in [str, unicode]):
                    res = release_element_regexp.match(val)
                    if (not res):
                        raise VersionFormatError('VersionNumber release value is invalid')
                    val = str(val)
                equiv = val
                if (type(val) in [str, unicode]):
                    res = all_digits_regexp.match(val)
                    if (res):
                        equiv = int(val)
                self.tuple = self.tuple + (val,)
                self.sorttuple = self.sorttuple + (equiv,)
                self.string = self.string + '.' + str(val)

            ls = [ str(val) for val in self.tuple[2:] ]
            self.release = '.'.join(ls)

        if (len(self.tuple) == 3 and self.tuple[2] == ''):
            raise VersionFormatError('VersionNumber release value may not be empty')

    def __str__(self):
        return self.string

    def __repr__(self):
        return ('<VersionNumber \'' + str(self.tuple) + '\'>')

    def __cmp__(self, vers):
        if (type(vers) in [str, unicode, int, long]):
            vers = VersionNumber(vers)
        if (isinstance(vers, VersionSpec)):
            raise TypeError('use match() to compare VersionNumber to VersionSpec')
        res = cmp(self.sorttuple, vers.sorttuple)
        if (res):
            return res
        res = cmp(self.tuple, vers.tuple)
        return res

    def __eq__(self, vers):
        if (vers is None):
            return False
        if (type(vers) in [str, unicode, int, long]):
            vers = VersionNumber(vers)
        if (isinstance(vers, VersionSpec)):
            return False
        return (self.tuple == vers.tuple)

    def __ne__(self, vers):
        if (vers is None):
            return True
        if (type(vers) in [str, unicode, int, long]):
            vers = VersionNumber(vers)
        if (isinstance(vers, VersionSpec)):
            return True
        return (self.tuple != vers.tuple)

    def __hash__(self):
        return hash(self.tuple)

    def match(self, spec):
        """match(spec) -> bool

        Compare the version number to a VersionSpec (or to a string which
        defines a VersionSpec). Return True if the version number satisfies
        the spec.
        """
        
        if (type(spec) in [str, unicode]):
            spec = VersionSpec(spec)
        if (isinstance(spec, VersionSpec)):
            return spec.match(self)
        raise TypeError('VersionNumber must be matched with VersionSpec')

class VersionSpec:
    """VersionSpec: represents a requirement for certain version numbers.

    A VersionSpec looks like one or more PATTERNS, separated by commas.
    A PATTERN looks like one of: "VERSION", "VERSION.", "VERSION-",
    "-VERSION", "VERSION-VERSION".
    A VERSION is "MAJOR" or "MAJOR.MINOR".

    (Here a complex, but legal, VersionSpec: "-2.3,5,7.3.,9.9-10.1,13.5-")

    A VersionSpec matches a version number if any of its PATTERNs match.
    PATTERNs match as follows:

        "X.Y" -- major version must be X, minor version must be Y or higher
        "X.Y." -- major version must be X, minor version must be Y
        "X.Y-" -- major version is X, minor version is Y or higher *or*
            major version is higher than X
        "-Z.W" -- major version is Z, minor version is W is lower *or*
            major version is lower than Z
        "X.Y-Z.W" -- both of the above

        In all cases, the release value of the version number is ignored.

    VersionSpecs are immutable, and may be used as dict keys. However,
    they compare naively; they will only test as equal if they are
    visually identical. The specs "1-3,3-5" and "1-5" are logically
    equivalent, but they will compare unequal.

    VersionSpecs cannot be compared with <, >, <=, >=.
        
    Constructors:

    VersionSpec() -- default spec "1.0-"; this matches anything
    VersionSpec(int) -- construct "X.0"
    VersionSpec(int, int) -- construct "X.Y"
    VersionSpec(str) -- parse a string into a VersionSpec

    Note that when parsing a string, extraneous characters are firmly
    rejected. Do not put spaces in your comma-separated list.
    
    Public methods:

    match() -- compare to a VersionNumber
    
    """
    
    def __init__(self, *args):
        self.patterns = None
        if (len(args) == 0):
            self.patterns = ( VersionPattern( (1,0), None ), )
            return
        if (len(args) == 1 and type(args[0]) in [int, long]):
            self.init_num(args[0], None)
            return
        if (len(args) == 2 and type(args[0]) in [int, long]
            and type(args[1]) in [int, long]):
            self.init_num(args[0], args[1])
            return
        if (len(args) == 1 and type(args[0]) in [str, unicode]):
            self.init_str(args[0])
            return
        raise VersionFormatError('VersionSpec requires a string, int, or (int, int)')

    def init_num(self, major, minor=None):
        """init_num(major, minor=None)

        Utility function for constructor. (Do not call.)
        """
        
        if (minor is None):
            minor = 0
        self.patterns = ( VersionPattern( (major, minor) ), )

    def init_str(self, arg):
        """init_str(arg)

        Utility function for constructor. (Do not call.)
        """
        
        if (not arg):
            self.patterns = ( VersionPattern( (1,0), None ), )
            return
        ls = [ VersionPattern(val) for val in arg.split(',') ]
        self.patterns = tuple(ls)

    def __str__(self):
        ls = [ str(pat) for pat in self.patterns ]
        return ','.join(ls)
        
    def __repr__(self):
        ls = [ (pat.typenames.get(pat.type,'???') + ':'
                + str(pat.startpair) + '-' + str(pat.endpair))
            for pat in self.patterns ]
        return '<VersionSpec ' + ', '.join(ls) + '>'

    def __eq__(self, vers):
        if (isinstance(vers, VersionNumber)):
            return False
        return (self.patterns == vers.patterns)
    
    def __ne__(self, vers):
        if (isinstance(vers, VersionNumber)):
            return True
        return (self.patterns != vers.patterns)
    
    def __hash__(self):
        return hash(self.patterns)

    def match(self, vnum):
        """match(vnum) -> bool

        Compare the version spec to a VersionNumber (or to a string or
        int which defines a VersionNumber). Return True if the version
        number satisfies the spec.
        """
        
        if (type(vnum) in [str, unicode, int, long]):
            vnum = VersionNumber(vnum)
        if (not isinstance(vnum, VersionNumber)):
            raise TypeError('VersionSpec must be matched with VersionNumber')

        major = vnum.major
        minor = vnum.minor
        for pat in self.patterns:
            if (pat.match(major, minor)):
                return True
        return False

class VersionPattern:
    """VersionPattern: represents one PATTERN element of a VersionSpec.

    A VersionPattern looks like one of: "VERSION", "VERSION.", "VERSION-",
    "-VERSION", "VERSION-VERSION".
    A VERSION is "MAJOR" or "MAJOR.MINOR".

    (This class is used internally by VersionSpec, and should be ignored
    by outside callers.)

    Constructors:

    VersionPattern((int,int)) -- construct "X.Y"
    VersionPattern((int,int), (int,int)) -- construct "X.Y-Z.W"
    VersionPattern((int,int), None) -- construct "X.Y-"
    VersionPattern(None, (int,int)) -- construct "-Z.W"
    VersionPattern(str) -- parse a string into a VersionPattern
    
    Public methods:

    match() -- compare to a version major/minor number
    
    """

    # Constants representing the various pattern types  
    SIMPLE = 0    #  "X.Y"
    RANGE = 1     #  "X.Y-Z.W"
    UPTO = 2      #  "-X.Y"
    ANDON = 3     #  "Z.W-"

    # Printable constants, for repr()
    typenames = {
        SIMPLE : 'SIMPLE',
        RANGE  : 'RANGE',
        UPTO   : 'UPTO',
        ANDON  : 'ANDON',
    }

    def __init__(self, start, end=True):
        self.type = None
        if (type(start) in [str, unicode]):
            self.init_str(start)
        else:
            self.init_tup(start, end)
        self.tuple = (self.type, self.startpair, self.endpair)

    def init_tup(self, startpair, endpair):
        """init_tup(arg)

        Utility function for constructor. (Do not call.)
        """
        
        if (type(startpair) == tuple):
            (major, minor) = startpair
            if (major < 1):
                raise VersionFormatError('VersionPattern major value must be positive')
            if (minor < 0):
                raise VersionFormatError('VersionPattern minor value must be non-negative')

        if (type(endpair) == tuple):
            (major, minor) = endpair
            if (major < 1):
                raise VersionFormatError('VersionPattern major value must be positive')
            if (minor < 0):
                raise VersionFormatError('VersionPattern minor value must be non-negative')

        if (startpair is None):
            if (endpair is None):
                raise VersionFormatError('VersionPattern None None')
            if (endpair is True):
                raise VersionFormatError('VersionPattern None True')
            self.startpair = None
            self.endpair = endpair
            self.type = VersionPattern.UPTO
            return
        self.startpair = startpair
        if (endpair is True):
            self.endpair = None
            self.type = VersionPattern.SIMPLE
        elif (endpair is None):
            self.endpair = None
            self.type = VersionPattern.ANDON
        else:
            self.endpair = endpair
            self.type = VersionPattern.RANGE

    def init_str(self, val):
        """init_str(arg)

        Utility function for constructor. (Do not call.)
        """
        
        if (val.startswith('-')):
            startpair = None
            endpair = val[1:]
        elif (val.endswith('-')):
            startpair = val[:-1]
            endpair = None
        elif ('-' in val):
            pos = val.index('-')
            startpair = val[:pos]
            endpair = val[pos+1:]
        elif (val.endswith('.')):
            startpair = val[:-1]
            endpair = startpair
        else:
            startpair = val
            endpair = True

        if (type(startpair) in [str, unicode]):
            startpair = self.parse_number(startpair)
        if (type(endpair) in [str, unicode]):
            endpair = self.parse_number(endpair)
        self.init_tup(startpair, endpair)

    def parse_number(self, val):
        """parse_number(val) -> (int,int)

        Parse a string of the form "X" or "X.Y" into a pair of numbers.
        (If there is no second number, it is assumed to be zero.)

        This parsing is strict; no spaces or other extraneous characters
        are allowed.
        """
        
        pos = val.find('.')
        if (pos < 0):
            res = all_digits_regexp.match(val)
            if (res):
                return (int(val), 0)
            raise VersionFormatError('VersionPattern invalid: ' + val)

        valmaj = val[:pos]
        valmin = val[pos+1:]

        res = all_digits_regexp.match(valmaj)
        if (not res):
            raise VersionFormatError('VersionPattern invalid: ' + val)
        res = all_digits_regexp.match(valmin)
        if (not res):
            raise VersionFormatError('VersionPattern invalid: ' + val)

        return (int(valmaj), int(valmin))

    def __str__(self):
        if (self.type == VersionPattern.SIMPLE):
            (major, minor) = self.startpair
            return (str(major) + '.' + str(minor))
        if (self.type == VersionPattern.ANDON):
            (major, minor) = self.startpair
            return (str(major) + '.' + str(minor) + '-')
        if (self.type == VersionPattern.UPTO):
            (major, minor) = self.endpair
            return ('-' + str(major) + '.' + str(minor))
        if (self.type == VersionPattern.RANGE):
            (major, minor) = self.startpair
            val = (str(major) + '.' + str(minor))
            if (self.startpair == self.endpair):
                return val + '.'
            (major, minor) = self.endpair
            return val + ('-' + str(major) + '.' + str(minor))
        return '???'

    def __cmp__(self, other):
        return cmp(self.tuple, other.tuple)
    
    def __hash__(self):
        return hash(self.tuple)

    def match(self, major, minor):
        """match(major, minor) -> bool

        Compare the pattern to a version number (as major and minor
        values). Return True if the version number satisfies the pattern.
        """
        
        if (self.type == VersionPattern.SIMPLE):
            (patmajor, patminor) = self.startpair
            return (major == patmajor and minor >= patminor)
        if (self.type == VersionPattern.ANDON):
            (patmajor, patminor) = self.startpair
            return (major > patmajor 
                or (major == patmajor and minor >= patminor))
        if (self.type == VersionPattern.UPTO):
            (endmajor, endminor) = self.endpair
            return (major < endmajor
                or (major == endmajor and minor <= endminor))
        if (self.type == VersionPattern.RANGE):
            (patmajor, patminor) = self.startpair
            (endmajor, endminor) = self.endpair
            if (not (major > patmajor
                or (major == patmajor and minor >= patminor))):
                return False
            if (not (major < endmajor
                or (major == endmajor and minor <= endminor))):
                return False
            return True
        return False

