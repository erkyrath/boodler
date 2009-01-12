# Boodler: a programmable soundscape tool
# Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

"""music: Utility functions for musical computation.

get_pitch() -- the pitch factor that corresponds to a given number of semitones
decibel() -- the volume factor that corresponds to a given number of decibels
"""

import math

# The piano keyboard, expressed in semitones:
# 
#   1  3     6  8  10
#  0  2  4  5  7  9  11
#  C  D  E  F  G  A  B

chromatic_octave = []

for ix in range(12):
    val = pow(2.0, ix/12.0)
    chromatic_octave.append(val)

octaves = []

for ix in range(8):
    val = pow(2, ix)
    octaves.append(val)

def get_pitch(semi):
    """get_pitch(semi) -> float

    Return the pitch factor that corresponds to a given number of semitones.
    The argument must be an integer.

    If val is zero, this returns 1. If val is negative, this returns a
    value less than 1 (but greater than zero); this value will lower a
    sound by the given number of semitones. If val is positive, this
    returns a value greater than 1, which will raise a sound.

    Example: Raising a sound by one octave (twelve semitones) will exactly
    double its pitch; therefore, get_pitch(12) is 2.0.
    """
    
    pos = semi % 12
    oct = (semi - pos) / 12
    if (oct >= 0):
        if (oct >= 8):
            return chromatic_octave[pos] * pow(2.0, oct)
        else:
            return chromatic_octave[pos] * octaves[oct]
    else:
        if (oct <= -8):
            return chromatic_octave[pos] / pow(2.0, -oct)
        else:
            return chromatic_octave[pos] / octaves[-oct]



decibel_factor = 0.1 * math.log(10)
def decibel(val=0):
    """decibel(val=0) -> float

    Return the volume factor that corresponds to a given number of decibels.
    
    If val is zero, this returns 1. If val is negative, this returns a
    value less than 1 (but greater than zero); this value will reduce a
    sound by the given number of decibels. If val is positive, this
    returns a value greater than 1, which will amplify a sound.

    Example: Fading a sound by three decibels will approximately halve
    its amplitude; therefore, decibel(-3) is approximately 0.5.
    """
    return math.exp(val * decibel_factor)
