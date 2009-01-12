# Boodler: a programmable soundscape tool
# Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
#   <http://boodler.org/>
# This program is distributed under the LGPL.
# See the LGPL document, or the above URL, for details.

"""sparse: A module which implements simple S-expressions.

An S-expression is a string, or a parenthesized list of S-expressions.
In other words, good old Lisp-style expressions. This implementation
also allows named elements in lists (as well as the usual positional
elements).

The following are valid S-expressions:

  string
  ()
  (string)
  (one two three)
  (key=value key2=value2)
  (list (containing a list) and ((another)))
  (one two named=(inner (list) ()))

A string can containing special characters -- whitespace, quotes, equals,
parentheses -- if it is quoted. Single or double quotes can be used.
Inside a quoted string, quotes and backslashes should be escaped with
a backslash. So the following are also valid:

  "quote \" mark"
  'single quote \' mark'
  "smiley =o) clown"

Note that these three expressions are identical:

  string
  "string"
  'string'

However, the following are not identical:

  (string)
  "(string)"

The former is a list containing one string; the latter is a string.

This module lets you convert the textual representation of an expression
into a structured representation -- a tree of Tree objects. (The subclasses
of Tree are List and ID, representing lists and strings.)

Classes:

Tree -- represents an S-expression
List -- subclass which represents a list expression
ID -- subclass which represents a string expression

Public functions:

parse() -- parse a string which contains exactly one S-expression

Internal classes:

AttrToken -- represents a named value encountered during parsing
ParseContext -- represents the state of an ongoing parse() operation
"""

import StringIO
import codecs

escaper = codecs.getencoder('unicode_escape')

class ParseError(Exception):
    """ParseError: represents an error parsing string data into Trees.
    """
    pass

class Tree:
    """Tree: represents an S-expression.

    This is a virtual base class. Do not instantiate it; instead use
    the List or ID class.
    """
    
    def serialize(self):
        """serialize() -> str or unicode

        Convert this tree into its textual representation. Strings will
        be quoted and escaped if necessary.
        """
        return '<Tree: unimplemented>'
    
    def __repr__(self):
        val = self.serialize()
        if (type(val) == unicode):
            (val, dummy) = escaper(val)
        return val

    def as_string(self):
        """as_string() -> str or unicode

        Get the string which this tree represents. (The result is not
        quoted or escaped; it is the underlying string value.)

        Raises ValueError if called on a List.
        """
        raise ValueError('a list cannot be understood as a string')

    def as_integer(self):
        """as_integer() -> int or long

        Get the integer value which this tree represents.

        Raises ValueError if called on a List, or on a string which
        is not interpretable as an integer.
        """
        raise ValueError('a list cannot be understood as a number')

    def as_float(self):
        """as_float() -> float

        Get the float value which this tree represents.

        Raises ValueError if called on a List, or on a string which
        is not interpretable as a float.
        """
        raise ValueError('a list cannot be understood as a number')

    def as_boolean(self):
        """as_boolean() -> bool

        Get the boolean value which this tree represents. The empty
        string is considered false, as are '0', 'no', or 'false'. Or
        really any string beginning with '0', 'n', 'N', 'f', or 'F'.
        Anything else is true.

        Raises ValueError if called on a List.
        """
        raise ValueError('a list cannot be understood as a boolean')

class List(Tree):
    """List: represents a list expression.

    A list can contain positional entries and named values; it therefore
    acts as both an array and a dict.

    Array-style operations:

        len(l)
        l[int]
        l[int:int]
        l.append(tree)

    Dict-style operations:

        l.has_attr(key)
        l.get_attr(key)
        l.set_attr(key, tree)

    (The keys in these operations must be strings.)

    Positional (array) values and named (dict) values are separate. If l
    has no positional values, len(l) is zero, no matter how many named
    values it has. Contrariwise, l.get_attr() will never retrieve a
    positional value.

        List(val, val, ... key=val, key=val) -- constructor

    Construct a List with the given named and/or positional values. All
    values must be Trees. You can also construct a List from a Python
    list or dict, using the forms List(*list) or List(**dict).
    """
    
    def __init__(self, *args, **attrs):
        self.list = list(args)
        self.attrs = dict(attrs)
        for val in self.list:
            if (not isinstance(val, Tree)):
                raise ValueError('List may only contain Lists and IDs')
        for val in self.attrs.values():
            if (not isinstance(val, Tree)):
                raise ValueError('List attribute must be List or ID')

    def append(self, val):
        """append(val) -> None

        Add the Tree as the last positional entry.
        """
        if (not isinstance(val, Tree)):
            raise ValueError('List may only contain Lists and IDs')
        self.list.append(val)

    def set_attr(self, key, val):
        """set_attr(key, val) -> None

        Add the Tree val as a named entry, with the given key.
        """
        if (not isinstance(val, Tree)):
            raise ValueError('List attribute must be List or ID')
        if (not (type(key) in [str, unicode])):
            raise ValueError('List attribute key must be a string')
        self.attrs[key] = val

    def get_attr(self, key):
        """get_attr(key) -> Tree

        Retrieve the named Tree which has the given key. If there is
        no entry with that key, returns None.
        """
        return self.attrs.get(key)
        
    def has_attr(self, key):
        """has_attr(key) -> bool

        Returns whether there is an entry with the given key.
        """
        return self.attrs.has_key(key)
        
    def serialize(self):
        ls = [ val.serialize() for val in self.list ]
        ls = ls + [ key+'='+(self.attrs[key].serialize())
            for key in self.attrs ]
        return '(' + ' '.join(ls) + ')'

    def __len__(self):
        return len(self.list)

    def __getitem__(self, key):
        return self.list.__getitem__(key)
        
    def __contains__(self, it):
        return self.list.__contains__(it)
        
    def __iter__(self):
        return self.list.__iter__()
        

class ID(Tree):
    """ID: represents a string expression.

        ID(val) -- constructor

    The value that you pass to the constructor may be str or unicode.
    It becomes the ID's underlying string value, so it should not be
    quoted or escaped.

    For any str or unicode val,

        ID(val).as_string() == val
    """
    
    def __init__(self, id):
        if (not (type(id) in [str, unicode])):
            raise ValueError('ID must contain a string')
        self.id = id
        self.delimiter = None
        self.escape = False

        if (not id):
            self.delimiter = '"'
        for ch in id:
            if (ch.isspace() or ch in ['=', '"', "'", '(', ')', '\\']):
                self.delimiter = '"'
                break

        if (self.delimiter):
            if ('"' in id):
                if ("'" in id):
                    self.escape = True
                else:
                    self.delimiter = "'"
        
        if ('\\' in id):
            self.escape = True

    def serialize(self):
        if (self.delimiter):
            val = self.id
            if (self.escape):
                val = val.replace('\\', '\\\\')
                val = val.replace(self.delimiter, '\\'+self.delimiter)
            return (self.delimiter + val + self.delimiter)
        else:
            return self.id
        
    def __len__(self):
        return len(self.id)
        
    def __cmp__(self, other):
        if (isinstance(other, ID)):
            other = other.id
        return cmp(self.id, other)

    def as_string(self):
        return self.id

    def as_integer(self):
        return int(self.id)

    def as_float(self):
        return float(self.id)

    def as_boolean(self):
        val = self.id.lower()
        if (not val):
            return False
        val = val[0]
        if (val in ['0', 'n', 'f']):
            return False
        return True

# EndOfList is used as an internal token during parsing. It should not be
# used outside this module.
EndOfList = object()

class AttrToken:
    """AttrToken: represents a named value encountered during parsing.

    This is an internal class; it should not be used outside this module.
    """
    def __init__(self, key):
        self.key = key

def parse(val):
    """parse(val) -> Tree

    Parse a str or unicode value which contains *exactly one* S-expression.
    The value must contain one string (possibly quoted), or one parenthesized
    list. If the expression is ill-formed (unbalanced parentheses or quotes),
    this raises ParseError.

    Whitespace before or after the expression is ignored. Inside a list,
    whitespace separates expressions, but the amount is not significant.

    Note that parse('') raises ParseError, because it does not contain any
    expression.
    """
    
    fl = StringIO.StringIO(val)
    context = ParseContext(fl)
    try:
        res = context.parsetree()
        if (res is EndOfList):
            raise ParseError('unexpected end of list)')
        if (isinstance(res, AttrToken)):
            raise ParseError('attributes may only occur in lists')
        context.finalwhite()
        return res
    finally:
        context.close()

class ParseContext:
    """ParseContext: represents the state of an ongoing parse() operation.

    Parsing S-expressions is quite simple; we only need a stream of
    characters and the ability to look ahead by one. (Or, if you like,
    the ability to push one character back onto the stream.)

    Fields:

        fl -- a file-like object, from which characters are read.
        nextch -- if a character has been pushed back, it is here;
            if not, this is None.

    Constructor:

        ParseContext(fl) -- constructor
    """
    
    def __init__(self, fl):
        self.fl = fl
        self.nextch = None

    def close(self):
        """close() -> None

        Shut down the parser, and close the underlying stream.
        """
        self.fl.close()

    def finalwhite(self):
        """finalwhite() -> None

        Ensure that there are no more expressions in the stream. Trailing
        whitespace is ignored.

        Raises ParseError on failure.
        """
        
        ch = self.nextch
        fl = self.fl

        if (ch is None):
            ch = fl.read(1)

        while (ch and ch.isspace()):
            ch = fl.read(1)
        
        if (ch):
            raise ParseError('extra stuff after value')

    def parsetree(self):
        """parsetree() -> Tree or EndOfList or AttrToken

        Parse one expression from the stream, and return the Tree that
        represents it. Leading whitespace is ignored.

        EndOfList indicates that a closing parenthesis has been
        reached; an AttrToken instance indicates a named value such
        as x=y. These are not valid expressions on their own; they can
        only occur inside lists.
        """
        
        ch = self.nextch
        fl = self.fl

        if (ch is None):
            ch = fl.read(1)

        while (ch and ch.isspace()):
            ch = fl.read(1)

        if (not ch):
            raise ParseError('unexpected end of input')
        
        if (ch == '('):
            self.nextch = None
            return self.parselist()

        if (ch == ')'):
            self.nextch = None
            return EndOfList

        if (ch in ['"', "'"]):
            self.nextch = ch
            return self.parsestring()

        if (True):
            self.nextch = ch
            return self.parseid()

    def parseid(self):
        """parseid() -> ID or AttrToken

        Parse an unquoted string expression. The stream must be at the
        beginning of the expression.
        """
        
        ch = self.nextch
        fl = self.fl

        if (ch is None):
            raise Exception('internal error: lookahead char missing')
        
        idfl = StringIO.StringIO()
        while (ch and not (ch in ['=', '"', "'", '(', ')', '\\'])
            and not ch.isspace()):
            idfl.write(ch)
            ch = fl.read(1)
        self.nextch = ch

        st = idfl.getvalue()

        if (ch == '='):
            self.nextch = None
            return AttrToken(st)
        if (ch == '\\'):
            raise ParseError('backslash is only valid inside a quoted string')
        return ID(st)

    def parsestring(self):
        """parsestring() -> ID

        Parse an quoted string expression. The stream must be at the
        beginning of the expression, before the initial quote.
        """

        terminator = self.nextch
        self.nextch = None
        
        fl = self.fl
        ch = fl.read(1)
        
        idfl = StringIO.StringIO()
        while True:
            if (not ch):
                raise ParseError('unterminated string literal')
            if (ch == terminator):
                break
            if (ch == '\\'):
                ch = fl.read(1)
                if (not (ch in ['"', "'", '\\'])):
                    raise ParseError('backslash must be followed by quote or backslash')
            idfl.write(ch)
            ch = fl.read(1)

        self.nextch = None
        st = idfl.getvalue()
        return ID(st)

    def parselist(self):
        """parselist() -> List

        Parse a parenthesized list expression. The stream must be at
        the beginning of the list contents, after the open parenthesis.
        """
        
        if (not (self.nextch is None)):
            raise Exception('internal error: lookahead char')
        
        nod = List()
        while True:
            val = self.parsetree()
            if (val is EndOfList):
                break
            if (isinstance(val, AttrToken)):
                key = val.key
                if (not key):
                    if (len(nod) == 0):
                        raise ParseError('= must be preceded by a key')
                    key = nod.list.pop()
                    if (not isinstance(key, ID)):
                        raise ParseError('= may not be preceded by a list')
                    key = key.id
                val = self.parseattr()
                nod.set_attr(key, val)
                continue
            nod.append(val)

        return nod

    def parseattr(self):
        """parseattr() -> Tree

        Parse the value part of a named value. The stream must be after
        the equals sign.
        """
        
        val = self.parsetree()
        if (val is EndOfList):
            raise ParseError('attribute must have a value')
        if (isinstance(val, AttrToken)):
            raise ParseError('attribute may not contain another =')
        return val
