#!/usr/bin/env python

# A cheesy script that runs pydoc on all of Boodler's modules, writing
# HTML documentation into doc/pydoc. I run this after "setup.py build_py",
# but you don't have to; the current doc/pydoc files are checked into
# SVN.

import sys, os, os.path
import re
import subprocess

packages = [ 'boodle', 'boopak', 'booman' ]
PYTHON_DOC_URL = 'http://www.python.org/doc/current/library/'

sysmodules = [
    '__builtin__', 'aifc', 'bisect', 'codecs', 'errno', 'exceptions',
    'fcntl', 'fileinput',
    'imp', 'inspect', 'keyword', 'logging', 'math', 'os', 're',
    'readline', 'select', 'sets', 'socket', 'StringIO', 'struct', 'sunau',
    'sys', 'tempfile', 'time', 'traceback', 'types', 'unittest',
    'wave', 'zipfile',
]
sysmodules = dict([ (key, True) for key in sysmodules])

index_head = """
<!doctype html PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<html><head><title>Python: Boodler packages</title>
</head><body bgcolor="#f0f0f8">

<table width="100%" cellspacing=0 cellpadding=2 border=0 summary="heading">
<tr bgcolor="#7799ee">
<td valign=bottom>&nbsp;<br>
<font color="#ffffff" face="helvetica, arial">&nbsp;<br><big><big><strong>boodler contents</strong></big></big></font></td>
</tr></table>

<p>
Boodler contains three main packages, each containing several modules.
</p>

<p>
If your goal is to build soundscapes, you will mostly be interested in
the <a href="boodle.agent.html#Agent">Agent</a> class,
the <a href="boodle.generator.html#Channel">Channel</a> class,
and (for argument types) the <a href="boopak.argdef.html">argdef</a> module.
</p>

<p>
(This reference documentation is generated from the source code by
<a href="http://www.python.org/doc/current/library/pydoc">pydoc</a>.
That's why it's a little rough. You will see more information about
the Exception classes than you really care about. Also,
document sections may be listed in an unintuitive order, making it
hard to read the pages top to bottom. We apologize.)
</p>

<table width="100%" cellspacing=0 cellpadding=2 border=0 summary="section">
<tr bgcolor="#aa55cc">
<td colspan=3 valign=bottom>&nbsp;<br>
<font color="#ffffff" face="helvetica, arial"><big><strong>Modules</strong></big></font></td></tr>
    
<tr><td bgcolor="#aa55cc"><tt>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</tt></td>
<td>&nbsp;</td>
<td width="100%">

<table width="100%" summary="list"><tr>

"""

index_tail = """

</tr></table>

</td></tr></table>

</body></html>
"""

if (len(sys.argv) < 2):
    print 'usage: python dodoc.py build/lib.XXXX'
    sys.exit(1)

buildpath = sys.argv[1]
buildpath = os.path.abspath(buildpath)

os.chdir('doc')
os.chdir('pydoc')

if (not os.path.isdir(buildpath)):
    print 'path does not exist:', buildpath
    sys.exit(1)

modules = []
    
for pkg in packages:
    path = os.path.join(buildpath, pkg)
    if (not os.path.isdir(path)):
        print 'package does not exist:', path
        sys.exit(1)
        
    modules.append(pkg)
    
    files = os.listdir(path)
    files.sort()
    for file in files:
        if (file.startswith('_')):
            continue
        if (file.startswith('test_')):
            continue
        if (not file.endswith('.py')):
            continue
        modules.append(pkg+'.'+file[:-3])

fileurl_regex = re.compile('href="file:([^"]*)"')
sysmod_regex = re.compile('href="([a-zA-Z_]*).html(#[a-zA-Z_]*)?"')
testmod_regex = re.compile('<a href="[a-z]*.test_[a-z]*.html">([a-z_]*)</a>')
cboodlemod_regex = re.compile('<a href="[a-z]*.cboodle_[a-z]*.html">([a-z_]*)</a>')
agentinherit_regex = re.compile('Methods inherited from <a href="boodle.agent.html#Agent">boodle.agent.Agent</a>:.*?</td>', re.DOTALL)

def fileurl_func(match):
    val = match.group(1)
    pos = val.find(buildpath)
    if (pos < 0):
        raise Exception('buildpath not in fileurl')
    srcname = val[ pos+len(buildpath) : ]
    return 'href="../../src%s"' % (srcname,)

def sysmod_func(match):
    val = match.group(1)
    if (not sysmodules.has_key(val)):
        if (not (val in packages)):
            print 'Warning: link to "%s.html" unmunged.' % (val,)
        return match.group(0)
    val = val.lower()
    fragment = match.group(2)
    if (fragment is None):
        fragment = ''
    return 'href="%s%s.html%s"' % (PYTHON_DOC_URL, val, fragment)

for mod in modules:
    ret = subprocess.call(['pydoc', '-w', mod])
    if (ret):
        print 'pydoc failed on', mod, ':', ret
        sys.exit(1)
        
    file = mod+'.html'
    fl = open(file)
    dat = fl.read()
    fl.close()

    newdat = dat + '\n'
    newdat = fileurl_regex.sub(fileurl_func, newdat)
    newdat = newdat.replace(buildpath+'/', '')
    newdat = sysmod_regex.sub(sysmod_func, newdat)
    newdat = testmod_regex.sub('\\1', newdat)
    newdat = cboodlemod_regex.sub('\\1', newdat)
    if (mod == 'boodle.builtin'):
        newdat = agentinherit_regex.sub('</td>', newdat)
    newdat = newdat.replace('href="."', 'href="index.html"')

    fl = open(file, 'w')
    fl.write(newdat)
    fl.close()

modsets = []
for mod in modules:
    if (not ('.' in mod)):
        modsets.append([])
    modsets[-1].append(mod)

fl = open('index.html', 'w')
fl.write(index_head)
for ls in modsets:
    fl.write('<td width="25%" valign=top>\n')
    for mod in ls:
        if (not ('.' in mod)):
            fl.write('<strong><a href="%s.html">%s</a></strong><br>\n' % (mod, mod))
        else:
            fl.write('<a href="%s.html">%s</a><br>\n' % (mod, mod))
    fl.write('</td>\n')
fl.write(index_tail)
fl.close()
print 'build index.html'
