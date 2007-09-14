#!/usr/bin/env python

# Boodler: a programmable soundscape tool
# Designed by Andrew Plotkin <erkyrath@eblong.com>
# For more information, see <http://www.eblong.com/zarf/boodler/>
#
# This Python script, "boodler.py", is in the public domain. 
# The Python modules that it uses (the contents of the "boodle" package, 
# including the C modules "cboodle_*") are licensed under the GNU Library
# General Public License (LGPL).
#
# You should have received a copy of the GNU Library General Public License
# along with this program. (It should be a document entitled "LGPL".) 
# If not, see the web URL above, or write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import sys
import os
import optparse

usage = 'usage: %prog [ options ] module.AgentClass [ data ... ]'

popt = optparse.OptionParser(prog=sys.argv[0],
	usage=usage,
	formatter=optparse.IndentedHelpFormatter(short_first=False))

popt.add_option('-o', '--output',
	action='store', type='string', dest='driver',
	help='output driver to use') ### default?
popt.add_option('-m', '--master',
	action='store', type='float', dest='basevolume', metavar='VOLUME',
	help='master volume (default: 0.5)')
popt.add_option('-d', '--device',
	action='store', type='string', dest='devname', metavar='DEVICE',
	help='name of the audio device (if more than one exists)')
popt.add_option('-r', '--rate',
	action='store', type='int', dest='ratewanted', metavar='RATE',
	help='sample rate of output stream')
popt.add_option('-l', '--listen',
	action='store_true', dest='netlisten',
	help='accept events from other machines')
popt.add_option('-p', '--port',
	action='store', type='string', dest='netport', metavar='PORT',
	help='port to accept events on (if --listen is set)')
popt.add_option('-D', '--define',
	action='append', dest='extraopts', metavar='VAR=VAL',
	help='define additional driver parameters')
popt.add_option('--stats',
	action='store', type='float', dest='statsrate', metavar='SECONDS',
	help='display statistics at regular intervals')
popt.add_option('-v', '--verbose',
	action='store_true', dest='verboseerrors',
	help='display verbose errors')
popt.add_option('--hardware',
	action='store_true', dest='verbosehardware',
	help='display verbose information about driver')

popt.set_defaults(
	ratewanted = 0,
	basevolume = 0.5,
	netlisten = False,
	verboseerrors = False,
	verbosehardware = False,
	extraopts = [])
### default driver

(opts, args) = popt.parse_args()

extraopts = []
for val in opts.extraopts:
	pos = val.find('=')
	if (pos < 0):
		op = (val, None)
	else:
		op = (val[ : pos], val[pos+1 : ])
	extraopts.append(op)
	op = None

import boodle
from boodle import agent, generator
cboodle = boodle.cboodle

if (opts.driver):
	cboodle = boodle.set_driver(opts.driver)

if (opts.verbosehardware and len(args) == 0):
	args = ['']

if (len(args) == 0):
	print usage.replace('%prog', sys.argv[0])
	sys.exit()

effects_dir = os.environ.get('BOODLER_EFFECTS_PATH')
if (effects_dir):
	effects_dir = effects_dir.split(':')
	for dir in effects_dir:
		if (len(dir) > 0):
			sys.path.append(dir)

clas = agent.load_class_by_name(args[0])

netport = opts.netport
if ((netport is not None) and netport.startswith('/')):
	netport = int(netport)

gen = generator.Generator(opts.basevolume, opts.netlisten, netport)
if (opts.verboseerrors):
	gen.set_verbose_errors(True)
if (opts.statsrate != None):
	gen.set_stats_interval(opts.statsrate)

try:
	ag = apply(clas, args[1:])
	if (not ag.inited):
		raise generator.ScheduleError('agent is uninitialized')
	gen.addagent(ag, gen.rootchannel, 0)
	
	cboodle.init(opts.devname, opts.ratewanted, opts.verbosehardware, extraopts)
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

