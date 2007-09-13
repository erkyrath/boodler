#!/usr/bin/python

# Boodler: a programmable soundscape tool
# Designed by Andrew Plotkin <erkyrath@eblong.com>
# For more information, see <http://www.eblong.com/zarf/boodler/>
#
# This Python script, "boodler.py", is in the public domain. 
# The Python modules that it uses (the contents of the "boodle" package, 
# including the C module "cboodle") are licensed under the GNU Library 
# General Public License (LGPL).
#
# You should have received a copy of the GNU Library General Public License
# along with this program. (It should be a document entitled "LGPL".) 
# If not, see the web URL above, or write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import sys
import os
import string
import getopt
from boodle import agent, generator, cboodle

try:
	(opts, args) = getopt.getopt(sys.argv[1:], 'd:r:m:lp:vD:', 
		['device=', 'rate=', 'listen', 'port=', 'verbose', 'hardware', 'stats=', 'master=', 'define='])
except getopt.error, ex:
	print (sys.argv[0] + ':'), str(ex)
	sys.exit()

devname = None
ratewanted = 0
netlisten = 0
netport = None
verboseerrors = 0
verbosehardware = 0
statsrate = None
basevolume = 0.5
extraopts = []

for (opname, opval) in opts:
	if (opname == '--device' or opname == '-d'):
		devname = opval
	elif (opname == '--rate' or opname == '-r'):
		ratewanted = int(opval)
	elif (opname == '--listen' or opname == '-l'):
		netlisten = 1
	elif (opname == '--port' or opname == '-p'):
		if (opval[0] == '/'):
			netport = opval
		else:
			netport = int(opval)
	elif (opname == '--verbose' or opname == '-v'):
		verboseerrors = 1
	elif (opname == '--hardware'):
		verbosehardware = 1
	elif (opname == '--stats'):
		statsrate = float(opval)
	elif (opname == '--master' or opname == '-m'):
		basevolume = float(opval)
	elif (opname == '--define' or opname == '-D'):
		pos = string.find(opval, '=')
		if (pos < 0):
			op = (opval, None)
		else:
			op = (opval[ : pos], opval[pos+1 : ])
		extraopts.append(op)
		op = None

if (verbosehardware and len(args) == 0):
	args = ['']

if (len(args) == 0):
	print 'usage:', sys.argv[0], '[--device /dev/device] [--rate soundrate] [--master volume] [--define key=val] [--verbose] [--hardware] [--stats interval] [--listen] [--port]', 'module.AgentClass [ data ... ]'
	sys.exit()

effects_dir = os.environ.get('BOODLER_EFFECTS_PATH')
if (effects_dir):
	effects_dir = string.split(effects_dir, ':')
	for dir in effects_dir:
		if (len(dir) > 0):
			sys.path.append(dir)

clas = agent.load_class_by_name(args[0])

gen = generator.Generator(basevolume, netlisten, netport)
if (verboseerrors):
	gen.set_verbose_errors(1)
if (statsrate != None):
	gen.set_stats_interval(statsrate)

try:
	ag = apply(clas, args[1:])
	if (not ag.inited):
		raise generator.ScheduleError('agent is uninitialized')
	gen.addagent(ag, gen.rootchannel, 0)
	
	cboodle.init(devname, ratewanted, verbosehardware, extraopts)
	extraopts = None

	try:
		try:
			print ('running "' + ag.getname() + '"')
			cboodle.loop(generator.run_agents, gen)
		finally:
			cboodle.final()
	except generator.StopGeneration:
		pass
finally:
	gen.close()

