#!/usr/bin/env python2
# -*- coding: utf-8 -*-

#**************************************************************************************************#
#                               PYUTILS - SOME PYTHON UTILITY FUNCTIONS
#
#   Description : Toolbox for Python scripts
#   Authors     : David Fischer
#   Contact     : david.fischer.ch@gmail.com
#   Copyright   : 2013-2013 David Fischer. All rights reserved.
#**************************************************************************************************#
#
#  This file is part of pyutils.
#
#  This project is free software: you can redistribute it and/or modify it under the terms of the
#  GNU General Public License as published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This project is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License along with this project.
#  If not, see <http://www.gnu.org/licenses/>
#
#  Retrieved from:
#    git clone https://github.com/davidfischer-ch/pyutils.git
#

import hashlib, inspect, json, logging, logging.handlers, os, re, shlex, subprocess, sys, uuid
from bson.json_util import dumps, loads
from datetime import datetime
from ipaddr import IPAddress


class ForbiddenError(Exception):
    pass

# --------------------------------------------------------------------------------------------------


def cmd(command, input=None, cli_input=None, fail=True, log=None):
    u"""
    Calls the ``command`` and returns a dictionary with stdout, stderr, and the returncode.

    * Pipe some content to the command with ``input``.
    * Answer to interactive CLI questions with ``cli_input``.
    * Set ``fail`` to False to avoid the exception ``subprocess.CalledProcessError``.
    * Set ``log`` to a method to log / print details about what is executed / any failure.

    **Example usage**:

    >>> def print_it(str):
    ...     print('[DEBUG] %s' % str)
    >>> print(cmd(['echo', 'it seem to work'], log=print_it)['stdout'])
    [DEBUG] Execute ['echo', 'it seem to work']
    it seem to work
    <BLANKLINE>

    >>> assert(cmd('cat missing_file', fail=False, log=print_it)['returncode'] != 0)
    [DEBUG] Execute cat missing_file
    >>> cmd('my.funny.missing.script.sh')
    Traceback (most recent call last):
    ...
    OSError: [Errno 2] No such file or directory

    >>> result = cmd('cat pyutils.py')
    >>> print(result['stdout'].splitlines()[0])
    #!/usr/bin/env python2
    """
    if log is not None:
        log('Execute %s%s%s' % ('' if input is None else 'echo %s | ' % repr(input), command,
            '' if cli_input is None else ' < %s' % repr(cli_input)))
    args = command
    if isinstance(command, str):
        args = shlex.split(command)
    process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    if cli_input is not None:
        process.stdin.write(cli_input)
    stdout, stderr = process.communicate(input=input)
    result = {'stdout': stdout, 'stderr': stderr, 'returncode': process.returncode}
    if fail and process.returncode != 0:
        if log is not None:
            log(result)
        raise subprocess.CalledProcessError(process.returncode, command, stderr)
    return result

# --------------------------------------------------------------------------------------------------


def rsync(source, destination, makedest=False, archive=True, delete=False, exclude_vcs=False,
          progress=False, recursive=False, simulate=False, excludes=None, includes=None, fail=True,
          log=None):
    if makedest and not os.path.exists(destination):
        os.makedirs(destination)
    source = os.path.normpath(source) + (os.sep if os.path.isdir(source) else '')
    destination = os.path.normpath(destination) + (os.sep if os.path.isdir(destination) else '')
    command = ['rsync',
               '-a' if archive else None,
               '--delete' if delete else None,
               '--progress' if progress else None,
               '-r' if recursive else None,
               '--dry-run' if simulate else None]
    if excludes is not None:
        command.extend(['--exclude=%s' % e for e in excludes])
    if includes is not None:
        command.extend(['--include=%s' % i for i in includes])
    if exclude_vcs:
        command.extend(['--exclude=.svn', '--exclude=.git'])
    command.extend([source, destination])
    return cmd(filter(None, command), fail=fail, log=log)

# --------------------------------------------------------------------------------------------------


def githash(data):
    u"""
    Return the blob of some data.

    This is how Git calculates the SHA1 for a file (or, in Git terms, a "blob")::

        sha1("blob " + filesize + "\0" + data)

    .. seealso::

        http://stackoverflow.com/questions/552659/assigning-git-sha1s-without-git

    **Example usage**

    >>> print(githash(''))
    e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
    >>> print(githash('give me some hash please'))
    abdd1818289725c072eff0f5ce185457679650be
    """
    s = hashlib.sha1()
    s.update("blob %u\0" % len(data))
    s.update(data)
    return s.hexdigest()


# --------------------------------------------------------------------------------------------------


def datetime_now(offset=None, format='%Y-%m-%d %H:%M:%S'):
    u"""
    Return the current UTC date and time.
    If format is not None, the date will be returned in a formatted string.

    :param offset: Offset added to datetime.utcnow() if set
    :type offset: datetime.timedelta
    :param format: Output date string formatting
    :type format: str

    **Example usage**:

    >>> from datetime import timedelta
    >>> now = datetime_now(format=None)
    >>> future = datetime_now(offset=timedelta(hours=2, minutes=10), format=None)
    >>> print future - now  # doctest: +ELLIPSIS
    2:10:00...
    >>> assert(isinstance(datetime_now(), str))
    """
    now = datetime.utcnow()
    if offset:
        now += offset
    return now.strftime(format) if format else now


def duration2secs(duration):
    u"""
    Returns the duration converted in seconds.

    **Example usage**:

    >>> duration2secs('00:10:00')
    600.0
    >>> duration2secs('01:54:17')
    6857.0
    >>> duration2secs('16.40')
    16.4
    """
    try:
        hours, minutes, seconds = duration.split(':')
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except ValueError:
        return float(duration)


def str2datetime(date, format='%Y-%m-%d %H:%M:%S'):
    return datetime.strptime(date, format)

# --------------------------------------------------------------------------------------------------


## http://stackoverflow.com/questions/6255387/mongodb-object-serialized-as-json
class SmartJSONEncoderV1(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return super(SmartJSONEncoderV1, self).default(obj)


class SmartJSONEncoderV2(json.JSONEncoder):
    def default(self, obj):
        attributes = {}
        for a in inspect.getmembers(obj):
            if inspect.isroutine(a[1]) or inspect.isbuiltin(a[1]) or a[0].startswith('__'):
                continue
            attributes[a[0]] = a[1]
        return attributes


def json2object(json, something):
    something.__dict__.update(loads(json))


def jsonfile2object(filename_or_file, something=None):
    if something is None:
        try:
            return json.load(open(filename_or_file))
        except TypeError:
            return json.load(filename_or_file)
    else:
        try:
            something.__dict__.update(json.load(open(filename_or_file)))
        except TypeError:
            something.__dict__.update(json.load(filename_or_file))


def object2json(something, include_properties):
    if not include_properties:
        return dumps(something, cls=SmartJSONEncoderV1)
    else:
        return dumps(something, cls=SmartJSONEncoderV2)

# --------------------------------------------------------------------------------------------------


def valid_filename(filename):
    u"""
    Returns True if ``filename`` is a valid filename.

    **Example usage**:

    >>> valid_filename('my_file_without_extension')
    False
    >>> valid_filename('my_file_with_extension.mp4')
    True
    """
    try:
        return True if re.match(r'[^\.]+\.[^\.]+', filename) else False
    except:
        return False


def valid_ip(ip):
    u"""
    Returns True if ``ip`` is a valid IP address.

    **Example usage**:

    >>> valid_ip('123.0.0.')
    False
    >>> valid_ip('239.232.0.222')
    True
    """
    try:
        IPAddress(ip)
        return True
    except:
        return False


def valid_mail(mail):
    u"""
    Returns True if ``mail`` is a valid e-mail address.

    **Example usage**:

    >>> valid_mail('Tabby@croquetes')
    False
    >>> valid_mail('Tabby@bernex.ch')
    True
    """
    try:
        return True if re.match(r'[^@]+@[^@]+\.[^@]+', mail) else False
    except:
        return False


def valid_port(port):
    u"""
    Returns True if ``port`` is a valid port.

    **Example usage**:

    >>> assert(not valid_port(-1))
    >>> assert(not valid_port('something not a port'))
    >>> assert(valid_port('80'))
    >>> valid_port(65535)
    True
    """
    try:
        return 0 <= int(port) < 2**16
    except:
        return False


def valid_secret(secret, none_allowed):
    u"""
    Returns True if ``secret`` is a valid secret.

    A valid secret contains at least 8 alpha-numeric characters.

    **Example usage**:

    >>> valid_secret('1234', False)
    False
    >>> valid_secret(None, True)
    True
    >>> valid_secret(None, False)
    False
    >>> valid_secret('my_password', False)
    True
    """
    if secret is None and none_allowed:
        return True
    try:
        return True if re.match(r'[A-Za-z0-9@#$%^&+=-_]{8,}', secret) else False
    except:
        return False


def valid_uuid(id, none_allowed):
    u"""
    Returns True if ``id`` is a valid UUID.

    **Example usage**:

    >>> valid_uuid('gaga-gogo-gaga-gogo', False)
    False
    >>> valid_uuid(None, True)
    True
    >>> valid_uuid(uuid.uuid4(), False)
    True
    """
    if id is None and none_allowed:
        return True
    try:
        uuid.UUID('{' + str(id) + '}')
    except ValueError:
        return False
    return True

# --------------------------------------------------------------------------------------------------


def setup_logging(name='', reset=False, filename=None, console=False, level=logging.DEBUG,
                  fmt='%(asctime)s %(levelname)-8s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S'):
    u"""
    Setup logging (TODO).

    :param name: TODO
    :type name: str
    :param reset: Unregister all previously registered handlers ?
    :type reset: bool
    :param filename: TODO
    :type name: str
    :param console: Toggle console output (stdout)
    :type console: bool
    :param level: TODO
    :type level: int
    :param fmt: TODO
    :type fmt: str
    :param datefmt: TODO
    :type datefmt: str

    **Example usage**

    Setup a console output for logger with name *test*:

    >>> setup_logging(name='test', reset=True, console=True, fmt=None, datefmt=None)
    >>> log = logging.getLogger('test')
    >>> log.info('this is my info')
    this is my info
    >>> log.debug('this is my debug')
    this is my debug
    >>> log.setLevel(logging.INFO)
    >>> log.debug('this is my hidden debug')
    >>> log.handlers = []  # Remove handlers manually: pas de bras, pas de chocolat !
    >>> log.debug('no handlers, no messages ;-)')

    Show how to reset handlers of the logger to avoid duplicated messages (e.g. in doctest):

    >>> setup_logging(name='test', console=True, fmt=None, datefmt=None)
    >>> setup_logging(name='test', console=True, fmt=None, datefmt=None)
    >>> log.info('double message')
    double message
    double message
    >>> setup_logging(name='test', reset=True, console=True, fmt=None, datefmt=None)
    >>> log.info('single message')
    single message
    """
    if reset:
        logging.getLogger(name).handlers = []
    if filename:
        log = logging.getLogger(name)
        log.setLevel(level)
        handler = logging.FileHandler(filename)
        handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
        log.addHandler(handler)
    if console:
        log = logging.getLogger(name)
        log.setLevel(level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
        log.addHandler(handler)

UUID_ZERO = str(uuid.UUID('{00000000-0000-0000-0000-000000000000}'))

# Main ---------------------------------------------------------------------------------------------

if __name__ == '__main__':
    print('Testing pyutils with doctest')
    import doctest
    doctest.testmod(verbose=False)
    print('OK')
