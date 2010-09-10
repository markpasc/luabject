import functools
import inspect
import logging
import sys

from eventlet import api


class Message(object):

    """A message "spoken" by a Thing for other Things to "hear"."""

    def __init__(self, speaker, text):
        assert isinstance(speaker, Thing)
        assert text is not None
        self.speaker = speaker
        self.text = text


class Null(object):

    """Stub replacement for a Thing that doesn't exist."""

    def __new__(cls):
        try:
            return cls.instance
        except AttributeError:
            cls.instance = super(Null, cls).__new__(cls)
            return cls.instance

    def __getattr__(self, name):
        return self

    def __call__(self, *args, **kwargs):
        pass


class TargetError(Exception):

    """Error thrown when an object cannot be found using the `Thing.find()`
    method."""

    pass


class Thing(object):

    def __init__(self, parent):
        assert parent is not None
        parent.add(self)
        self.contents = set()

    def _get_name(self):
        try:
            return self.__dict__['name']
        except KeyError:
            return repr(self)

    def _set_name(self, value):
        self.__dict__['name'] = value

    name = property(_get_name, _set_name)
    """The human readable name for this Thing, by which it can be found in its
    environment."""

    def add(self, obj):
        """Adds `obj` to this Thing's contents.

        When added to this Thing, `obj` is removed from its existing parent,
        if it has one.

        """
        self.contents.add(obj)
        parent = getattr(obj, 'parent', None)
        obj.parent = self
        if parent is not None:
            parent.remove(obj)

    def remove(self, obj):
        """Removes `obj` from this Thing's contents.

        The `obj` Thing is not reparented anywhere. Making it continue to be
        available in the object hierarchy is up to you.

        """
        if obj.parent is self:
            return
        self.contents.remove(obj)

    def hear(self, message):
        """Gives this Thing the Message `message` to "hear."

        In this implementation, the message is repropagated to all this
        Thing's contents (so a Thing's contents all "hear" a message the Thing
        "hears").

        """
        for child in iter(self.contents):
            child.hear(message)

    def find_inside(self, target):
        """Returns the item or a list of items in this Thing's contents the
        names of which contain the string `target`."""
        items = [child for child in iter(self.contents)
            if target in child.name]
        if not items:
            raise TargetError('No such contents %r' % target)
        if len(items) == 1:
            return items[0]
        return items

    def find(self, target):
        """Returns the item or list of items somewhere around this Thing the
        names of which contain the string `target`.

        Matching items this Thing contains are returned first; if none match,
        matching sibling Things inside this Thing's parent are returned (if
        any). If `target` is either of the special strings `"me"` or `"here"`,
        this Thing itself or its parent respectively are returned.

        """
        norm_target = target.strip().lower()
        if norm_target == 'me':
            return self
        if norm_target == 'here':
            return self.parent

        try:
            return self.find_inside(target)
        except TargetError:
            pass

        return self.parent.find_inside(target)


class Avatar(Thing):

    """A Thing with a network connection to an external animating construct
    (such as a real human player)."""

    def __init__(self, conn, parent):
        super(Avatar, self).__init__(parent)

        self.conn = conn
        self.writer = conn.makefile('w')
        self.reader = conn.makefile('r')

    def hear(self, message):
        """Gives this Avatar the Message `message` to "hear."

        This implementation prints the message to the remote user over the
        wire.

        """
        super(Avatar, self).hear(message)
        self.write('%s says, "%s"', message.speaker.name, message.text)

    def unknown_command(self, cmd, *args):
        self.write("Oops, no such command %r.", cmd)

    def operate(self):
        """Serve the player's input line by line until they disconnect."""
        line = self.reader.readline()
        while line:
            lineparts = line.strip().split(None, 1)
            cmd = lineparts.pop(0)

            try:
                handler = getattr(self, 'do_' + cmd)
            except AttributeError:
                self.unknown_command(cmd)
            else:
                # Resplit according to how many args there are.
                funcargs, varargs, varkw, defaults = inspect.getargspec(handler)
                logging.debug('Handler %r takes %d args %r', handler, len(funcargs), funcargs)
                args = line.strip().split(None, len(funcargs) - 1)  # ignore self
                args.pop(0)  # ignore cmd

                try:
                    handler(*args)
                except Exception, exc:
                    exc_type = type(exc).__name__
                    self.write("Oops, %s: %s.", exc_type, str(exc))
                    logging.error('Oops, %s handling command %r', exc_type, line)
                    logging.exception(exc)

            line = self.reader.readline()

    def do_say(self, text):
        """Send the player's message to other objects in its parent when the
        player uses the "say" command."""
        m = Message(self, text)
        self.parent.hear(m)

    def do_name(self, name):
        """Change this Avatar's name when the player uses the "name"
        command."""
        self.name = name

    def do_look(self, target=None):
        """Show the player the target object's `description` attribute when
        the player uses the "look" command."""
        if target is None:
            target = 'here'

        target_obj = self.find(target)
        self.write(target_obj.description)

    def do_set(self, target, property, value):
        """Set the target object's property `property` to the value `value`
        when the player uses the "set" command."""
        target_obj = self.find(target)
        # TODO: confirm that the actor has permissions on that obj
        setattr(target_obj, property, value)
        self.write('Set.')

    def write(self, line, *args):
        """Print `line` to the player.

        Extra arguments, if provided, are formatted into `line` first.

        """
        if args:
            line = line % args
        wr = self.writer
        wr.write(line)
        wr.write('\r\n')
        wr.flush()


class Server(object):

    """A world server hosting a hierarchy and a set of connections."""

    def __init__(self):
        self.room = Thing(Null())

    def host(self):
        server = api.tcp_listener(('0.0.0.0', 3000))
        while True:
            logging.info('Waiting for connection')
            conn, addr = server.accept()
            logging.info('Somebody from %r connected', addr)

            api.spawn(Avatar(conn, self.room).operate)


def main(argv=None):
    logging.basicConfig(level=logging.DEBUG)

    try:
        Server().host()
    except KeyboardInterrupt:
        logging.info('Terminating')

    return 0


if __name__ == '__main__':
    sys.exit(main())
