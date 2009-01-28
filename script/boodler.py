#!/usr/bin/env python

# Boodler: a programmable soundscape tool
# Designed by Andrew Plotkin <erkyrath@eblong.com>
# For more information, see <http://boodler.org/>
#
# This Python script ("boodler.py") is in the public domain. 
# The Python modules that it uses (boodle, boopak, and booman) are 
# licensed under the GNU Library General Public License (LGPL). The 
# cboodle extensions are licensed under either the LGPL or the GPL.
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

# same as in boodlemgr.py
if ('darwin' in sys.platform.lower()):
    Default_Relative_Data_Dir = 'Library/Application Support/Boodler'
else:
    Default_Relative_Data_Dir = '.boodler'

defaultdriver = 'oss'
if (sys.platform == 'darwin'):
    defaultdriver = 'macosx'
    try:
        # default to AudioQueue driver if we can identify the OS as 10.5
        # or iPhone.
        val = os.uname()
        if (val[0] == 'Darwin'):
            ls = val[2].split('.')
            if (int(ls[0]) >= 9):
                defaultdriver = 'osxaq'
    except:
        pass

# The next line may be modified during package installation.
configfiledriver = '' # CONFIGUREDDRIVER
if (configfiledriver):
    defaultdriver = configfiledriver.lower()

usage = 'usage: %prog [ options ] package/Agent [ data ... ]'

loglevels = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

popt = optparse.OptionParser(usage=usage,
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
popt.add_option('--stdinevents',
    action='store_true', dest='stdinlisten',
    help='accept events from stdin')
popt.add_option('-D', '--define',
    action='append', dest='extraopts', metavar='VAR=VAL',
    help='define additional driver parameters')
popt.add_option('--data', action='store', dest='basedir',
    metavar='DIR', help='directory to store Boodler sound information (default: HOME/'+Default_Relative_Data_Dir+')')
popt.add_option('--collection', action='store', dest='collection',
    metavar='DIR', help='directory which contains your sound collection (default: DATA/Collection)')
popt.add_option('--external', ### -E?
    action='append', dest='externaldirs', metavar='DIR',
    help='an additional directory in which to look for sound packages')
popt.add_option('--prop',     ### -P?
    action='append', dest='rootprops', metavar='VAR=VAL',
    help='define properties for the root channel')
popt.add_option('-L', '--log',
    action='store', type='choice', dest='loglevel', metavar='LEVEL',
    choices=loglevels.keys(),
    help='message level to log (default: warning)')
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
popt.add_option('--testsound',
    action='store_true', dest='playtestsound',
    help='play a test tune')

popt.set_defaults(
    driver=defaultdriver,
    ratewanted = 0,
    basevolume = 0.5,
    netlisten = False,
    stdinlisten = False,
    verboseerrors = False,
    verbosehardware = False,
    extraopts = [],
    rootprops = [],
    externaldirs = [])

(opts, args) = popt.parse_args()

import boopak.collect

# same as in boodlemgr.py
basedir = opts.basedir
if (not basedir):
    basedir = os.environ.get('BOODLER_DATA')
if (not basedir):
    basedir = os.path.join(os.environ.get('HOME'), Default_Relative_Data_Dir)

coldir = opts.collection
if (not coldir):
    coldir = os.environ.get('BOODLER_COLLECTION')
# basedir is overridden by coldir, if it is provided.
if (coldir is None and not (basedir is None)):
    coldir = os.path.join(basedir, boopak.collect.Filename_Collection)

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
    """LogFormatter: A logging formatter class, customized for Boodler.

    This has format strings built in. It also obeys the --verbose option
    (or lack of it) when showing backtraces, and when showing the logger
    name on each line.
    """
    
    def __init__(self, verbose):
        if (verbose):
            dateformat = '%b-%d %H:%M:%S'
        else:
            dateformat = '%H:%M:%S'
        logging.Formatter.__init__(self,
            '%(asctime)s (%(name)s) %(message)s', dateformat)
        if (not verbose):
            self.format = self.shortFormat
        self.verboseerrors = verbose
    def shortFormat(self, rec):
        """shortFormat(rec) -> str

        Custom formatting for non-verbose mode. This abbreviates the
        full logger name to just its last element. This method replaces
        the normal format() method when -v is not used.

        (Conceivably this could mess up the log message by abbreviating
        the name in the content section, as well as the header. I don't
        care.)
        """
        res = logging.Formatter.format(self, rec)
        if ('.' in rec.name):
            val = rec.name+')'
            shortname = val.split('.')[-1]
            res = res.replace(val, shortname)
        return res
    def formatException(self, tup):
        """formatException(tup) -> str

        Custom formatting for logged exceptions. If the --verbose option
        is not set, this shows only the bottom of the stack trace.

        For BoodlerErrors, this shows the lowest frame which is not in
        the boodle.* package. This is a moderately filthy hack, but
        convenient.
        """
        
        if (self.verboseerrors):
            # Standard, complete traceback.
            return logging.Formatter.formatException(self, tup)

        moreinfo = None
        limit = None
        notboodle = (isinstance(tup[1], boodle.BoodlerError)
            or isinstance(tup[1], boopak.pload.PackageLoadError))
        if (notboodle):
            # Iterate down the stack. Keep track of the last frame which
            # is not in the boodle package. (But don't count the initial
            # frames which are not in boodle; those are just the calling
            # script.)
            depth = 0
            inboodle = False
            tr = tup[2]
            while (tr):
                modname = tr.tb_frame.f_globals.get('__name__', '')
                if (modname == 'boodle' or modname.startswith('boodle.')
                    or modname == 'boopak' or modname.startswith('boopak.')):
                    inboodle = True
                else:
                    if (inboodle):
                        limit = depth+1
                tr = tr.tb_next
                depth += 1
            if (not limit):
                limit = None
        
        fl = StringIO.StringIO()
        traceback.print_tb(tup[2], limit=limit, file=fl)
        res = fl.getvalue()
        fl.close()
        fl = None

        ex = tup[1]
        if (isinstance(ex, SyntaxError)):
            # Add the description of the bad line.
            moreinfo = [
                '  File "%s", line %d' % (ex.filename, ex.lineno),
                '      '+ex.text.rstrip().replace('\t',' '),
                '     %s^' % (' '*ex.offset,),
            ]

        # Clear up the temp variables, to prevent the stack frame from
        # staring into the abyss.
        tup = None
        ex = None
        
        ls = res.split('\n')
        ls = [ ln for ln in ls if ln ]
        ls = ls[-2:]
        if (moreinfo):
            ls.extend(moreinfo)
        return ('\n'.join(ls))
        
rootlogger = logging.getLogger()
level = None

if (opts.logconfig):
    import logging.config
    logging.config.fileConfig(opts.logconfig)
    if (opts.loglevel):
        level = loglevels.get(opts.loglevel)
else:
    if (not opts.loglevel):
        level = logging.WARNING
    else:
        level = loglevels.get(opts.loglevel)
    roothandler = logging.StreamHandler(sys.stderr)
    roothandler.setFormatter(LogFormatter(opts.verboseerrors))
    rootlogger.addHandler(roothandler)

if (level):
    rootlogger.setLevel(level)

import boodle
import boopak.pload

if (not os.path.isdir(coldir)):
    rootlogger.error('collection directory does not exist: ' + coldir)
    # But we keep going, because --testsound should still work.
loader = boopak.pload.PackageLoader(coldir, importing_ok=True)

if (opts.externaldirs):
    import booman.command
    import booman.create
    for val in opts.externaldirs:
        # Go through a create cycle, so that resources are found.
        tup = booman.create.examine_directory(loader, val)
        (pkgname, pkgvers) = loader.add_external_package(val, tup[2], tup[3])
        rootlogger.warning('located external package: %s %s',
            pkgname, pkgvers)

from boodle import agent, generator, builtin
cboodle = boodle.cboodle

if (opts.listdrivers):
    ls = boodle.list_drivers()
    print len(ls), 'output drivers available:'
    for (key, name) in ls:
        print '   ', key+':', name

if (opts.driver):
    opts.driver = opts.driver.lower()
    cboodle = boodle.set_driver(opts.driver)


if (opts.playtestsound):
    if (len(args) != 0):
        rootlogger.warning('ignoring arguments, playing --testsound instead')
    args = [ '/boodle.builtin.TestSoundAgent' ]

if (opts.verbosehardware or opts.listdevices):
    # For these options, we need to start up the driver even if
    # no agent was specified. So specify a no-op agent.
    if (len(args) == 0):
        args = [ '/boodle.builtin.NullAgent' ]

if (len(args) == 0):
    if (opts.listdrivers):
        sys.exit()
    print usage.replace('%prog', os.path.basename(sys.argv[0]))
    sys.exit()

rootprops = []
val = os.environ.get('BOODLER_PROPERTIES')
if (val):
    for val in val.split(','):
        val = val.strip()
        pos = val.find('=')
        if (pos < 0):
            op = (val, True)
        else:
            op = (val[ : pos], val[pos+1 : ])
        rootprops.append(op)
        op = None
for val in opts.rootprops:
    pos = val.find('=')
    if (pos < 0):
        op = (val, True)
    else:
        op = (val[ : pos], val[pos+1 : ])
    rootprops.append(op)
    op = None

netport = opts.netport
if (netport is not None):
    if (not netport.startswith('/')):
        netport = int(netport)

gen = generator.Generator(opts.basevolume, opts.stdinlisten,
    opts.netlisten, netport, loader=loader)
if (opts.statsrate != None):
    gen.set_stats_interval(opts.statsrate)

try:
    # Set the global properties on the root channel.
    for (key, val) in rootprops:
        try:
            ### do we want to run val through the s-parser? Like args?
            gen.rootchannel.set_prop(key, val)
        except:
            rootlogger.warning('invalid name for property: ' + key)

    try:
        clas = agent.load_described(loader, args)
        ag = clas()
    except Exception, ex:
        rootlogger.error(str(ex))
        if (opts.verboseerrors):
            raise
        raise boodle.StopGeneration()
    if (not ag.inited):
        raise generator.ScheduleError('agent is uninitialized')
    gen.addagent(ag, gen.rootchannel, 0, ag.run)

    title = ag.get_title()
    if (not [True for (key,val) in extraopts if (key == 'title')]):
        # The extraopts get passed into the C extension, which only deals
        # with C (byte) strings. Therefore, we must convert a unicode title
        # to UTF-8.
        try:
            strtitle = title
            if (type(strtitle) is unicode):
                strtitle = strtitle.encode('UTF-8')
        except:
            strtitle = 'unable to encode agent title'
        extraopts.append( ('title', strtitle) )
    
    cboodle.init(opts.devname, opts.ratewanted, opts.verbosehardware, extraopts)
    extraopts = None

    try:
        rootlogger.warning('Running "' + title + '"')
        cboodle.loop(generator.run_agents, gen)
    finally:
        cboodle.final()
except boodle.StopGeneration:
    pass
except KeyboardInterrupt:
    rootlogger.warning('keyboard interrupt')
except Exception, ex:
    rootlogger.critical('%s: %s', ex.__class__.__name__, ex,
        exc_info=True)

gen.close()

