# Boodler: a programmable soundscape tool
# Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

import traceback
import StringIO

# Global state for the command interpreter.

# loader: the PackageCollection object.
loader = None

# shutdown: set True by the Quit command.
shutdown = False

# is_interactive: True if the interpreter is prompting for commands;
#   False if the interpreter was given commands as arguments.
is_interactive = False

# last_backtrace: the stack trace (in string form) of the last Exception
#   caught by the interpreter.
last_backtrace = None

# is_force: whether to prompt to confirm dangerous actions. True if
#   the --force command-line option was supplied.
is_force = False

def set_force_option(val=True):
    """set_force_option(val=True) -> None

    Set whether the interpreter should prompt to confirm dangerous actions.
    (True means don't.) This is called during setup if the --force option
    was supplied.
    """
    global is_force
    is_force = val

def set_interactive(val=True):
    """set_interactive(val=True) -> None

    Set whether the interpreter is prompting for commands, or if commands
    were supplied as arguments.
    """
    global is_interactive
    is_interactive = val

def quit_yet():
    """quit_yet() -> bool

    Return whether the Quit command has been executed.
    """
    return shutdown

def set_quit(val=True):
    """set_quit(val=True) -> None

    Set the shutdown flag. This is called when the Quit command is executed.
    """
    global shutdown
    shutdown = val

def get_last_backtrace():
    """get_last_backtrace() -> str

    Get a string representation of the backtrace of the last Exception
    that was caught.

    (The return string will have several lines, separated by newlines.
    However, it will not end with a newline.)
    """
    return last_backtrace

def note_backtrace():
    """note_backtrace() -> None

    Record a string representation of the backtrace of the current Exception.
    This should only be called from an exception handler.
    """
    global last_backtrace

    fl = StringIO.StringIO()
    traceback.print_exc(None, fl)
    last_backtrace = fl.getvalue().rstrip()
    fl.close()

def setup_loader(basedir, coldir, dldir, importing_ok=False):
    """setup_loader(basedir, coldir, dldir, importing_ok=False) -> None

    Create the PackageCollection, which will be used by all commands.
    (See the PackageCollection class for the arguments.)
    """
    global loader
    loader = collect.PackageCollection(basedir, coldir, dldir,
        importing_ok=importing_ok)

def handle(args=None):
    """handle(args=None) -> None

    Process one command (from user input, or from the arguments provided).
    In interactive mode, this is called repeatedly. If there are command-
    line arguments, this is called once, with the list of arguments passed
    in.

    This catches all exceptions except KeyboardInterrupt.
    """
    global last_backtrace

    # Very, very late import
    import booman.command

    try:
        # Print a blank line between interactive commands.
        if (is_interactive):
            print

        # Some ugliness here. If the user types a blank line at an input
        # prompt, it will show up as a CommandCancelled exception. We
        # want to prompt again, without exiting the handle() function or
        # printing another blank line. So we do a little loop here. If
        # a command is typed, or we get any exception *except* a
        # CommandCancelled, this loop only runs once.
        while (True):
            try:
                source = token.InputSource(args)
                tok = booman.command.CommandToken()
                cmdclass = tok.accept(source)
                break
            except CommandCancelled:
                pass
        # Okay, we got a command. Execute it.
        cmd = cmdclass()
        cmd.perform(source)
    except CommandError, ex:
        # Simple exception: print the message.
        if (str(ex)):
            print str(ex)
    except KeyboardInterrupt:
        # EOF or interrupt. Pass it on.
        raise
    except Exception, ex:
        # Unexpected exception: print it, and save a backtrace.
        note_backtrace()
        print 'Python exception:', ex.__class__.__name__+':', str(ex)

def cleanup():
    """cleanup() -> None

    Shut down the PackageCollection object. Must be called when the
    interpreter is exiting.
    """
    global loader
    if (loader):
        loader.shut_down()
        loader = None


# Late imports

from boopak import collect
import booman
from booman import CommandError, CommandCancelled
from booman import token
