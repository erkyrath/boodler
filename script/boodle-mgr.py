#!/usr/bin/env python

# Boodler: a programmable soundscape tool
# Designed by Andrew Plotkin <erkyrath@eblong.com>
# For more information, see <http://eblong.com/zarf/boodler/>
#
# This Python script ("boodle-mgr.py") and the Python modules that it
# uses (boodle.boopak and boodle.booman) are licensed under the GNU
# Library General Public License (LGPL).
#
# You should have received a copy of the GNU Library General Public License
# along with this program. (It should be a document entitled "LGPL".) 
# If not, see the web URL above, or write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
###

install (file|url)       # install this
install (pkgv)           # find on web site, install
installdep (pkgv|file|url) # install, then install dependencies from web site
verify (pkgv|file|url)   # ensure it loads, display key and name
describe (pkgv|file|url) # display all metadata
contents (pkgv|file|url) # display all contents
versions (pkg)           # show all versions of this package
current                  # show current version of all packages
obsolete                 # list packages on which no current one depends
checkdep (pkgv|file|url) # ensure that all dependencies (trans) are avail
dependson (pkgv)         # what depends on this
remove (pkgv)            # delete this
removeall                # blow collection away
"""

import sys
import os
from optparse import OptionParser

from booman import frame

# same as in boodler.py
if ('darwin' in sys.platform.lower()):
	Default_Relative_Data_Dir = 'Library/Application Support/Boodler'
else:
	Default_Relative_Data_Dir = '.boodler'

parser = OptionParser()

parser.add_option('-d', '--data', action='store', dest='basedir',
	metavar='DIR', help='directory to store Boodler sound information (default: HOME/'+Default_Relative_Data_Dir+')')
parser.add_option('--collection', action='store', dest='collection',
	metavar='DIR', help='directory which contains your sound collection (default: DATA/Collection)')
parser.add_option('--download', action='store', dest='download',
	metavar='DIR', help='directory in which to store temporary download files (default: DATA/Download)')
parser.add_option('-f', '--force', action='store_true', dest='force',
	help='take action without asking for confirmation')
parser.add_option('--import', action='store_true', dest='importing_ok',
	help='allow importing (needed only for package creation)')

(options, args) = parser.parse_args()

if (options.force):
	frame.set_force_option()

# same as in boodler.py
basedir = options.basedir
if (not basedir):
	basedir = os.environ.get('BOODLER_DATA')
if (not basedir):
	basedir = os.path.join(os.environ.get('HOME'), Default_Relative_Data_Dir)

coldir = options.collection
if (not coldir):
	coldir = os.environ.get('BOODLER_COLLECTION')

dldir = options.download
if (not dldir):
	dldir = os.environ.get('BOODLER_DOWNLOAD')

if (not args):
	print 'Welcome to Boodle-Manager. Type "help" for a list of commands.'

# Prepare the package manager.		
frame.setup_loader(basedir, coldir, dldir, importing_ok=options.importing_ok)

# If args exist, execute them as a command. If not, loop grabbing and
# executing commands until we discover that the user has executed Quit.
# (The handler catches all exceptions except KeyboardInterrupt.)
try:
	if (args):
		frame.set_interactive(False)
		frame.handle(args)
	else:
		frame.set_interactive(True)
		while (not frame.quit_yet()):
			frame.handle([])
		print '<exiting>'
except KeyboardInterrupt:
	print '<interrupted>'

# Shut down the package manager.		
frame.cleanup()

