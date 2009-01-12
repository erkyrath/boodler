# Boodler: a programmable soundscape tool
# Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

"""agent: A module which contains the Agent class, the fundamental work
unit of Boodler.
"""

import logging
import types

class Agent:
    """Agent: base class for Boodler agents.

    Methods and fields to be overridden:

    init() -- set the agent up
    run() -- perform the agent's action
    receive() -- perform the agent's action

    Publicly readable fields:

    channel -- the channel in which this agent is running
    firsttime -- True the first time the run() method is called

    Methods which can be called from a run() method:

    sched_note() -- schedule a note to be played
    sched_note_duration() -- schedule a note to be played for an extended time
    sched_note_pan() -- schedule a note to be played at a stereo position
    sched_note_duration_pan() -- schedule a note, extended and stereo
    sched_note_params() -- schedule a note, allowing all parameters
    sched_agent() -- schedule another agent to run
    resched() -- schedule self to run again
    new_channel() -- create a channel
    new_channel_pan() -- create a channel at a stereo position
    listen() -- begin listening for events
    unlisten() -- stop listening
    get_root_channel() -- return the root channel of the channel tree
    post_listener_agent() -- post another agent to listen for events
    send_event() -- create an event, which posted agents may receive
    get_prop() -- get a property from the agent's channel
    has_prop() -- see whether the agent's channel has a given property
    set_prop() -- set a property on the agent's channel
    del_prop() -- delete a property from the agent's channel
    load_described() -- load a named module or agent

    Class methods:
    
    get_title() -- return a string which describes the agent
    get_argument_list() -- return the argument specification for the agent
    get_class_name() -- return the qualified names of the module and Agent
    """

    # Class members:

    # The default inited flag; instances set this true in __init__().
    inited = False
    # Another default value; subclasses can override this.
    selected_event = None
    
    # Another default value. A subclass can override this to specify
    # extra information about its argument types (more information than
    # can be inferred by inspecting the init() method).
    _args = None

    # Maps Agent subclasses to (pkgname, resname, bool) pairs;
    # see get_class_name().
    # (This does not get wiped during loader.clear_cache(), which means
    # obsolete classes stay alive forever, at least in an importing
    # environment. If we really cared, we'd use weak key refs.)
    cached_class_names = {}

    # Maps Agent subclasses to ArgLists; see get_argument_list().
    cached_argument_lists = {}
    
    def __init__(self, *args, **kwargs):
        self.inited = True
        self.queued = False
        self.handlers = {}
        self.firsttime = True
        self.generator = None
        self.channel = None
        self.origdelay = None
        
        tup = self.get_class_name()
        if (tup[2]):
            val = 'pkg.' + tup[0] + '.' + tup[1]
        else:
            val = tup[0] + '.' + tup[1]
        self.logger = logging.getLogger(val)

        try:
            self.init(*args, **kwargs)
        except TypeError, ex:
            raise boodle.BoodlerError(str(ex))

    def sched_note(self, samp, pitch=1.0, volume=1.0, delay=0, chan=None):
        """sched_note(sample, pitch=1, volume=1, delay=0, chan=self.channel)
            -> duration

        Schedule a note to play. The sound is loaded from samp (which can
        be a filename, File, or Sample object). The pitch is given as a
        multiple of the sound's original frequency; the volume is given
        as a fraction of the sound's original volume. The delay is a time
        (in seconds) to delay before the note is played. The channel,
        if None or not supplied, defaults to the same channel the agent is
        running in.

        This returns the expected duration of the sound, in seconds.
        """

        return self.sched_note_pan(samp, None, pitch, volume, delay, chan)

    def sched_note_pan(self, samp, pan=None, pitch=1.0, volume=1.0, delay=0,
        chan=None):
        """sched_note_pan(sample, pan=0, pitch=1, volume=1, delay=0,
            chan=self.channel) -> duration

        Schedule a note to play, panning the stereo origin of the sound.
        The pan value defaults to 0, meaning no shift in origin;
        -1 means directly to the left; 1 means directly to the right. The
        value may also be an object created by the stereo module.

        The sound is loaded from samp (which can be a filename, File,
        or Sample object). The pitch is given as a multiple of the
        sound's original frequency; the volume is given as a fraction
        of the sound's original volume. The delay is a time (in seconds)
        to delay before the note is played. The channel, if None or not
        supplied, defaults to the same channel the agent is running in.

        This returns the expected duration of the sound, in seconds.
        """

        if (self.generator is None or self.channel is None):
            raise generator.ScheduleError('scheduler has never been scheduled')
        if (chan is None):
            chan = self.channel
        if (not chan.active):
            raise generator.ChannelError('cannot schedule note to inactive channel')
        gen = self.generator
        samp = sample.get(samp)

        starttime = gen.select_time(delay)
        pan = stereo.cast(pan)
        dur = samp.queue_note(pitch, volume, pan, starttime, chan)
        return float(dur) / float(cboodle.framespersec())

    def sched_note_duration(self, samp, duration, pitch=1.0, volume=1.0,
        delay=0, chan=None):
        """sched_note_duration(sample, duration, pitch=1, volume=1, delay=0,
            chan=self.channel) -> duration
        
        Schedule a note to play, extending the original sound sample to a
        longer period of time. The duration is given in seconds. 

        The sound is loaded from samp (which can be a filename, 
        File, or Sample object). The pitch is given as a multiple of the
        sound's original frequency; the volume is given as a fraction
        of the sound's original volume. The delay is a time (in seconds)
        to delay before the note is played. The channel, if None or not
        supplied, defaults to the same channel the agent is running in.

        This returns the expected duration of the sound, in seconds. Due to
        the way sounds are looped, this may be slightly longer than the
        given duration.
        """

        return self.sched_note_duration_pan(samp, duration, None, pitch, volume, delay, chan)

    def sched_note_duration_pan(self, samp, duration, pan=None, pitch=1.0, volume=1.0, delay=0, chan=None):
        """sched_note_duration_pan(sample, duration, pan=0, pitch=1, volume=1,
            delay=0, chan=self.channel) -> duration

        Schedule a note to play, panning the stereo origin of the sound.
        The pan value defaults to 0, meaning no shift in origin;
        -1 means directly to the left; 1 means directly to the right. The
        value may also be an object created by the stereo module.

        The sound is loaded from samp (which can be a filename, File,
        or Sample object). The pitch is given as a multiple of the
        sound's original frequency; the volume is given as a fraction
        of the sound's original volume. The delay is a time (in seconds)
        to delay before the note is played. The channel, if None or not
        supplied, defaults to the same channel the agent is running in.

        This extends the original sound sample to a longer period of time. 
        The duration is given in seconds. This returns the expected duration 
        of the sound, in seconds. Due to the way sounds are looped, this may 
        be slightly longer than the given duration.
        """

        if (self.generator is None or self.channel is None):
            raise generator.ScheduleError('scheduler has never been scheduled')
        if (chan is None):
            chan = self.channel
        if (not chan.active):
            raise generator.ChannelError('cannot schedule note to inactive channel')
        gen = self.generator
        samp = sample.get(samp)

        starttime = gen.select_time(delay)
        fduration = gen.select_duration(duration)

        pan = stereo.cast(pan)
        dur = samp.queue_note_duration(pitch, volume, pan, starttime, fduration, chan)
        return float(dur) / float(cboodle.framespersec())

    def sched_note_params(self, samp, **args):
        """sched_note_params(sample, param=value, param=value...) -> duration
        
        Schedule a note to play. This method understands all the arguments
        used by the other sched_note methods, but they must be supplied as
        named keywords. The arguments may be in any order.
        For example: "self.sched_note_params(snd, volume=0.5, pitch=2)"

        The valid arguments, and their default values:
            pitch = 1     (original pitch)
            volume = 1    (full volume)
            delay = 0     (play immediately)
            pan = None    (no stereo shift)
            duration = 0  (exactly once through the sound)
            chan = None   (play in agent's own channel)
        """

        duration = args.get('duration', 0.0)
        pan = args.get('pan', None)
        pitch = args.get('pitch', 1.0)
        volume = args.get('volume', 1.0)
        delay = args.get('delay', 0.0)
        chan = args.get('chan', None)
        return self.sched_note_duration_pan(samp, duration, pan, pitch, volume, delay, chan)

    def listen(self, event=None, handle=None, hold=None, chan=None):
        """listen(event=self.selected_event, handle=self.receive, hold=None, 
            chan=self.channel) -> Handler

        Begin listening for events. The event should be a string, or a
        function which returns a string. (If no event is given, the
        agent.selected_event field will be consulted.) The agent will
        listen on the given channel, or (if none is given) on the
        agent's own channel.

        The agent will react whenever a matching event is seen on the
        channel. An event matches if it is equal to the selected event
        string, or begins with it; and if it is in the listening channel,
        or a subchannel of it. (So event "foo.bar" will trigger agents
        listening for event "foo.bar", "foo", or "".)

        When an agent is triggered, its receive() method is run. (If you
        pass a different function as handle, that function will be run.)

        The hold value indicates whether the agent's channel will be kept
        alive for as long as it listens. If this is False/None, the channel
        will follow the usual rule and expire as soon as nothing is scheduled 
        on it. (A listening agent does not automatically count as scheduled!)
        If the listening channel is not the same as the agent's own channel,
        you may pass one of the constants HoldRun or HoldListen, to keep
        just one of them alive. A True value will keep both.

        The listen() method returns a Handler object. You may store this
        for later use; it has a cancel() method which may be used to stop
        listening.
        """
        
        if (not self.inited):
            raise generator.ScheduleError('agent is uninitialized')
        if (self.generator is None or self.channel is None):
            raise generator.ScheduleError('listener has never been scheduled')
        if (chan is None):
            chan = self.channel
        if (not chan.active):
            raise generator.ChannelError('cannot listen to inactive channel')
            
        if (event is None):
            event = self.selected_event
        if (event is None):
            raise generator.ScheduleError('must specify event to listen for')
        if (callable(event)):
            event = event()
            if (event is None):
                raise generator.ScheduleError('must return event to listen for')
        if (event != ''):
            event = boodle.check_prop_name(event)

        if (handle is None):
            handle = self.receive

        gen = self.generator
        han = Handler(self, handle, event, chan, hold)
        gen.addhandler(han)
        
        return han

    def unlisten(self, event=None):
        """unlisten(event=None) -> None

        Stop listening. If no event argument is given, stop listening to
        all events. If an event is given, stop listening for that specific
        event.
        """
        
        if (self.generator is None or self.channel is None):
            raise generator.ScheduleError('listener has never been scheduled')

        if (event is None):
            ls = [ han for han in self.handlers ]
        else:
            event = boodle.check_prop_name(event)
            ls = [ han for han in self.handlers if (han.event == event) ]

        if (not ls):
            return
            
        gen = self.generator
        gen.remhandlers(ls)
        
    def post_listener_agent(self, ag, chan=None, event=None, handle=None, 
        hold=None, listenchan=None):
        """post_listener_agent(agent, chan=self.channel, 
            event=ag.selected_event, handle=ag.receive, hold=None, 
            listenchan=chan)

        Post an agent to listen for events. This is equivalent to 
            sched_agent(ag, handle=ag.listen(...))

        That is, the agent must not currently be scheduled. It runs
        immediately, but only to call its listen() method, with any
        arguments you pass in.
        """

        # Define a closure to call the agent's listen function with the
        # appropriate arguments.
        def func():
            ag.listen(event=event, handle=handle, hold=hold, chan=listenchan)

        self.sched_agent(ag, 0, chan=chan, handle=func)

    def send_event(self, evname, *args, **kwargs):
        """send_event(event, ..., chan=self.channel)

        Send an event. The event consists of the given name, followed by
        zero or more arguments (which may be any Python object). The
        event is sent on the given channel, or (if none given) on the
        agent's own channel.
        """

        chan = kwargs.pop('chan', None)
        if (kwargs):
            raise TypeError('invalid keyword argument for this function')

        if (self.generator is None or self.channel is None):
            raise generator.ScheduleError('sender has never been scheduled')
        if (chan is None):
            chan = self.channel
        if (not chan.active):
            raise generator.ChannelError('cannot send event to inactive channel')
        gen = self.generator

        evname = boodle.check_prop_name(evname)
        ev = (evname,) + args

        gen.sendevent(ev, chan)

    def sched_agent(self, ag, delay=0, chan=None, handle=None):
        """sched_agent(agent, delay=0, chan=self.channel, handle=self.run)

        Schedule an agent to run. This may be the current agent (self) or 
        a newly-created agent. The delay is a time (in seconds) to delay
        before the agent runs. The channel, if None or not supplied,
        defaults to the same channel that self is running in. The agent's
        run() method will be called, unless you specify a different
        handle function.
        """

        if (not isinstance(ag, Agent)):
            raise generator.ScheduleError('not an Agent instance')
        if (not ag.inited):
            raise generator.ScheduleError('agent is uninitialized')
        if (self.generator is None or self.channel is None):
            raise generator.ScheduleError('scheduler has never been scheduled')
        if (chan is None):
            chan = self.channel
        if (not chan.active):
            raise generator.ChannelError('cannot schedule agent to inactive channel')
        if (handle is None):
            handle = ag.run
        gen = self.generator

        starttime = gen.select_time(delay)
        ag.origdelay = delay
        gen.addagent(ag, chan, starttime, handle)

    def resched(self, delay=None, chan=None, handle=None):
        """resched(delay=None, chan=self.channel, handle=self.run)

        Reschedule the current agent (self). The delay is a time (in
        seconds) to delay before the agent runs again. The channel, if
        None or not supplied, defaults to the same channel that self is
        running in.

        If delay is not supplied, it defaults to the delay used when this
        agent was first scheduled. Note that if this value was zero, 
        you will probably cause an infinite loop.

        The agent's run() method will be called, unless you specify a 
        handle different function.
        """

        if (delay is None):
            delay = self.origdelay
            if (delay is None):
                raise generator.ScheduleError('resched with no prior delay')
        self.sched_agent(self, delay, chan, handle)

    def new_channel(self, startvolume=1.0, parent=None):
        """new_channel(startvolume=1, parent=self.channel) -> channel

        Create a new channel. The startvolume is the volume the channel
        is initially set to; this will affect all sounds played in the
        channel and any subchannels. The new channel will be a subchannel
        of parent -- if None or not supplied, it will be a subchannel of
        the channel that the agent (self) is running in.
        """

        if (self.channel is None):
            raise generator.ChannelError('creator is not in a channel')
        if (parent is None):
            parent = self.channel
        chan = generator.Channel(parent, self.generator, self, startvolume, stereo.default())
        return chan

    def new_channel_pan(self, pan=None, startvolume=1.0, parent=None):
        """new_channel_pan(pan=0, startvolume=1, parent=self.channel) -> channel

        Create a new channel, panning the stereo origin of its sounds.
        (See the stereo module.) The startvolume is the volume the channel
        is initially set to; this will affect all sounds played in the
        channel and any subchannels. The new channel will be a subchannel
        of parent -- if None or not supplied, it will be a subchannel of
        the channel that the agent (self) is running in.
        """

        if (self.channel is None):
            raise generator.ChannelError('creator is not in a channel')
        if (parent is None):
            parent = self.channel
        
        pan = stereo.cast(pan)
        chan = generator.Channel(parent, self.generator, self, startvolume, pan)
        return chan

    def get_root_channel(self):
        """get_root_channel() -> channel

        Return the root channel of the channel tree.
        """
        return self.generator.rootchannel

    def get_prop(self, key, default=None):
        """get_prop(key, default=None) -> any

        Get a property from the agent's channel. If none is set, see if 
        one is inherited from the parent. If there is no inherited value 
        either, return None, or the given default.

        Note that None is a legal property value. To distinguish between
        no property and a property set to None, use has_prop().
        """
        return self.channel.get_prop(key, default)
            
    def has_prop(self, key):
        """has_prop(key) -> bool

        See whether the agent's channel has a given property. If none is 
        set, see if one is inherited from the parent.
        """
        return self.channel.has_prop(key)
            
    def set_prop(self, key, val):
        """set_prop(key, val) -> None

        Set a property on the agent's channel.
        """
        return self.channel.set_prop(key, val)
            
    def del_prop(self, key):
        """del_prop(key) -> None

        Delete a property from the agent's channel. If none is set, this 
        has no effect.

        Note that this does not affect parent channels. So get_prop(key)
        may still return a value after del_prop(key).
        """
        return self.channel.del_prop(key)

    def load_described(self, val, wantmodule=False):
        """load_described(val, wantmodule=False) -> Agent or module

        Load a named agent or module. The argument should be a string (or
        list of strings, or sparse Tree) giving a fully qualified name:

            package.name/AgentName
            package.name:version.needed/AgentName
            package.name::exact.version.number/AgentName

        To load an agent with arguments, just append the arguments.

            package.name/AgentName 0.5 2

        Just as on the command line, arguments referring to more agents
        go in parentheses:

            package.name/AgentName (package.name/AnotherAgent 2)

        To get an entire module, pass wantmodule=True. (And leave off the
        "/AgentName" part, and don't use any arguments.)

        This method is not intended for module creation time (loading one
        module which another depends on). It bypasses Boodler's dependency
        tracking. Use this method when your agent is using a user-specified
        value to find an arbitrary Boodler entity.
        """

        loader = self.generator.loader
        return load_described(loader, val, wantmodule)
    
    def init(self):
        """init(...)

        Set the agent up. The arguments are passed along from the 
        constructor call. Each subclass of Agent may override
        this method; if it wants to accept constructor arguments, it
        must override this.
        """
        pass

    def run(self):
        """run()

        Perform the agent's action. Each subclass of Agent must override
        this method.
        """
        raise NotImplementedError('agent has no run() method')

    def receive(self, event):
        """receive(event)

        Perform the agent's action when an appropriate event arrives. 
        Each subclass of Agent which listens for events must override this
        method (or provide an alternative handler).
        
        The event is a tuple, starting with a string, followed (possibly)
        by more values.
        """
        raise NotImplementedError('agent has no receive() method')

    def get_class_name(cla):
        """get_class_name() -> (str, str, bool)

        Return the qualified name of the module, and of the Agent class
        within the module. These strings are intended for logging and
        error messages.

        If the bool return value is true, the module came from the
        package collection; it is a package name (although with no version
        information). If the value is false, the module came from
        sys.path.
        """
        
        res = Agent.cached_class_names.get(cla)
        if (res):
            return res

        # Default value
        res = (cla.__module__, cla.__name__, False)
        
        loader = pload.PackageLoader.global_loader
        if (loader):
            try:
                (pkg, resource) = loader.find_item_resources(cla)
                res = (pkg.name, resource.key, True)
            except:
                pass
            
        Agent.cached_class_names[cla] = res
        return res
            
    get_class_name = classmethod(get_class_name)
    
    def get_argument_list(cla):
        """get_argument_list() -> ArgList

        Return the argument list specification for the class.
        """
        
        res = Agent.cached_argument_lists.get(cla)
        if (not (res is None)):
            return res

        # Default value
        res = None
        nodestr = None
        
        loader = pload.PackageLoader.global_loader
        if (loader):
            try:
                (pkg, resource) = loader.find_item_resources(cla)
                nodestr = resource.get_one('boodler.arguments')
            except:
                pass

        if (nodestr):
            node = sparse.parse(nodestr)
            res = argdef.ArgList.from_node(node)
            
        Agent.cached_argument_lists[cla] = res
        return res
            
    get_argument_list = classmethod(get_argument_list)
    
    def get_title(cla):
        """get_title() -> string

        Return the name of the agent. This normally returns the title
        value from the agent's metadata. (An agent class can override
        this behavior, but there is usually no reason to do so.)
        """

        loader = pload.PackageLoader.global_loader
        if (loader):
            try:
                (pkg, resource) = loader.find_item_resources(cla)
                res = resource.get_one('dc.title')
                if (res):
                    return res
            except:
                pass

        # Default value
        return 'unnamed agent'

    get_title = classmethod(get_title)

# Constants for the hold parameter of Agent.listen()
HoldRun = 'run'
HoldListen = 'listen'
HoldBoth = True
        
class Handler:
    """Handler: Represents the state of one agent listening for one event.

    This is mostly a data object; the generator module uses its fields.
    It does export one method, cancel(), for Agent code to make use of.

    Public methods:

    cancel() -- stop listening

    Internal methods:

    finalize() -- shut down the object
    """

    def __init__(self, ag, func, event, chan, hold):
        self.alive = False
        self.agent = ag
        self.func = func
        self.generator = ag.generator
        self.event = event
        self.listenchannel = chan
        self.runchannel = ag.channel
        self.holdlisten = False
        self.holdrun = False

        if (hold is HoldListen):
            self.holdlisten = True
            hold = None
        if (hold is HoldRun):
            self.holdrun = True
            hold = None
        if (hold):
            self.holdlisten = True
            self.holdrun = True

    def finalize(self):
        """finalize() -> None

        Shut down the Handler object and drop all references.

        This is an internal call. It should only be called by 
        Generator.remhandlers(), and only after the listen has been
        cancelled.
        """

        self.alive = False
        self.agent = None
        self.generator = None
        self.event = None
        self.listenchannel = None
        self.runchannel = None

    def cancel(self):
        """cancel() -> None

        Stop listening. It is safe to call this more than once.
        """

        if (not self.alive):
            return
        self.generator.remhandlers([self])


def load_described(loader, args, wantmodule=False):
    """load_described(loader, val, wantmodule=False) -> module or Agent

    Load a named module or agent. The argument should be a string (or
    list of strings, or sparse Tree) giving a fully qualified name:

        package.name/AgentName
        package.name:version.needed/AgentName
        package.name::exact.version.number/AgentName

    To load an agent with arguments, just append the arguments.

        package.name/AgentName 0.5 2

    Just as on the command line, arguments referring to more agents
    go in parentheses:

        package.name/AgentName (package.name/AnotherAgent 2)

    To get an entire module, pass wantmodule=True. (And leave off the
    "/AgentName" part, and don't use any arguments.)

    This method is not intended for module creation time (loading one
    module which another depends on). It bypasses Boodler's dependency
    tracking.
    """
        
    if (type(args) in [str, unicode]):
        argstr = args
        args = [ '(', args, ')' ]
    elif (type(args) == list):
        argstr = ' '.join(args)
        args = [ '(' ] + args + [ ')' ]
    elif (type(args) == tuple):
        argstr = ' '.join(args)
        args = [ '(' ] + list(args) + [ ')' ]
    elif (isinstance(args, sparse.Tree)):
        argstr = args.serialize()
        # args is fine
    else:
        raise TypeError('args must be a str, list of str, or Tree')

    if (not isinstance(args, sparse.Tree)):
        args = sparse.parse(' '.join(args))

    if (isinstance(args, sparse.ID)):
        args = sparse.List(args)
    if (not isinstance(args, sparse.List)):
        raise ValueError('arguments must be a list')
    if (len(args) == 0):
        # default to the null agent, if none was given
        args = sparse.List(sparse.ID('/boodle.builtin.NullAgent'))
    
    classarg = args[0]
    if (not isinstance(classarg, sparse.ID)):
        raise ValueError('arguments must begin with a class name')

    if (wantmodule):
        ### clumsy!
        mod = loader.load_item_by_name(classarg.as_string()+'/')

        if (type(mod) != types.ModuleType):
            raise TypeError(argstr + ' is not a module')
        if (len(args) > 1):
            raise ValueError('modules cannot have arguments')
        return mod
    
    clas = loader.load_item_by_name(classarg.as_string())

    if (type(clas) != type(Agent)):
        raise TypeError(argstr + ' is not a class')
    if (not issubclass(clas, Agent)):
        raise TypeError(argstr + ' is not an Agent class')

    arglist = clas.get_argument_list()
    if (arglist is None):
        arglist = argdef.ArgList()
    (valls, valdic) = arglist.resolve(args)
    wrapper = argdef.ArgClassWrapper(clas, valls, valdic)
    return wrapper
    
# Late imports.

import boodle
from boodle import generator, sample, stereo
# cboodle may be updated later, by a set_driver() call.
cboodle = boodle.cboodle
from boodle.generator import FrameCount # imported for users to see

from boopak import version, pload, pinfo, sparse, argdef

argdef.Agent = Agent
argdef.load_described = load_described
