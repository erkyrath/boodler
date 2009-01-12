# Boodler: a programmable soundscape tool
# Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

# readline is not available on all platforms, but we import it if possible.
try:
    import readline
except:
    pass

import os.path

class Token:
    """Token: represents a command element to be parsed.

    Or you can think of it this way: a Token is an object which can grab
    an element from the user's input (whether from a prompt or from a
    command-line argument). Each subclass of Token grabs a particular
    kind of element. For example, CommandToken (in command.py) grabs
    a word that matches one of the commands (help, quit, etc).

    Publicly readable fields:

    prompt -- the string to use when prompting for this element (by itself)

    Methods:

    accept() -- grab the desired command element and return it.
    """

    prompt = ''
    
    def accept(self, source):
        """accept(source) -> value

        Grab the desired command element from the given InputSource, and
        return it. The type of value returned depends on the Token subclass.

        (Raising KeyboardInterrupt is always a possibility.)
        """
        raise NotImplementedError(str(self))

class YesNoToken(Token):
    """YesNoToken: Grab a "yes" or "no" element from the user. This
    token is always interactive; ignores command-line arguments and
    dangling parts of the InputSource, and goes straight for
    input_line().

    Returns True or False. (But not CommandCancelled.)
    """

    prompt = 'yes/no'
    
    def accept(self, source):
        while (True):
            try:
                ln = input_line(self.prompt)
            except CommandCancelled:
                return False
            ln = ln.lower()
            if (ln.startswith('y')):
                return True
            if (ln.startswith('n')):
                return False
            print '(Type "yes" or "no")'

class PathToken(Token):
    """PathToken: Grab the name of a file or directory.

    PathToken(mustexist=True) -- constructor

    If mustexist is True, this only accepts the name of a file or directory
    which exists.
    """

    prompt = 'path'
    
    def __init__(self, mustexist=True):
        self.mustexist = mustexist

    def accept(self, source):
        val = source.pop_word(self)
        if (not os.path.exists(val)):
            if (self.mustexist):
                raise CommandError('Does not exist: ' + val)
            return (val, False)
        else:
            return (val, True)
    
class FileToken(PathToken):
    """FileToken: Grab the name of a file.

    FileToken(mustexist=True) -- constructor

    If mustexist is True, this only accepts the name of a file
    which exists.
    """

    prompt = 'file'
    
    def accept(self, source):
        (val, exists) = PathToken.accept(self, source)
        if (exists and not os.path.isfile(val)):
            raise CommandError('Not a file: ' + val)
        return (val, exists)

class DirToken(PathToken):
    """DirToken: Grab the name of a file.

    DirToken(mustexist=True) -- constructor

    If mustexist is True, this only accepts the name of a directory
    which exists.
    """

    prompt = 'dir'
    
    def accept(self, source):
        (val, exists) = PathToken.accept(self, source)
        if (exists and not os.path.isdir(val)):
            raise CommandError('Not a directory: ' + val)
        return (val, exists)

class PackageToken(Token):
    """PackageToken: Grab the name of a package.
    """

    prompt = 'package'
    
    def accept(self, source):
        val = source.pop_word(self)
        try:
            pinfo.parse_package_name(val)
        except:
            raise CommandError('Invalid package name: ' + val)
        return val

class PackageOptVersionToken(Token):
    """PackageOptVersionToken: Grab the name of a package, and also
    a version number (if one is provided). Returns (pkgname, vers)
    where vers may be a VersionNumber, VersionSpec, or None.
    """

    prompt = 'package'

    greedy = True
    
    def accept(self, source):
        val = source.pop_word(self)
        
        if (':' in val):
            try:
                (pkgname, vers) = pinfo.parse_package_version_spec(val)
                return (pkgname, vers)
            except:
                raise CommandError('Invalid package name: ' + val)
            
        try:
            pinfo.parse_package_name(val)
        except:
            raise CommandError('Invalid package name: ' + val)

        pkgname = val
        val = None
        vers = None

        if (not source.is_empty()):
            val = source.pop_word(self)
            try:
                vers = version.VersionNumber(val)
            except version.VersionFormatError:
                if (self.greedy):
                    raise CommandError('Invalid version number: ' + val)
                if (not (val is None)):
                    source.push_word(val)
        return (pkgname, vers)

class PackageFileURLToken(Token):
    """PackageFileURLToken: Grab the name of a package (including version
    number if available), or a filename, or a URL. Returns one of the
    tuples

        (collect.Source_PACKAGE, (pkgname, vers))
        (collect.Source_FILE, filename)
        (collect.Source_URL, url)

    This uses some slightly rough heuristics to decide what's a package
    name and what's a filename.
    """

    prompt = 'package/file/url'

    greedy = True

    def accept(self, source):
        val = source.pop_word(self)

        if (':' in val
            and not (val.startswith('/') or val.startswith('\\') or val.startswith('.'))):
            pos = val.find(':')
            dotpos = val.find('.')
            if (dotpos < 0 or dotpos > pos):
                return (collect.Source_URL, val)

        if (val.endswith('.zip') or val.endswith(collect.Suffix_PackageArchive)):
            return (collect.Source_FILE, val)
        
        if (':' in val):
            try:
                (pkgname, vers) = pinfo.parse_package_version_spec(val)
                return (collect.Source_PACKAGE, (pkgname, vers))
            except:
                pass
        
        try:
            pinfo.parse_package_name(val)
        except:
            return (collect.Source_FILE, val)

        pkgname = val
        val = None
        vers = None

        if (not source.is_empty()):
            val = source.pop_word(self)
            try:
                vers = version.VersionNumber(val)
            except version.VersionFormatError:
                if (self.greedy):
                    raise CommandError('Invalid version number: ' + val)
                if (not (val is None)):
                    source.push_word(val)
        return (collect.Source_PACKAGE, (pkgname, vers))

class ResourceToken(Token):
    """ResourceToken: Grab the name of a resource. This must be
    pkgname/resource, pkgname:spec/resource, or pkgname::vers/resource.
    Returns ((pkgname, vers), resource), where vers will be None,
    a VersionSpec, or a VersionNumber.
    """

    prompt = 'resource'
    
    def accept(self, source):
        val = source.pop_word(self)
        pos = val.find('/')
        if (pos < 0):
            raise CommandError('Not of form package/resource: ' + val)

        res = val[ pos+1 : ]
        val = val[ : pos ]

        try:
            pinfo.parse_resource_name(res)
        except:
            raise CommandError('Invalid resource name: ' + res)
            
        try:
            (pkg, vers) = pinfo.parse_package_version_spec(val)
        except:
            raise CommandError('Invalid package name: ' + val)
        
        return ( (pkg, vers), res )


class InputSource:
    """InputSource: represents the user's input (which may include command-
    line arguments and pieces of previously-typed commands). Various Tokens
    pull information out of the InputSource; when it is empty, it asks
    for more from the user.
    
    A Token can also push information back into the InputSource, which
    means that lookahead is possible.

    InputSource(args=None) -- constructor

    The args, if supplied, should be a list of shell-style arguments. 
    (That is, entries may contain whitespace; and the whitespace should be
    considered to be a part of the entries, as opposed to separating
    entries.)

    Methods:

    is_empty() -- check whether any input is currently stored up
    pop_word() -- grab one word of input
    push_word() -- push back one word of input
    drain() -- grab all remaining words of input
    """

    # Constants representing what kind of input is currently stored up.
    EMPTY = 0
    SHELL = 1
    LINE  = 2

    def __init__(self, args=None):
        self.state = self.EMPTY
        self.list = None
        self.line = None
        self.pushback = []

        if (args is None or args == []):
            return
        else:
            self.state = self.SHELL
            self.list = args

    def is_empty(self):
        """is_empty() -> bool

        Check whether any input is currently stored up.
        """
        return (self.state == self.EMPTY and (not self.pushback))

    def pop_word(self, tok):
        """pop_word(tok) -> str

        Grab one word of input. This typically means one whitespace-
        delimited word (although arguments from the command line are
        treated a bit differently).

        If no input is available, the user is prompted for some, using
        the token argument's prompt.
        """

        if (self.pushback):
            return self.pushback.pop()

        if (self.is_empty()):
            self.state = self.LINE
            self.line = input_line(tok.prompt)

        if (self.state == self.SHELL):
            val = self.list.pop(0)
            if (not self.list):
                self.state = self.EMPTY
            return val
        if (self.state == self.LINE):
            # Maybe we should allow backslash escapes
            pos = self.line.find(' ')
            if (pos < 0):
                val = self.line
                self.line = ''
            else:
                val = self.line[:pos].strip()
                self.line = self.line[pos+1:].strip()
            if (not self.line):
                self.state = self.EMPTY
            return val

    def push_word(self, val):
        """push_word(val) -> None

        Push back one word of input. This will become the next word popped.
        """
        self.pushback.append(val)

    def drain(self):
        """drain() -> list of str

        Grab all the remaining words of input, and return them as a list.
        If the InputSource is empty, this returns an empty list.
        """

        res = []
        while (not self.is_empty()):
            res.append(self.pop_word(None))
        return res

def input_line(prompt=''):
    """input_line(prompt='') -> str

    Read a line of text, using readline (if available). The prompt will
    be ">" following the optional prompt argument. The line returned will
    be whitespace-stripped.

    If the user enters an empty line, this raises CommandCancelled.
    If the user interrupts the program, this raises KeyboardInterrupt.
    (EOF on stdin also appears as a KeyboardInterrupt.)
    """
    try:
        ln = raw_input(prompt+'> ')
        ln = ln.strip()
        if (not ln):
            raise CommandCancelled()
        return ln
    except EOFError:
        raise KeyboardInterrupt()

# Late imports
from boopak import version
from boopak import pinfo
from boopak import collect
from booman import CommandError, CommandCancelled
