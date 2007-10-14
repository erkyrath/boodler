#!/usr/bin/env python

# Boodler: a programmable soundscape tool
# Designed by Andrew Plotkin <erkyrath@eblong.com>
# For more information, see <http://eblong.com/zarf/boodler/>
#
# This Python script, "boodler.py", is in the public domain. 
# The Python modules that it uses are licensed under the GNU Library
# General Public License (LGPL). The cboodle extensions are licensed
# under either the LGPL or the GPL.
#
# You should have received a copy of the GNU Library General Public License
# along with this program. (It should be a document entitled "LGPL".) 
# If not, see the web URL above, or write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import sys
import os
import optparse
import logging
import traceback
import StringIO

defaultdriver = 'oss'
if (sys.platform == 'darwin'):
	defaultdriver = 'macosx'

# The next line may be modified during package installation.
configfiledriver = '' # CONFIGUREDDRIVER
if (configfiledriver):
	defaultdriver = configfiledriver.lower()

usage = 'usage: %prog [ options ] module.AgentClass [ data ... ]'

loglevels = {
	'debug': logging.DEBUG,
	'info': logging.INFO,
	'warning': logging.WARNING,
	'error': logging.ERROR,
	'critical': logging.CRITICAL
}

popt = optparse.OptionParser(prog=sys.argv[0],
	usage=usage,
	formatter=optparse.IndentedHelpFormatter(short_first=False))

popt.add_option('-o', '--output',
	action='store', type='string', dest='driver',
	help='output driver to use (default: '+defaultdriver+')')
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
popt.add_option('-L', '--log',
	action='store', type='choice', dest='loglevel', metavar='LEVEL',
	choices=loglevels.keys(),
	help='message level to log (default: error)')
popt.add_option('--logconfig',
	action='store', type='string', dest='logconfig', metavar='CONFIGFILE',
	help='log configuration file')
popt.add_option('--stats',
	action='store', type='float', dest='statsrate', metavar='SECONDS',
	help='display statistics at regular intervals')
popt.add_option('-v', '--verbose',
	action='store_true', dest='verboseerrors',
	help='display verbose errors')
popt.add_option('--hardware',
	action='store_true', dest='verbosehardware',
	help='display verbose information about driver')
popt.add_option('--list-drivers',
	action='store_true', dest='listdrivers',
	help='list all available output drivers')
popt.add_option('--list-devices',
	action='store_true', dest='listdevices',
	help='list all available device names')

popt.set_defaults(
	driver=defaultdriver,
	ratewanted = 0,
	basevolume = 0.5,
	netlisten = False,
	verboseerrors = False,
	verbosehardware = False,
	extraopts = [])

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

if (opts.listdevices):
	extraopts.append( ('listdevices', None) )

class LogFormatter(logging.Formatter):
	def __init__(self, verbose):
		logging.Formatter.__init__(self,
			'%(asctime)s: %(levelname)-8s: (%(name)s) %(message)s',
			'%b-%d %H:%M:%S')
		self.verboseerrors = verbose
	def formatException(self, tup):
		if (self.verboseerrors):
			return logging.Formatter.formatException(self, tup)
		fl = StringIO.StringIO()
		traceback.print_tb(tup[2], file=fl)
		res = fl.getvalue()
		fl.close()
		fl = None
		tup = None
		ls = res.split('\n')
		return ('\n'.join(ls[-3:]))
		
rootlogger = logging.getLogger()
level = None

if (opts.logconfig):
	import logging.config
	logging.config.fileConfig(opts.logconfig)
	if (opts.loglevel):
		level = loglevels.get(opts.loglevel)
else:
	if (not opts.loglevel):
		level = logging.ERROR
	else:
		level = loglevels.get(opts.loglevel)
	roothandler = logging.StreamHandler(sys.stderr)
	roothandler.setFormatter(LogFormatter(opts.verboseerrors))
	rootlogger.addHandler(roothandler)

if (level):
	rootlogger.setLevel(level)

import boodle
from boodle import agent, generator
cboodle = boodle.cboodle

if (opts.listdrivers):
	ls = boodle.list_drivers()
	print len(ls), 'output drivers available:'
	for (key, name) in ls:
		print '   ', key+':', name

if (opts.driver):
	opts.driver = opts.driver.lower()
	cboodle = boodle.set_driver(opts.driver)

avoidstdout = False
if (opts.driver == 'stdout'):
	avoidstdout = True

if (opts.verbosehardware or opts.listdevices):
	# For these options, we need to start up the driver even if
	# no agent was specified. So specify a no-op agent.
	if (len(args) == 0):
		args = ['']

if (len(args) == 0):
	if (opts.listdrivers):
		sys.exit()
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

	title = ag.getname()
	if (not [True for (key,val) in extraopts if (key == 'title')]):
		extraopts.append( ('title', title) )
	
	cboodle.init(opts.devname, opts.ratewanted, opts.verbosehardware, extraopts)
	extraopts = None

	try:
		try:
			if (not avoidstdout):
				print ('running "' + title + '"')
			cboodle.loop(generator.run_agents, gen)
		finally:
			cboodle.final()
	except generator.StopGeneration:
		pass
finally:
	gen.close()

