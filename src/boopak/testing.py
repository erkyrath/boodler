# Boodler: a programmable soundscape tool
# Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

"""testing: Unit tests for Boodler.

To run all tests:

    python -c 'from boopak import testing; testing.run()'

You can limit the test to a single module, or a space-separated list of
modules:

    python -c 'from boopak import testing; testing.run("pinfo pload")'
"""

import sys
import unittest

import boopak.test_pinfo
import boopak.test_version
import boopak.test_pload
import boopak.test_sparse
import boopak.test_argdef
import booman.create
import boodle.stereo

testlist = [
    ('version', boopak.test_version.TestVersion),
    ('sparse', boopak.test_sparse.TestSParse),
    ('argdef', boopak.test_argdef.TestArgDef),
    ('pinfo', boopak.test_pinfo.TestPInfo),
    ('pload', boopak.test_pload.TestPLoad),
    ('create', booman.create.TestCreate),
    ('stereo', boodle.stereo.TestStereo),
]

def run(arglist=[]):
    if (type(arglist) == str):
        arglist = arglist.split()
        
    if (not arglist):
        tests = testlist
    else:
        tests = [(key, case) for (key, case) in testlist if key in arglist]
        
    ls = [ case for (key, case) in tests ]
    print 'Running:', (' '.join([ key for (key, case) in tests ]))
    suitels = [ unittest.makeSuite(case) for case in ls ]
    suite = unittest.TestSuite(suitels)
    unittest.TextTestRunner().run(suite)

if __name__ == '__main__':
    run(sys.argv[1:])
