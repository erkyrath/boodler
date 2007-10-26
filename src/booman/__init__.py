__all__ = [
	'token', 'command', 'frame', 'create'
]

# A few utility definitions, which will be used by several of the
# booman.* modules

class CommandError(Exception):
	"""CommandError: represents a failure in command processing which
	should be reported to the user.

	(All exceptions are caught, but CommandErrors are those which are
	printed as simple messages.)
	"""
	pass

class CommandCancelled(CommandError):
	"""CommandCancelled: represents a command which was interrupted by
	an empty input at a prompt.
	"""
	def __init__(self, msg='<cancelled>'):
		CommandError.__init__(self, msg)

