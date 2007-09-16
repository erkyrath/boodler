# Boodler: a programmable soundscape tool
# Copyright 2002-7 by Andrew Plotkin <erkyrath@eblong.com>
# <http://eblong.com/zarf/boodler/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.


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



