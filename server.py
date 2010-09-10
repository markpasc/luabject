import functools
import inspect
import logging
import sys

from eventlet import api


class Message(object):

    def __init__(self, speaker, text):
        assert isinstance(speaker, Thing)
        assert text is not None
        self.speaker = speaker
        self.text = text


class Null(object):

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

    def add(self, obj):
        self.contents.add(obj)
        parent = getattr(obj, 'parent', None)
        obj.parent = self
        if parent is not None:
            parent.remove(obj)

    def remove(self, obj):
        if obj.parent is self:
            return
        self.contents.remove(obj)

    def hear(self, message):
        for child in iter(self.contents):
            child.hear(message)

    def find_inside(self, target):
        items = [child for child in iter(self.contents)
            if target in child.name]
        if not items:
            raise TargetError('No such contents %r' % target)
        if len(items) == 1:
            return items[0]
        return items

    def find(self, target):
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

    def __init__(self, conn, parent):
        super(Avatar, self).__init__(parent)

        self.conn = conn
        self.writer = conn.makefile('w')
        self.reader = conn.makefile('r')

    def hear(self, message):
        super(Avatar, self).hear(message)
        self.write('%s says, "%s"', message.speaker.name, message.text)

    def unknown_command(self, cmd, *args):
        self.write("Oops, no such command %r.", cmd)

    def operate(self):
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
        m = Message(self, text)
        self.parent.hear(m)

    def do_name(self, name):
        self.name = name

    def do_look(self, target=None):
        if target is None:
            target = 'here'

        target_obj = self.find(target)
        self.write(target_obj.description)

    def write(self, line, *args):
        if args:
            line = line % args
        wr = self.writer
        wr.write(line)
        wr.write('\r\n')
        wr.flush()


class Server(object):

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
