import functools
import inspect
import logging
import sys

import argparse
import eventlet
from pymongo import Connection

from village.luabject import Luabject


log = logging.getLogger(__name__)


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

    def _del_name(self):
        try:
            del self.__dict__['name']
        except KeyError:
            pass

    name = property(_get_name, _set_name, _del_name)
    """The human readable name for this Thing, by which it can be found in its
    environment."""

    def _get_luacode(self):
        return self.__dict__['luacode']

    def _set_luacode(self, value):
        self.__dict__['luacode'] = value

        def say():
            m = Message(self, 'HI!')
            self.parent.hear(m)

        self.lua = Luabject()
        self.lua.register_global('say', say)
        self.lua.load_script(value)

    def _del_luacode(self):
        del self.__dict__['luacode']
        del self.lua

    luacode = property(_get_luacode, _set_luacode, _del_luacode)

    def as_dict(self):
        data = dict()
        for k, v in self.__dict__.items():
            if isinstance(v, Thing):
                if not hasattr(v, '_id'):
                    raise ValueError("Cannot serialize %r to dictionary with an unsaved %r in its %r attribute"
                        % (self, v, k))
                data[k] = v._id
            else:
                data[k] = v
        del data['contents']
        return data

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

    def touched(self, toucher):
        try:
            lua = self.lua
        except AttributeError:
            pass
        else:
            self.lua.run('touched')

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

    def as_dict(self):
        data = super(Avatar, self).as_dict()
        del data['conn']
        del data['writer']
        del data['reader']
        return data

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
        if isinstance(target_obj, list):
            self.write('Which %r? %s?', target, ' or '.join(thing.name for thing in target_obj))
            return
        self.write(target_obj.description)

    def do_set(self, target, property, value):
        """Set the target object's property `property` to the value `value`
        when the player uses the "set" command."""
        target_obj = self.find(target)
        # TODO: confirm that the actor has permissions on that obj
        setattr(target_obj, property, value)
        self.write('Set.')

    def do_make(self, name):
        th = Thing(self)
        th.name = name
        self.write('Created %s.', name)

    def do_inventory(self):
        if not self.contents:
            self.write("You aren't carrying anything.")
            return

        self.write('You are carrying: %s', ', '.join(thing.name for thing in self.contents))

    def do_give(self, thingname, targetname):
        try:
            thing = self.find_inside(thingname)
        except TargetError:
            self.write("You aren't carrying a %r.", thingname)
            return
        if isinstance(thing, list):
            self.write("Which %r? %s?", thingname, ' or '.join(th.name for th in thing))
            return

        try:
            target = self.find(targetname)
            if isinstance(target, list):
                target = [t for t in target if isinstance(t, Avatar)]
                if not target:
                    raise TargetError()
                if len(target) > 1:
                    self.write("Which %r? %s?", targetname, ' or '.join(t.name for t in target))
                    return
                target = target[0]
            if not isinstance(target, Avatar):
                raise TargetError()
        except TargetError:
            self.write("There isn't a %r here.", targetname)
            return

        target.add(thing)
        self.write('You give your %s to %s.', thing.name, target.name)
        target.write('%s gives their %s to you.', self.name, thing.name)

    def do_drop(self, name):
        try:
            thing = self.find_inside(name)
        except TargetError:
            self.write("You aren't carrying a %r.", name)
            return

        if isinstance(thing, list):
            self.write("Which %r? %s?", name, ' or '.join(t.name for t in thing))
            return

        self.parent.add(thing)
        self.write('You drop your %s.', thing.name)

    def do_take(self, name):
        try:
            thing = self.parent.find_inside(name)
        except TargetError:
            self.write("There isn't a %r here to take.", name)
            return

        if isinstance(thing, list):
            self.write("Which %r? %s?", name, ' or '.join(t.name for t in thing))
            return

        self.add(thing)
        self.write('You take the %s.', thing.name)

    def do_touch(self, name):
        try:
            thing = self.parent.find_inside(name)
        except TargetError:
            self.write("There isn't a %r here to take.", name)
            return

        if isinstance(thing, list):
            self.write("Which %r? %s?", name, ' or '.join(t.name for t in thing))
            return

        thing.touched(self)

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

    def __init__(self, dburi):
        conn = Connection(dburi) if dburi is not None else Connection()
        self.db = conn.village

    def create_world(self):
        self.db.objects.drop()

        self.root = Thing(Null())
        self.root.name = 'Here'
        self.root._is_root = True

        self.save_world()
        log.info('Saved new empty database')

    def load_world(self):
        log.info('Loading database')

        all_objs = dict()
        for obj in self.db.objects.find():
            thing = all_objs.get(obj['_id'], Thing(Null()))
            thing.__dict__.update(obj)

            all_objs[thing._id] = thing

            try:
                parent = thing.parent
            except AttributeError:
                self.root = thing
            else:
                if parent not in all_objs:
                    all_objs[parent] = Thing(Null())
                parentobj = all_objs[parent]
                thing.parent = parentobj
                parentobj.contents.add(thing)

        assert hasattr(self, 'root')
        log.info('Loaded database')

    def save_world(self):
        log.info('Saving database')

        def nextthing(thing):
            things = [thing]
            to_ask = []

            while things:
                for thing in things:
                    to_ask.append(thing)
                    yield thing
                things = []
                while to_ask and not things:
                    next_ask = to_ask.pop(0)
                    try:
                        childs = next_ask.contents
                    except AttributeError:
                        pass
                    else:
                        things = childs

        for thing in nextthing(self.root):
            log.debug('Inserting obj %r with _id %s', thing, getattr(thing, '_id', None))
            thingid = self.db.objects.insert(thing.as_dict())
            thing._id = thingid

        log.info('Database saved')

    def host(self):
        log.info('Starting to serve')

        server = eventlet.listen(('0.0.0.0', 3000))
        while True:
            logging.info('Waiting for connection')
            conn, addr = server.accept()
            logging.info('Somebody from %r connected', addr)

            eventlet.spawn(Avatar(conn, self.root).operate)


def main(argv):
    parser = argparse.ArgumentParser(description="Runs a village world server")
    parser.add_argument('-v', dest='verbosity', action='append_const', const=1,
        help='Be more verbose (stackable)', default=[3])
    parser.add_argument('-q', dest='verbosity', action='append_const', const=-1,
        help='Be less verbose (stackable)')

    parser.add_argument('--db', metavar='URI',
        help='The hostname and/or port where the database server is listening')

    parser.add_argument('--createdb', action='store_true',
        help='Create a database instead of starting up')

    args = parser.parse_args(argv)

    verbosity = sum(args.verbosity)
    verbosity = 0 if verbosity < 0 else verbosity if verbosity < 4 else 4
    log_level = [logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG][verbosity]
    logging.basicConfig(level=log_level,
        format='%(asctime)s %(levelname)-8s %(name)-15s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')

    if args.db is not None and not args.db.startswith('mongodb://'):
        args.db = 'mongodb://%s' % args.db
    log.debug('Expecting database at %s', args.db)

    serv = Server(args.db)

    if args.createdb:
        serv.create_world()
        return 0

    serv.load_world()
    try:
        serv.host()
    except KeyboardInterrupt:
        print
        serv.save_world()
        log.info('Terminating')

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
