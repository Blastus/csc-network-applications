#! /usr/bin/env python3
"""Provide a Multichat server implementation with various capabilities.

This server demonstrates some possibilities when implementing a chat host
supporting multiple users, administration controls, named rooms, contacts,
expression interpreters, asynchronous communications, and account options."""

__author__ = 'Stephen "Zero" Chappell <Noctis.Skytower@gmail.com>'
__date__ = '11 October 2012'
__version__ = 1, 0, 0

################################################################################

import threading
import socket
import sys
import inspect
import pickle
import os
import weakref
import textwrap
import traceback
import random
import operator
import json

################################################################################

# Save source code in a global variable.

with open(sys.argv[0] if __name__ == '__main__' else __file__) as SOURCE:
    SOURCE = tuple(SOURCE.read().split('\n'))

################################################################################

# Module Functions

def main(path):
    "Run a chat server using path as root for various files."
    # Load Static Handler Data
    BanFilter.load(path)
    OutsideMenu.load(path)
    InsideMenu.load(path)
    # Start The Chat Server
    server = Server('', 8989)
    server.start()
    server.join()
    # Wait On Connected Clients
    while True:
        current = threading.current_thread()
        key = lambda thread: not (thread.daemon or thread is current)
        threads = tuple(filter(key, threading.enumerate()))
        if not threads:
            break
        for thread in threads:
            thread.join()
    # Save All Static Data
    InsideMenu.save(path)
    OutsideMenu.save(path)
    BanFilter.save(path)

def enum(names):
    "Create an enumeration based on the names that are given."
    names = names.replace(',', ' ').split()
    space = dict((reversed(pair) for pair in enumerate(names)), __slots__=())
    return type('enum', (object,), space)()

################################################################################

class Handler:

    "Handler(client) -> Handler instance"

    def __init__(self, client):
        "Initialize handler by saving client to public attribute."
        self.client = client

    def handle(self):
        "Raise an error for calling this abstract method."
        raise NotImplementedError()

    def command_loop(self, prompt='Command:'):
        "Handle commands received from the client."
        mute = False
        while True:
            line = self.client.input() if mute else self.client.input(prompt)
            mute = False
            value = self.run_command(line)
            if value == '__json_help__':
                mute = True
            elif isinstance(value, AttributeError):
                self.client.print('Command not found!')
            elif isinstance(value, EOFError):
                return
            elif value is not None:
                return value

    def run_command(self, line):
        "Try running command with arguments based on line."
        tokens = line.strip().split()
        if tokens:
            cmd, *args = tokens
            if cmd.endswith('__json_help__'):
                return self.json_help()
            if cmd == '?':
                cmd = 'help'
            try:
                func = getattr(self, 'do_' + cmd)
            except AttributeError as error:
                return error
            else:
                return func(args)

    def json_help(self):
        "Send client information on what commands are available."
        package = {name: self.get_help(name) for name in self.commands}
        self.client.print(json.dumps(package))
        return '__json_help__'

    @property
    def commands(self):
        "Provide a list of commands the server will respond to."
        return (name[3:] for name in dir(self) if name.startswith('do_'))

    def get_help(self, name):
        "Return the documentation string of command having name."
        try:
            func = getattr(self, 'do_' + name)
        except AttributeError:
            return 'Command not found!'
        doc = inspect.getdoc(func)
        if doc is None:
            return 'Command has no help!'
        return doc

    ########################################################################

    # These are handler commands.
    # Help reads documentation strings.

    def do_exit(self, args):
        "Exit from this area of the server."
        return EOFError()

    def do_help(self, args):
        "Call help with a command name for more information."
        if args:
            cmd = 'help' if args[0] == '?' else args[0]
            self.client.print(self.get_help(cmd))
        else:
            self.client.print('Command list:', *self.commands, sep='\n    ')
            self.client.print('Call help with command name for more info.')

    ########################################################################

    @classmethod
    def load(cls, directory):
        "Generically load static variables from directory."
        for name in os.listdir(directory):
           parts = name.split('.')
           if len(parts) == 3:
               klass, static, dat = parts
               if klass == cls.__name__ and static.isupper() and dat == 'dat':
                   path = os.path.join(directory, name)
                   if os.path.isfile(path):
                       with open(path, 'rb') as file:
                           setattr(cls, static, pickle.load(file))

    @classmethod
    def save(cls, directory):
        "Generically save static variables to directory."
        for name in filter(str.isupper, dir(cls)):
            path = '{}.{}.dat'.format(cls.__name__, name)
            with open(os.path.join(directory, path), 'wb') as file:
                pickle.dump(getattr(cls, name), file, pickle.HIGHEST_PROTOCOL)

################################################################################

class BanFilter(Handler):

    "BanFilter(client) -> BanFilter instance"

    BLOCKED = []
    data_lock = threading.Lock()

    def __init__(self, client):
        "Initialize filter with the client to screen."
        super().__init__(client)
        self.passed = False

    def handle(self):
        "Verify if client is allowed to continue to OutsideMenu."
        if self.passed:
            self.client.print('Disconnecting ...')
            self.client.close()
            return
        host, alias, ip = socket.gethostbyaddr(self.client.address[0])
        with self.data_lock:
            if host.lower() in self.BLOCKED:
                self.client.close()
            for name in alias:
                if name.lower() in self.BLOCKED:
                    self.client.close()
            for addr in ip:
                if addr in self.BLOCKED:
                    self.client.close()
        self.passed = True
        return OutsideMenu(self.client)

################################################################################

class OutsideMenu(Handler):

    "OutsideMenu(client) -> OutsideMenu instance"

    ACCOUNTS = {}
    data_lock = threading.Lock()

    @classmethod
    def account_exists(cls, name):
        "Find out if an account with name exists."
        with cls.data_lock:
            return name in cls.ACCOUNTS

    @staticmethod
    def clean_name_from_channels(name):
        "Remove all references to name in channels."
        for channel in InsideMenu.get_channels():
            with channel.data_lock:
                if name in channel.muted_to_muter:
                    del channel.muted_to_muter[name]
                while name in channel.banned:
                    channel.banned.remove(name)
                for muted in channel.muted_to_muter.keys():
                    muter = channel.muted_to_muter[muted]
                    if name in muter:
                        muter.remove(name)
                        if not muter:
                            del channel.muted_to_muter[muted]

    @classmethod
    def delete_account(cls, name):
        "Delete the account identified by name."
        with cls.data_lock:
            if name in cls.ACCOUNTS:
                del cls.ACCOUNTS[name]
                for account in cls.ACCOUNTS.values():
                    with account.data_lock:
                        if name in account.contacts:
                            account.contacts.remove(name)
        cls.clean_name_from_channels(name)

    @classmethod
    def deliver_message(cls, source, name, text):
        "Send message to name via source with text if possible."
        with cls.data_lock:
            if name in cls.ACCOUNTS:
                account = cls.ACCOUNTS[name]
                with account.data_lock:
                    account.messages.append(Message(source, text))
                event = '[EVENT] {} has sent you a message.'.format(source)
                account.broadcast(event)
                return True
            else:
                return False

    @classmethod
    def is_administrator(cls, name):
        "Check if account identified by name is an administrator."
        with cls.data_lock:
            if name in cls.ACCOUNTS:
                return cls.ACCOUNTS[name].administrator

    @classmethod
    def is_online(cls, name):
        "Check if user identified by name is online."
        with cls.data_lock:
            if name in cls.ACCOUNTS:
                return cls.ACCOUNTS[name].online
            else:
                return False

    def handle(self):
        "Print banner before entering the command loop."
        self.print_banner()
        return self.command_loop()

    def print_banner(self):
        "Show banner to the client."
##        self.client.print('''\
##===================================
##Welcome to Multichat
##Python Edition 1.0
##===================================''')
        self.client.print('''\
/----------------------------\\
|                            |
|    Welcome to Multichat    |
|   ======================   |
|     Python Edition 1.0     |
|                            |
\\----------------------------/''')

    ########################################################################

    # These are additional commands this handler recognizes.

    def do_login(self, args):
        "Login to the server to access account."
        name = args[0] if len(args) > 0 else self.client.input('Username:')
        word = args[1] if len(args) > 1 else self.client.input('Password:')
        cls = type(self)
        with self.data_lock:
            if name in cls.ACCOUNTS and \
               word == cls.ACCOUNTS[name].password:
                account = cls.ACCOUNTS[name]
                with account.data_lock:
                    if account.online:
                        self.client.print('Account is already logged in!')
                        return
                    return self.login_account(account, name)
        self.client.print('Authentication failed!')

    def do_open_source(self, args):
        "Display the entire source code for this program."
        if args and args[0] == 'show':
            show = True
        else:
            show = self.client.input('Are you sure?') in ('yes', 'true', '1')
        if show:
            for line in SOURCE:
                self.client.print(line)

    def do_register(self, args):
        "Register for an account using this command."
        if not self.check_terms_of_service():
            return EOFError()
        name = args[0] if args else self.client.input('Username:')
        if len(name.split()) > 1:
            self.client.print('Username may not have whitespace!')
            return
        cls = type(self)
        with self.data_lock:
            if name in cls.ACCOUNTS:
                self.client.print('Account already exists!')
                return
            account = cls.ACCOUNTS[name] = Account(not bool(cls.ACCOUNTS))
        try:
            word = args[1] if len(args) > 1 else self.client.input('Password:')
            assert len(word.split()) == 1
        except:
            with self.data_lock:
                del cls.ACCOUNTS[name]
            self.client.print('Password may not have whitespace!')
        else:
            with account.data_lock:
                account.password = word
                return self.login_account(account, name)

    ########################################################################

    def check_terms_of_service(self):
        "Find out if client agrees to these terms of service."
##        self.client.print('''\
##===================================
##TERMS OF SERVICE
##
##By registering with this service,
##you agree to be bound by these
##principle requirements until death
##or the end of the world:
##
##1. This service is being provided
##to you for free and must remain
##free for these terms to continue.
##
##2. Administrators should be held
##faultless in all they do except
##promoting falsehood and deception.
##
##3. The account given you will
##remain the property of the issuer
##and may be removed without warning.
##
##4. You give up all legal rights,
##privacy of data, and demands for
##fairness while using this system.
##
##5. Your terms of service will
##remain in effect if you lose
##possession over an account you
##received.
##===================================''')
        self.client.print('''\
/----------------------------\\
|      TERMS OF SERVICE      |
|  ========================  |
|  By registering with this  |
|  service, you agree to be  |
|  bound by these principle  |
|  requirements until death  |
|  or the end of the world:  |
|                            |
|  1. This service is being  |
|  provided to you for free  |
|  and must remain free for  |
|  these terms to continue.  |
|                            |
|  2. Administrators should  |
|  be held faultless in all  |
|  they do except promoting  |
|  falsehood and deception.  |
|                            |
|  3. The account given you  |
|  will remain the property  |
|  of the issuer and may be  |
|  removed without warning.  |
|                            |
|  4. You give up all legal  |
|  rights, privacy of data,  |
|  and demands for fairness  |
|  while using this system.  |
|                            |
|  5. Your terms of service  |
|  will remain in effect if  |
|  you lose possession over  |
|  an account you received.  |
\\----------------------------/''')
        return self.client.input('Do you agree?') in ('yes', 'true', '1')

    def login_account(self, account, name):
        "Complete the action of logging the client into his/her account."
        account.online = True
        self.client.name = name
        self.client.account = account
        account.client = weakref.ref(self.client, account.cleanup)
        return InsideMenu(self.client)

################################################################################

class InsideMenu(Handler):

    "InsideMenu(client) -> InsideMenu instance"
    
    MAX_FORGIVENESS = 2

    data_lock = threading.Lock()
    NEXT_CHANNEL = 1
    CHANNEL_NAMES = {}

    @classmethod
    def channel_exists(cls, name):
        "Find out if channel identified by name exists."
        with cls.data_lock:
            return name in cls.CHANNEL_NAMES

    @classmethod
    def delete_channel(cls, name):
        "Delete channel name from registry."
        with cls.data_lock:
            if name in cls.CHANNEL_NAMES:
                # The file cannot be deleted, so leave its history alive.
                # delattr(cls, 'CHANNEL_' + str(cls.CHANNEL_NAMES[name]))
                del cls.CHANNEL_NAMES[name]
                return True
            return False

    @classmethod
    def get_channels(cls):
        "Get a list of real channel (server) objects."
        with cls.data_lock:
            names = cls.CHANNEL_NAMES.values()
        channels = []
        for index in names:
            try:
                channels.append(getattr(cls, 'CHANNEL_' + str(index)))
            except:
                pass
        return channels

    @classmethod
    def get_channel_names(cls):
        "Get a list of the channel names."
        with cls.data_lock:
            return tuple(cls.CHANNEL_NAMES.keys())

    @classmethod
    def rename_channel(cls, old_name, new_name):
        "Change channel's name from old_name to new_name."
        with cls.data_lock:
            if old_name in cls.CHANNEL_NAMES:
                if new_name in cls.CHANNEL_NAMES:
                    return False
                index = cls.CHANNEL_NAMES[old_name]
                del cls.CHANNEL_NAMES[old_name]
                cls.CHANNEL_NAMES[new_name] = index
                return True

    def handle(self):
        "Handle commands from the client for the inside menu."
        self.print_status()
        handler = self.command_loop()
        if handler is None:
            with self.client.account.data_lock:
                self.client.account.online = False
                del self.client.account
                del self.client.name
        return handler
        
    def print_status(self):
        "Show a status message to those just entering the inside menu."
        if self.client.account.administrator:
            self.client.print('Welcome, administrator!')
        key = lambda message: message.new
        with self.client.account.data_lock:
            new = sum(map(key, self.client.account.messages))
            contacts = list(self.client.account.contacts)
        args = new, ('s', '')[new == 1]
        self.client.print('You have {} new message{}.'.format(*args))
        online = 0
        with OutsideMenu.data_lock:
            for name in contacts:
                if name in OutsideMenu.ACCOUNTS:
                    account = OutsideMenu.ACCOUNTS[name]
                    with account.data_lock:
                        if account.online:
                            online += 1
        total = len(contacts)
        args = online, total, ('s', '')[total == 1], ('are', 'is')[online == 1]
        self.client.print('{} of your {} friend{} {} online.'.format(*args))

    ########################################################################

    # These are additional commands this handler recognizes.

    def do_admin(self, args):
        "Access the administration console (if you are an administrator)."
        if not self.client.account.administrator:
            cls = type(self)
            if self.client.account.forgiven >= cls.MAX_FORGIVENESS:
                with BanFilter.data_lock:
                    BanFilter.BLOCKED.append(self.client.address[0])
                OutsideMenu.delete_account(self.client.name)
                self.client.print('You have been warned for the last time!')
                self.client.print('Now your IP address has been blocked &')
                self.client.print('your account has been completely removed.')
                self.client.close()
            with self.client.account.data_lock:
                self.client.account.forgiven += 1
            self.client.print('You are not authorized to be here.')
            return EOFError()
        return AdminConsole(self.client)

    def do_channel(self, args):
        "Allows you create and connect to message channels."
        name = args[0] if args else self.client.input('Channel to open?')
        if len(args) > 1 or len(name.split()) > 1:
            self.client.print('Channel name may not have whitespace!')
            return
        if name:
            cls = type(self)
            with self.data_lock:
                if name in self.CHANNEL_NAMES:
                    index = str(self.CHANNEL_NAMES[name])
                    channel = getattr(cls, 'CHANNEL_' + index)
                else:
                    channel = ChannelServer(name, self.client.name)
                    self.CHANNEL_NAMES[name] = cls.NEXT_CHANNEL
                    attr_name = 'CHANNEL_' + str(cls.NEXT_CHANNEL)
                    setattr(cls, attr_name, channel)
                    cls.NEXT_CHANNEL += 1
                self.client.print('Opening the', name, 'channel ...')
                return channel.connect(self.client)
        self.client.print('Channel name may not be empty.')

    def do_contacts(self, args):
        "Opens up your contacts list and allows you to edit it."
        return ContactManager(self.client)

    def do_eval(self, args):
        "Proof of concept: this is a math expression evaluator."
        version = args[0] if args else self.client.input('Version?')
        if version == 'old':
            return MathExpressionEvaluator(self.client)
        elif version == 'new':
            return MathEvaluator2(self.client)
        self.client.print('Try old or new.')

    def do_messages(self, args):
        "Opens up your account's inbox to read and send messages."
        return MessageManager(self.client)

    def do_options(self, args):
        "You can change some your settings with this command."
        return AccountOptions(self.client)

################################################################################

class Server(threading.Thread):

    "Server(host, port) -> Server instance"

    def __init__(self, host, port):
        "Initialize variables for creating server thread."
        super().__init__()
        self.clients = []
        self.loop = True
        self.host = host
        self.port = port
        self.data_lock = threading.Lock()

    def run(self):
        "Create and run a server loop for connecting clients."
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.host, self.port))
        server.listen(5)
        while self.loop:
            connection, address = server.accept()
            with self.data_lock:
                if self.loop:
                    client = Client(connection, address)
                    client.server = self
                    self.clients.append(client)
                    Stack(BanFilter(client)).start()
        server.close()

################################################################################

class Client:

    "Client(socket, address) -> Client instance"

    RECV_SIZE = 1 << 12
    BUFF_SIZE = 1 << 16
    SEPARATOR = b'\r\n'

    def __init__(self, socket, address):
        "Initialize variables that make up a client instance."
        self.closed = False
        self.socket = socket
        self.address = address
        self.buffer = bytes()

    def recv(self):
        "Return a line having a separator at its end."
        if self.closed:
            sys.exit()
        while self.SEPARATOR not in self.buffer:
            try:
                self.buffer += self.socket.recv(self.RECV_SIZE)
            except socket.error:
                self.close()
            else:
                if len(self.buffer) > self.BUFF_SIZE:
                    self.close()
        index = self.buffer.index(self.SEPARATOR) + len(self.SEPARATOR)
        self.buffer, text = self.buffer[index:], self.buffer[:index]
        return text

    def send(self, text):
        "Normalize and encode text before sending all data."
        if self.closed:
            sys.exit()
        for index in range(len(self.SEPARATOR), 0, -1):
            text = text.replace(self.SEPARATOR[:index], self.SEPARATOR[-1:])
        self.socket.sendall(text.replace(self.SEPARATOR[-1:], self.SEPARATOR))

    def close(self, suppress_exit=False):
        "Properly close socket and optionally signal end-of-stream."
        if self.closed:
            sys.exit()
        self.closed = True
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()
        if not suppress_exit:
            sys.exit()

    def input(self, *prompt):
        "Return decoded line without separator and optionally print prompt."
        if prompt:
            assert len(prompt) == 1, 'One argument at most allowed!'
            self.print(*prompt)
        return self.recv()[:-len(self.SEPARATOR)].decode()

    def print(self, *value, sep=' ', end='\n'):
        "Format arguments and send resulting string to client."
        self.send('{}{}'.format(sep.join(map(str, value)), end).encode())

################################################################################

class Stack(threading.Thread):

    "Stack(handler) -> Stack instance"

    def __init__(self, handler):
        "Initialize stack with client handler."
        super().__init__()
        self.root = handler
        self.stack = [handler]

    def run(self):
        "Execute dedicated thread for processing client handlers."
        client = self.root.client
        try:
            while self.stack:
                try:
                    handler = self.stack[-1].handle()
                except SystemExit:
                    raise
                except Exception as error:
                    try:
                        client.print('X' * 70)
                        client.print('Please report this error ASAP!')
                        client.print('X' * 70)
                        client.print(traceback.format_exc())
                        client.print('X' * 70)
                    except:
                        pass
                    raise error
                if handler is None:
                    self.stack.pop()
                else:
                    self.stack.append(handler)
        except SystemExit:
            pass
        finally:
            try:
                with client.server.data_lock:
                    client.server.clients.remove(client)
                client.account.online = False
            except:
                pass

################################################################################

class Account:

    "Account(administrator) -> Account instance"

    def __init__(self, administrator):
        "Initialize Account with various variables it requires."
        self.administrator = administrator
        self.data_lock = threading.Lock()
        self.online = False
        self.password = ''
        self.contacts = []
        self.messages = []
        self.forgiven = 0

    def __getstate__(self):
        "Return state of account for pickling purposes."
        state = self.__dict__.copy()
        del state['data_lock']
        del state['online']
        if 'client' in state:
            del state['client']
        return state

    def __setstate__(self, state):
        "Set the state of this instance while unpickling."
        self.__dict__.update(state)
        self.data_lock = threading.Lock()
        self.online = False

    def add_contact(self, name):
        "Try to add contact name to contact list for this account."
        with self.data_lock:
            assert name not in self.contacts
            if OutsideMenu.account_exists(name):
                self.contacts.append(name)
                return True
            return False

    def broadcast(self, message):
        "If there is a client for this account, display message."
        with self.data_lock:
            if self.online:
                client = self.client()
                if client is not None:
                    client.print(message)

    def cleanup(self, client):
        "Remove the client associated with this account."
        del self.client

    def delete_message(self, data):
        "Remove the given message(s) from this account."
        if isinstance(data, (list, tuple)):
            for message in data:
                self.delete_message(message)
        elif isinstance(data, Message):
            with self.data_lock:
                if data in self.messages:
                    self.messages.remove(data)
        else:
            raise TypeError('Data type not expected!')

    def force_disconnect(self):
        "If there is a client for this account, disconnect it."
        with self.data_lock:
            if self.online:
                client = self.client()
                if client is not None:
                    client.close(True)

    def prune_by_source(self, source, messages):
        "Remove messages that do not match the required source."
        if source is None or not messages:
            return messages
        key = lambda message: message.source == source
        return tuple(filter(key, messages))

    def prune_by_status(self, status, messages):
        "Remove messages that do not match the required status."
        if status is None or not messages:
            return messages
        assert status in ('read', 'unread'), 'Status is not valid!'
        if status == 'read':
            key = lambda message: not message.new
        else:
            key = lambda message: message.new
        return tuple(filter(key, messages))

    def purge_contacts(self):
        "Delete all contact information from this account."
        with self.data_lock:
            self.contacts = []

    def purge_messages(self):
        "Delete all messages stored on this account."
        with self.data_lock:
            self.messages = []

    def remove_contact(self, name):
        "Remove contact name from contact list on this account."
        with self.data_lock:
            if name in self.contacts:
                self.contacts.remove(name)
                return True
            return False

    def show_contacts(self, client, status):
        "Print account contact list to given client."
        with self.data_lock:
            contacts = list(self.contacts)
        if contacts:
            if status:
                for index, name in enumerate(contacts):
                    statext = ('FF', 'N')[OutsideMenu.is_online(name)]
                    args = index + 1, name, statext
                    client.print('({}) {} [O{}line]'.format(*args))
            else:
                for index, name in enumerate(contacts):
                    client.print('({}) {}'.format(index + 1, name))
        else:
            client.print('Contact list is empty.')
        return contacts

    def show_message_summary(self, client, status, length, *,
                             filter_status=None, filter_source=None):
        "Print a formatted summary of the messages on this account."
        with self.data_lock:
            messages = list(self.messages)
        messages = self.prune_by_status(filter_status, messages)
        messages = self.prune_by_source(filter_source, messages)
        if messages:
            statext = ''
            for index, data in enumerate(messages):
                if status:
                    statext = (' [read]', ' [UNread]')[data.new]
                args = index + 1, data.source, statext
                client.print('Message {} from {}{}:'.format(*args))
                text = data.message.replace('\n', ' ')
                if len(text) > length:
                    client.print('    {}...'.format(text[:length]))
                else:
                    client.print('    {}'.format(text))
        else:
            client.print('There are no messages.')
        return messages

################################################################################

class AdminConsole(Handler):

    "AdminConsole(client) -> AdminConsole instance"

    shutdown = enum('server, users, admin, all')

    def handle(self):
        "Show client status of action and run command loop."
        self.client.print('Opening admin console ...')
        return self.command_loop()

    ########################################################################

    # These are additional commands this handler recognizes.

    def do_account(self, args):
        "Access all account related controls."
        if not args:
            self.client.print('Try view, remove, or edit.')
            return
        command = args[0]
        if command == 'view':
            self.account_view(None)
        elif command == 'remove':
            self.account_remove(args[1:])
        elif command == 'edit':
            return self.account_edit(args[1:])
        else:
            self.client.print('Try view, remove, or edit.')

    def do_ban(self, args):
        "Access all IP ban filter controls."
        if not args:
            self.client.print('Try view, add, or remove.')
            return
        command = args[0]
        if command == 'view':
            self.ban_view(None)
        elif command == 'add':
            self.ban_add(args[1:])
        elif command == 'remove':
            self.ban_remove(args[1:])
        else:
            self.client.print('Try view, add, or remove.')

    def do_channels(self, args):
        "View a list of all current channels."
        names = InsideMenu.get_channel_names()
        if names:
            s = len(names) == 1 and ' ' or 's '
            self.client.print('Channel{}currently in existence:'.format(s))
            for name in names:
                self.client.print('   ', name)
        else:
            self.client.print('There are no channels at this time.')

    def do_shutdown(self, args):
        "Arrange for the server to shutdown and save its data."
        if not args:
            self.client.print('Try server, users, admin, or all.')
            return
        message = self.client.name + ' is shutting down your connection.'
        level = getattr(self.shutdown, args[0], -1)
        if level == self.shutdown.server:
            self.shutdown_server(message)
        elif level > self.shutdown.server:
            self.shutdown_server(message)
            self.disconnect_accounts(message, level)
        else:
            self.client.print('Try server, users, admin, or all.')

    ########################################################################

    def account_edit(self, args):
        "Return an AccountEditor for the selected account."
        if args:
            name = args[0]
        else:
            name = self.get_account_name()
        if name is not None:
            if name == self.client.name:
                self.client.print('You may not edit yourself.')
            else:
                with OutsideMenu.data_lock:
                    if name in OutsideMenu.ACCOUNTS:
                        account = OutsideMenu.ACCOUNTS[name]
                    else:
                        self.client.print('Unable to access account.')
                        return
                return AccountEditor(self.client, name, account)

    def account_remove(self, args):
        "Remove account specified by client."
        if args:
            name = args[0]
            if name == self.client.name:
                self.client.print('You cannot remove yourself.')
                return
            else:
                success = self.disconnect_and_remove(name)
        else:
            name = self.get_account_name()
            if name is None:
                return
            success = self.disconnect_and_remove(name)
        if success:
            self.client.print('Account has been removed.')

    def account_view(self, account_list):
        "Print formatted list of accounts."
        if account_list is None:
            with OutsideMenu.data_lock:
                account_list = list(OutsideMenu.ACCOUNTS.keys())
        for index, address in enumerate(account_list):
            self.client.print('({}) {}'.format(index + 1, address))

    def ban_add(self, args):
        "Add an address to the list of those banned."
        addr = args[0] if args else self.client.input('Address:')
        if addr:
            with BanFilter.data_lock:
                if addr in BanFilter.BLOCKED:
                    self.client.print('Address in already in ban list.')
                else:
                    BanFilter.BLOCKED.append(addr)
                    self.client.print('Address has been successfully added.')
        else:
            self.client.print('Empty address may not be added.')

    def ban_remove(self, args):
        "Remove an address from the list of those banned."
        if args:
            with BanFilter.data_lock:
                if args[0] in BanFilter.BLOCKED:
                    BanFilter.BLOCKED.remove(args[0])
                else:
                    self.client.print('Address not found.')
                    return
        else:
            with BanFilter.data_lock:
                addr_list = list(BanFilter.BLOCKED)
            self.ban_view(addr_list)
            if addr_list:
                try:
                    index = int(self.client.input('Item number?')) - 1
                    assert 0 <= index < len(addr_list)
                except:
                    self.client.print('You must enter a valid number.')
                    return
                else:
                    addr = addr_list[index]
                    with BanFilter.data_lock:
                        while addr in BanFilter.BLOCKED:
                            BanFilter.BLOCKED.remove(addr)
        self.client.print('Address has been removed.')

    def ban_view(self, addr_list):
        "View list of addresses that are banned."
        if addr_list is None:
            with BanFilter.data_lock:
                addr_list = list(BanFilter.BLOCKED)
        if addr_list:
            for index, address in enumerate(addr_list):
                self.client.print('({}) {}'.format(index + 1, address))
        else:
            self.client.print('No one is in the ban list.')

    def disconnect_accounts(self, message, level):
        "Send message to matching accounts and disconnect them."
        with OutsideMenu.data_lock:
            accounts = list(OutsideMenu.ACCOUNTS.values())
        for account in accounts:
            if account is not self.client.account:
                if level > self.shutdown.users or not account.administrator:
                    account.broadcast(message)
                    account.force_disconnect()
        self.client.print('Shutdown process has been completed.')
        if level == self.shutdown.all:
            self.client.close()

    def disconnect_and_remove(self, name):
        "Force account name to disconnect and then delete."
        with OutsideMenu.data_lock:
            if name in OutsideMenu.ACCOUNTS:
                OutsideMenu.ACCOUNTS[name].force_disconnect()
            else:
                self.client.print('Account does not exist.')
                return False
        OutsideMenu.delete_account(name)
        return True

    def disconnect_clients(self, message, client_array):
        "Send message to client and disconnect them."
        count = 0
        for client in client_array:
            if not hasattr(client, 'name'):
                client.print(message)
                client.close(True)
                count += 1
        args = count, ('s were', ' was')[count == 1]
        self.client.print('{} sleeper{} disconnected.'.format(*args))

    def get_account_name(self):
        "Display accounts and get name for one of them."
        with OutsideMenu.data_lock:
            names = OutsideMenu.ACCOUNTS.keys()
            names = filter(lambda name: name != self.client.name, names)
            account_list = list(names)
        if account_list:
            self.account_view(account_list)
            try:
                index = int(self.client.input('Account number?')) - 1
                assert 0 <= index < len(account_list)
            except:
                self.client.print('You must enter a valid number.')
            else:
                return account_list[index]
        else:
            self.client.print('There are no other accounts.')

    def shutdown_server(self, message):
        "Shutdown server to disconnect clients and save static data."
        server = self.client.server
        with server.data_lock:
            if server.loop:
                server.loop = False
                socket.create_connection(('localhost', self.client.server.port))
                self.client.print('Server has been shutdown.')
                client_array = tuple(server.clients)
            else:
                self.client.print('Server was already closed.')
                client_array = None
        if client_array is not None:
            self.disconnect_clients(message, client_array)

################################################################################

class AccountEditor(Handler):

    "AccountEditor(client, name, account) -> AccountEditor instance"

    def __init__(self, client, name, account):
        "Initialize the editor with information on the account."
        super().__init__(client)
        self.name = name
        self.account = account

    def handle(self):
        "Handle all instructions from the client."
        self.client.print('Opening account editor ...')
        return self.command_loop()

    ########################################################################

    # These are additional commands this handler recognizes.

    def do_edit(self, args):
        "Change various attributes of the account."
        attr = args[0] if args else self.client.input('What?')
        account = self.account
        if attr == 'admin':
            with account.data_lock:
                admin = account.administrator = not account.administrator
            args = self.name, ('not ', '')[admin]
            self.client.print('{} is {}an administrator now.'.format(*args))
        elif attr == 'password':
            word = args[1] if len(args) > 1 else self.client.input('Password:')
            with account.data_lock:
                account.password = word
            self.client.print('Password has been changed to', repr(word))
        elif attr == 'forgiven':
            if len(args) > 1 and args[1] == 'reset':
                reset = True
            else:
                reset = self.client.input('Reset?') in ('yes', 'true', '1')
            if reset:
                with account.data_lock:
                    account.forgiven = 0
                self.client.print('Forgiven count has been set to zero.')
        else:
            self.client.print('Try admin, password, or forgiven.')

    def do_info(self, args):
        "Show information about the current account."
        self.client.print('About account "{}":'.format(self.name))
        account = self.account
        with account.data_lock:
            self.client.print('Admin    =', account.administrator)
            self.client.print('Online   =', account.online)
            self.client.print('Friends  =', len(account.contacts))
            self.client.print('Messages =', len(account.messages))
            self.client.print('Forgiven =', account.forgiven)

    def do_password(self, args):
        "Show the password on the account."
        self.client.print('Username:', repr(self.name))
        with self.account.data_lock:
            self.client.print('Password:', repr(self.account.password))

    def do_read(self, args):
        "Show account's contact list or read message summaries."
        attr = args[0] if args else self.client.input('Contacts or messages?')
        account = self.account
        if attr == 'contacts':
            self.client.print("{}'s contact list:".format(self.name))
            account.show_contacts(self.client, False)
        elif attr == 'messages':
            self.client.print('First 70 bytes of each message:')
            account.show_message_summary(self.client, False, 70)
        else:
            self.client.print('Try contacts or messages.')

################################################################################

class ChannelServer(Handler):

    "ChannelServer(channel_name, owner) -> ChannelServer instance"

    state = enum('start, setup, ready, reset, final')
    builtin_buffer_limit = 10000

    def __init__(self, channel_name, owner):
        "Initialize the ChannelServer with information about the channel."
        self.channel_name = channel_name
        self.owner = owner
        self.password = ''
        self.buffer = []
        self.buffer_size = None
        self.replay_size = 10
        self.status = self.state.start
        self.data_lock = threading.Lock()
        self.connected_clients = {}
        self.muted_to_muter = {}
        self.kicked = []
        self.banned = []
        self.admin_lock = threading.Lock()
        self.admin_name = ''

    def __getstate__(self):
        "Get the state of the channel for saving and pickling."
        state = self.__dict__.copy()
        del state['data_lock']
        del state['admin_lock']
        del state['connected_clients']
        return state

    def __setstate__(self, state):
        "Restore the state of the channel when loading and unpickling."
        self.__dict__.update(state)
        self.data_lock = threading.Lock()
        self.connected_clients = {}
        self.admin_lock = threading.Lock()

    @staticmethod
    def get_size(client, args=None):
        "Get a number that represents a size."
        while True:
            if args:
                line, args = args[0], None
            else:
                line = client.input('Size limitation:')
            if line in ('all', 'infinite', 'total'):
                return
            try:
                size = int(line)
                assert size >= 0
            except (ValueError, AssertionError):
                client.print('Please enter a non-negative number.')
            else:
                return size

    @property
    def client(self):
        "Get the correct client based on the current thread."
        with self.data_lock:
            return self.connected_clients[threading.current_thread().ident]

    def handle(self):
        "Handle people connecting to the channel server."
        try:
            handler = self.dispatch()
        finally:
            name = self.client.name
            with self.data_lock:
                while name in self.kicked:
                    self.kicked.remove(name)
            self.disconnect()
        return handler

    ########################################################################

    # These are additional commands this handler recognizes.

    def do_admin(self, args):
        "Owner: change this channels settings."
        if self.privileged():
            return ChannelAdmin(self.client, self)

    def do_ban(self, args):
        "Owner: ban a user from joining this channel."
        client = self.client
        if self.privileged():
            if not args:
                client.print('Try add, del, or list.')
                return
            command = args[0]
            if command == 'add':
                name = args[1] if len(args) > 1 else client.input('Who?')
                if not name:
                    client.print('Cancelling ...')
                    return
                self.add_ban(client, name)
            elif command == 'del':
                name = args[1] if len(args) > 1 else client.input('Who?')
                if not name:
                    client.print('Cancelling ...')
                    return
                self.del_ban(client, name)
            elif command == 'list':
                self.list_ban(client)
            else:
                client.print('Try add, del, or list.')

    def do_invite(self, args):
        "Invite someone to join this channel."
        client = self.client
        with self.data_lock:
            exists = self.channel_name is not None
            password = self.password
        if not exists:
            client.print('This channel has been permanently closed.')
            return
        if not password or self.privileged():
            self.send_invitation(args, client)

    def do_kick(self, args, verbose=True):
        "Owner: kick a user off this channel."
        if self.privileged():
            name = args[0] if args else self.client.input('Who?')
            printer = self.client.print if verbose else lambda *args: None
            if not name:
                printer('Cancelling ...')
                return
            protected = self.is_protected(name)
            if protected is not None:
                if protected:
                    printer(name, 'cannot be kicked.')
                    return
                with self.data_lock:
                    connected = self.connected_clients.items()
                for ident, client in connected:
                    if client.name == name:
                        with self.data_lock:
                            if ident in self.connected_clients:
                                self.kicked.append(name)
                                printer(name, 'has been kicked.')
                                break
                else:
                    printer(name, 'is not on this channel.')

    def do_list(self, args):
        "Show everyone connected to this channel."
        with self.data_lock:
            client_list = tuple(self.connected_clients.values())
        if len(client_list) == 1:
            self.client.print('You alone are on this channel.')
        else:
            self.client.print('Current connected to this channel:')
            for client in client_list:
                self.client.print('   ', client.name)

    def do_mute(self, args):
        "Access and change your muted user list."
        client = self.client
        if not args:
            client.print('Try add, del, or list.')
            return
        command = args[0]
        if command == 'add':
            muted = args[1] if len(args) > 1 else client.input('Who?')
            self.add_mute(muted, client)
        elif command == 'del':
            muted = args[1] if len(args) > 1 else client.input('Who?')
            self.del_mute(muted, client)
        elif command == 'list':
            self.list_mute(client)
        else:
            self.client.print('Try add, del, or list.')

    def do_summary(self, args):
        "Proof of concept: Mark V Shaney summarizes the channel."
        with self.data_lock:
            buffer = self.buffer[:]
        if buffer:
            size = (len(buffer) + 3) // 4
            return MarkVShaney(self.client, buffer, size, self)
        else:
            self.client.print('There is nothing to summarize.')

    def do_wisper(self, args):
        "Send a message to one specific person."
        client = self.client
        name = args[0] if args else client.input('Who?')
        if not name:
            client.print('Cancelling ...')
            return
        if not OutsideMenu.account_exists(name):
            client.print(name, 'does not exist.')
            return
        message = client.input('Message:')
        if not message:
            client.print('You may not wisper empty messages.')
            return
        if self.send_wisper(name, message):
            client.print('Message sent.')
        else:
            client.print(name, 'no longer has an account.')

    ########################################################################

    def add_ban(self, client, name):
        "Try to ban user identified by name."
        protected = self.is_protected(name)
        if protected is not None:
            if protected:
                client.print(name, 'cannot be banned.')
            with self.data_lock:
                will_ban = name not in self.banned
                if will_ban:
                    self.banned.append(name)
            if will_ban:
                self.do_kick([name], False)
                client.print(name, 'has been banned.')
            else:
                client.print(name, 'was already been banned.')

    def add_line(self, name, line):
        "Add a line to the channel buffer."
        with self.data_lock:
            if self.buffer_size is None:
                buffer_size = self.builtin_buffer_limit
            else:
                buffer_size = min(self.buffer_size, self.builtin_buffer_limit)
            channel_line = ChannelLine(name, line)
            if buffer_size:
                self.buffer.append(channel_line)
                if len(self.buffer) > buffer_size:
                    del self.buffer[:len(self.buffer)-buffer_size]
            return channel_line

    def add_mute(self, muted, client):
        "Add someone to list of muted people."
        with self.data_lock:
            okay = OutsideMenu.account_exists(muted)
            if okay:
                if muted in self.muted_to_muter:
                    muters = self.muted_to_muter[muted]
                    if client.name not in muters:
                        muters.append(client.name)
                        okay += 1
                else:
                    self.muted_to_muter[muted] = [client.name]
                    okay += 1
        if okay:
            if okay > 1:
                client.print(muted, 'has been muted.')
            else:
                client.print(muted, 'was already muted.')
        else:
            if muted:
                client.print(muted, 'does not exist.')
            else:
                client.print('Cancelling ...')

    def authenticate(self):
        "Allow client to authenticate to the channel if needed."
        with self.data_lock:
            password = self.password
        if not password or self.privileged(False):
            return True
        return self.client.input('Password to connect:') == password

    def broadcast(self, channel_line, echo):
        "Send message to all connected clients except the sender."
        client = self.client
        with self.data_lock:
            clients = tuple(self.connected_clients.values())
            muter = self.muted_to_muter.get(channel_line.source, [])
            kicked = tuple(self.kicked)
        def accept(destination):
            if destination.name in kicked:
                return False
            if destination.name in muter:
                return False
            if echo:
                return True
            return destination is not client
        for destination in filter(accept, clients):
            channel_line.echo(destination)

    def connect(self, client):
        "Connect the client to this channel."
        with self.data_lock:
            self.connected_clients[threading.current_thread().ident] = client
        return self

    def del_ban(self, client, name):
        "Try to remove a ban from user identified by name."
        with self.data_lock:
            will_remove = name in self.banned
            if will_remove:
                self.banned.remove(name)
        if will_remove:
            client.print(name, 'is no longer banned on this channel.')
        else:
            client.print(name, 'was not banned on this channel.')
        return False

    def del_mute(self, muted, client):
        "Remove someone from list of muted people."
        if muted:
            message = muted + ' was not muted.'
            with self.data_lock:
                if muted in self.muted_to_muter:
                    muters = self.muted_to_muter[muted]
                    if client.name in muters:
                        message = muted + ' has been unmuted.'
                        muters.remove(client.name)
                        if not muters:
                            del self.muted_to_muter[muted]
            client.print(message)
        else:
            client.print('Cancelling ...')

    def disconnect(self):
        "Remove the client from this channel's registry."
        with self.data_lock:
            del self.connected_clients[threading.current_thread().ident]

    def dispatch(self):
        "Ensure the channel is setup before allow people to enter."
        client = self.client
        with self.data_lock:
            if self.status == self.state.final:
                return
            if self.status == self.state.reset and client.name == self.owner:
                self.status = self.state.start
            status = self.status
            if self.status == self.state.start:
                self.status = self.state.setup
        if status == self.state.start:
            try:
                self.setup_channel()
            finally:
                with self.data_lock:
                    status = self.status = self.state.ready
        if status in (self.state.setup, self.state.reset):
            client.print(self.owner, 'is setting up this channel.')
            return
        elif status == self.state.ready:
            return self.run_channel()
        else:
            raise ValueError(str(status) + ' is not a proper status value!')

    def is_protected(self, name):
        "Find out if user identified by name has certain protections."
        with self.data_lock:
            if self.owner == name:
                return True
        administrator = OutsideMenu.is_administrator(name)
        if administrator is None:
            self.client.print(name, 'does not exist.')
        else:
            return administrator

    def list_ban(self, client):
        "List the names of users banned on this channel."
        with self.data_lock:
            banned = tuple(self.banned)
        if banned:
            client.print('Those that are banned from this channel:')
            for name in banned:
                client.print('   ', name)
        else:
            client.print('No one has been banned on this channel.')

    def list_mute(self, client):
        "List people who have been muted."
        with self.data_lock:
            m2m = self.muted_to_muter.copy()
        you_mute = []
        for muted in m2m:
            if client.name in m2m[muted]:
                you_mute.append(muted)
        if you_mute:
            client.print('You have muted:', *you_mute, sep='\n    ')
        else:
            client.print('Your list is empty.')

    def may_wisper(self, name):
        "Find out if client may wisper to user identified by name."
        sender = self.client.name
        with self.data_lock:
            if name in self.muted_to_muter.get(sender, ()):
                return
            clients = self.connected_clients.values()
        for client in clients:
            if client.name == name:
                return client

    def message_loop(self):
        "Process incoming commands from client."
        client = self.client
        event = ChannelLine('EVENT', client.name + ' is joining.')
        self.broadcast(event, False)
        while True:
            line = client.input()
            with self.data_lock:
                if client.name in self.kicked:
                    client.print('You have been kicked out of this channel.')
                    return
            if line.startswith(':'):
                value = self.run_command(line[1:])
                if value == '__json_help__':
                    pass
                elif isinstance(value, AttributeError):
                    client.print('Command not found!')
                elif isinstance(value, EOFError):
                    return
                elif value is not None:
                    return value
            else:
                channel_line = self.add_line(client.name, line)
                self.broadcast(channel_line, True)

    def privileged(self, show_error=True):
        "Find out if current user is privileged and display error if needed."
        client = self.client
        with client.account.data_lock:
            if client.account.administrator:
                return True
        with self.data_lock:
            if client.name == self.owner:
                return True
        if show_error:
            client.print('Only administrators or channel owner may do that.')

    def run_channel(self):
        "Handle user entering into a channel and run message loop as needed."
        client = self.client
        with self.data_lock:
            banned = client.name in self.banned
        if banned:
            client.print('You have been banned from this channel.')
        elif self.authenticate():
            self.replay_buffer()
            self.show_status()
            try:
                data = self.message_loop()
            finally:
                event = ChannelLine('EVENT', self.client.name + ' is leaving.')
                self.broadcast(event, False)
            return data
        else:
            client.print('You have failed authentication.')

    def replay_buffer(self):
        "Show the message buffer to client."
        with self.data_lock:
            if self.replay_size is None:
                buffer = tuple(self.buffer)
            elif self.replay_size > 0:
                buffer = tuple(self.buffer[-self.replay_size:])
            else:
                buffer = ()
        client = self.client
        for line in buffer:
            line.echo(client)

    def send_invitation(self, args, client):
        "Send an invitation to another users to join this channel."
        name = args[0] if args else client.input('Who?')
        if name:
            if name == client.name:
                client.print('You are already here.')
                return
            with self.data_lock:
                channel_name = self.channel_name
            if channel_name is None:
                client.print('This channel has been permanently closed.')
                return
            args = client.name, channel_name
            message = '{} has invited you to channel {}.'.format(*args)
            if self.password:
                message += '\n\nUse this to get in: ' + repr(self.password)
            if OutsideMenu.deliver_message(client.name, name, message):
                client.print('Invitation has been sent.')
            else:
                client.print(name, 'does not exist.')
        else:
            client.print('Cancelling ...')

    def send_wisper(self, name, message):
        "Send a wispered message to user identified by name."
        client = self.may_wisper(name)
        if client is None:
            return OutsideMenu.deliver_message(self.client.name, name, message)
        client.print('({}) {}'.format(self.client.name, message))
        return True

    def show_status(self):
        "Show how many people are connected to the channel."
        with self.data_lock:
            connected = len(self.connected_clients)
        args = connected, ('people are', 'person is')[connected == 1]
        self.client.print('{} {} connected.'.format(*args))

    def setup_buffer_size(self):
        "Allow the client to set the buffer size."
        client = self.client
        answer = client.input('Do you want to set the buffer size?')
        if answer in ('yes', 'true', '1'):
            size = self.get_size(client)
            with self.data_lock:
                self.buffer_size = size

    def setup_channel(self):
        "Allow client to setup the channel (password, buffer, and replay)."
        self.setup_password()
        self.setup_buffer_size()
        self.setup_replay_size()

    def setup_password(self):
        "Allow client to set the password."
        answer = self.client.input('Password protect this channel?')
        if answer in ('yes', 'true', '1'):
            while True:
                password = self.client.input('Set password to:')
                if password:
                    with self.data_lock:
                        self.password = password
                    return
                else:
                    self.client.print('Password may not be empty.')

    def setup_replay_size(self):
        "Allow the client to set the replay size."
        client = self.client
        answer = client.input('Do you want to set the replay size?')
        if answer in ('yes', 'true', '1'):
            size = self.get_size(client)
            with self.data_lock:
                self.replay_size = size

    ########################################################################

    # The following commands will never be created using the current
    # framework this program is built upon. They are here to reflect
    # what may happen in the future, dreams of greater expectations.

    def do_bot(self, args):
        "Owner: add optional channel commands."
        if self.privileged():
            self.client.print('Reserved command for future expansion ...')
            # this would be a good place for the math expression evaluator

    def do_map(self, args):
        "Owner: add optional channel modifiers."
        if self.privileged():
            self.client.print('Reserved command for future expansion ...')
            # scrambling the middle letters of all words would be very fun

    def do_run(self, args):
        "Owner: add optional channel extensions."
        if self.privileged():
            self.client.print('Reserved command for future expansion ...')
            # alternate programs could be implemented and executed via run

################################################################################

class ChannelAdmin(Handler):

    "ChannelAdmin(client, channel) -> ChannelAdmin instance"

    def __init__(self, client, channel):
        "Initialize admin console with client and associated channel."
        super().__init__(client)
        self.channel = channel

    def handle(self):
        "Acquire control of the channel and run the command loop."
        admin = self.channel.admin_lock.acquire(False)
        if admin:
            with self.channel.data_lock:
                self.channel.admin_name = self.client.name
            try:
                self.client.print('Opening admin console ...')
                handler = self.command_loop()
            finally:
                self.channel.admin_lock.release()
            if handler is None:
                self.channel.connect(self.client)
            return handler
        else:
            self.client.print(self.channel.admin_name,
                              'is currently using the admin console.')
            self.channel.connect(self.client)

    ########################################################################

    # These are additional commands this handler recognizes.

    def do_buffer(self, args):
        "Set the buffer size of this channel."
        size = ChannelServer.get_size(self.client, args)
        with self.channel.data_lock:
            self.channel.buffer_size = size

    def do_close(self, args):
        "Kick everyone off the channel (useful after delete)."
        with self.channel.data_lock:
            for client in self.channel.connected_clients.values():
                self.channel.kicked.append(client.name)
        self.client.print('Everyone has been kicked off the channel.')

    def do_delete(self, args):
        "Unregister this channel as though it did not exist."
        with self.channel.data_lock:
            deleted = self.channel.channel_name is None
            if not deleted:
                assert InsideMenu.delete_channel(self.channel.channel_name), \
                       'Name was set, but it was not registered.'
                self.channel.channel_name = None
        if deleted:
            self.client.print('This channel had been previously deleted.')
        else:
            self.client.print('This channel is no longer enterable.')

    def do_finalize(self, args):
        "Delete, close, and reset the channel (returns you to main menu)."
        with self.channel.data_lock:
            self.channel.status = ChannelServer.state.final
            if self.channel.channel_name is not None:
                InsideMenu.delete_channel(self.channel.channel_name)
                self.channel.channel_name = None
            for client in self.channel.connected_clients.values():
                self.channel.kicked.append(client.name)
            self.reset_channel()
        self.client.print('The channel has been finalized.')
        self.client.print('Returning to the main menu ...')
        return EOFError()

    def do_history(self, args):
        "Show the entire contents of the channel buffer."
        with self.channel.data_lock:
            buffer = tuple(self.channel.buffer)
        if buffer:
            for line in buffer:
                line.echo(self.client)
        else:
            self.client.print('The channel buffer is empty.')

    def do_owner(self, args):
        "Change the owner of this channel."
        new_owner = args[0] if args else self.client.input('New owner:')
        if not new_owner:
            self.client.print('Cancelling ...')
            return
        if len(args) > 1 or len(new_owner.split()) > 1:
            self.client.print('Username may not have whitespace!')
            return
        with self.channel.data_lock:
            different = new_owner != self.channel.owner
            if different:
                user_exists = OutsideMenu.account_exists(new_owner)
                if user_exists:
                    self.channel.owner = new_owner
        if not different:
            self.client.print(new_owner, 'already owns this channel.')
        elif user_exists:
            self.client.print(new_owner, 'is now the owner of this channel.')
        else:
            self.client.print(new_owner, 'does not have an account.')

    def do_password(self, args):
        "Change the password of this channel."
        if not args:
            self.client.print('Try set or unset.')
            return
        command = args[0]
        if command == 'set':
            word = args[1] if len(args) > 1 else self.client.input('Password:')
            if word:
                with self.channel.data_lock:
                    self.channel.password = word
                self.client.print('Password has been set to:', word)
            else:
                self.client.print('Password may not be empty.')
        elif command == 'unset':
            with self.channel.data_lock:
                self.channel.password = ''
            self.client.print('The password has been cleared.')
        else:
            self.client.print('Try set or unset.')

    def do_purge(self, args):
        "Clear the contents of the channel buffer."
        with self.channel.data_lock:
            self.channel.buffer = []
        self.client.print('The buffer has been cleared.')

    def do_rename(self, args):
        "Give this channel a new name not used by another channel."
        with self.channel.data_lock:
            old_name = self.channel.channel_name
        if old_name is None:
            self.client.print('Deleted channels cannot be renamed.')
            return
        new_name = args[0] if args else self.client.input('New name:')
        if not new_name:
            self.client.print('Cancelling ...')
            return
        if len(args) > 1 or len(new_name.split()) > 1:
            self.client.print('Channel name may not have whitespace!')
            return
        exists, success = self.try_rename(new_name)
        self.show_rename_result(exists, success, new_name)

    def do_replay(self, args):
        "Set the replay size of this channel."
        size = ChannelServer.get_size(self.client, args)
        with self.channel.data_lock:
            self.channel.replay_size = size

    def do_reset(self, args):
        "Make the channel like new again with nothing in it."
        with self.channel.data_lock:
            self.channel.status = ChannelServer.state.reset
            for client in self.channel.connected_clients.values():
                self.channel.kicked.append(client.name)
            self.reset_channel()
        self.client.print('Channel has been reset, and you are its owner.')

    def do_settings(self, args):
        "Show channel owner, password, buffer size, and replay size."
        with self.channel.data_lock:
            owner = self.channel.owner
            password = self.channel.password
            buffer_size = self.channel.buffer_size
            replay_size = self.channel.replay_size
        self.client.print('Owner:      ', owner)
        self.client.print('Password:   ', password)
        size = 'Infinite' if buffer_size is None else buffer_size
        self.client.print('Buffer size:', size)
        size = 'Infinite' if replay_size is None else replay_size
        self.client.print('Replay size:', size)

    ########################################################################

    def reset_channel(self):
        "Restore the channel to a new-like condition."
        self.channel.owner = self.client.name
        self.channel.password = ''
        self.channel.buffer = []
        self.channel.buffer_size = None
        self.channel.replay_size = 10
        self.channel.muted_to_muter = {}
        self.channel.banned = []

    def show_rename_result(self, exists, success, new_name):
        "Show the results of an attempted rename operation."
        if not exists:
            self.client.print('This channel has been deleted.')
            return
        assert success is not None, 'Name was set, but it was not registered.'
        if success:
            self.client.print(new_name, 'is the new name of this channel.')
        else:
            self.client.print('The name', new_name, 'is already in use.')

    def try_rename(self, new_name):
        "Try to rename the channel to a new name."
        success = None
        with self.channel.data_lock:
            old_name = self.channel.channel_name
            exists = old_name is not None
            if exists:
                success = InsideMenu.rename_channel(old_name, new_name)
                if success:
                    self.channel.channel_name = new_name
        return exists, success

################################################################################

class ChannelLine:

    "ChannelLine(source, message) -> ChannelLine instance"

    def __init__(self, source, message):
        "Initialize structure with message and its source."
        self.source = source
        self.message = message

    def echo(self, client):
        "Print a formatted line to the client."
        client.print('[{}] {}'.format(self.source, self.message))

################################################################################

class ContactManager(Handler):

    "ContactManager(client) -> ContactManager instance"

    def handle(self):
        "Show client status of action and run command loop."
        self.client.print('Opening contact manager ...')
        return self.command_loop()

    ########################################################################

    # These are additional commands this handler recognizes.

    def do_add(self, args):
        "Add a friend to your contact list."
        name = args[0] if args else self.client.input('Who?')
        try:
            status = self.client.account.add_contact(name)
        except AssertionError:
            self.client.print(name, 'is already in your contact list.')
        else:
            if status:
                self.client.print(name, 'has been added to your contact list.')
            else:
                self.client.print(name, 'does not currently exist.')

    def do_remove(self, args):
        "Remove someone from your contact list."
        name = args[0] if args else self.client.input('Who?')
        if self.client.account.remove_contact(name):
            self.client.print(name, 'has been removed from your contact list.')
        else:
            self.client.print(name, 'is not in your contact list.')

    def do_show(self, args):
        "Display your friend list with online/offline status."
        self.client.account.show_contacts(self.client, True)

################################################################################

class MessageManager(Handler):

    "MessageManager(client) -> MessageManager instance"

    def handle(self):
        "Show client status of action and run command loop."
        self.client.print('Opening message manager ...')
        return self.command_loop()

    ########################################################################

    # These are additional commands this handler recognizes.

    def do_delete(self, args):
        "Provides various options for deleting your messages."
        data = self.parse_args(args, True)
        if data is not None:
            self.client.account.delete_message(data)
            self.client.print('Deletion has been completed.')

    def do_read(self, args):
        "Allows you to read a message in its entirety."
        data = self.parse_args(args, False)
        if data is not None:
            data.new = False
            self.client.print('From:', data.source)
            self.client.print('=' * 70)
            paragraphs = data.message.split('\n\n')
            for index, section in enumerate(paragraphs):
                for line in textwrap.wrap(section.replace('\n', ' ')):
                    self.client.print(line)
                if index + 1 < len(paragraphs):
                    self.client.print()
            self.client.print('=' * 70)

    def do_send(self, args):
        "Allows you to send a message to someone else."
        name = args[0] if args else self.client.input('Destination:')
        if name == self.client.name:
            self.client.print('You are not allowed to talk to yourself.')
            return
        if not OutsideMenu.account_exists(name):
            self.client.print('Account does not exist.')
            return
        text = self.get_message()
        if not text:
            self.client.print('Empty messages may not be sent.')
            return
        if OutsideMenu.deliver_message(self.client.name, name, text):
            self.client.print('Message has been delivered.')
        else:
            self.client.print(name, 'was removed while you were writing.')

    def do_show(self, args, internal=False):
        "Shows messages summaries with status information."
        data = self.client.account.show_message_summary(self.client, True, 70)
        if internal:
            return data

    ########################################################################

    def find_message(self, args, allow_all):
        "Find a message that the client has requested."
        clue = args[0]
        try:
            index = int(clue) - 1
        except ValueError:
            show = self.client.account.show_message_summary
            if clue in ('read', 'unread'):
                messages = show(self.client, True, 70, filter_status=clue)
            else:
                messages = show(self.client, True, 70, filter_source=clue)
            return self.pick_message(messages, allow_all)
        else:
            with self.client.account.data_lock:
                messages = tuple(self.client.account.messages)
            if 0 <= index < len(messages):
                return messages[index]
            self.client.print('That is not a valid message number.')

    def get_message(self):
        "Get message to send from the client."
        lines = []
        self.client.print('Please compose your message.')
        self.client.print('Enter 2 blank lines to send.')
        self.client.print('=' * 70)
        while lines[-2:] != ['', '']:
            lines.append(self.client.input())
        self.client.print('=' * 70)
        while lines and not lines[0]:
            del lines[0]
        return '\n'.join(lines[:-2])

    def parse_args(self, args, allow_all):
        "Parse the arguments, show messages, and pick them."
        if args:
            return self.find_message(args, allow_all)
        messages = self.do_show(args, True)
        return self.pick_message(messages, allow_all)

    def pick_message(self, messages, allow_all):
        "Pick a message the client wants."
        while messages:
            line = self.client.input('Which one?')
            if not line:
                self.client.print('Cancelling ...')
                break
            if allow_all and line == 'all':
                return messages
            try:
                index = int(line) - 1
                assert 0 <= index < len(messages)
            except (ValueError, AssertionError):
                self.client.print('Please enter a valid message number.')
            else:
                return messages[index]

################################################################################

class Message(ChannelLine):

    "Message(source, message) -> Message instance"

    def __init__(self, source, message):
        "Initialize message that includes new (read/unread) flag."
        super().__init__(source, message)
        self.new = True

################################################################################

class AccountOptions(Handler):

    "AccountOptions(client) -> AccountOptions instance"

    def handle(self):
        "Show client status of action and run command loop."
        self.client.print('Opening account options ...')
        return self.command_loop()

    ########################################################################

    # These are additional commands this handler recognizes.

    def do_delete_account(self, args):
        "Delete your account permanently."
        if args and args[0] == 'force':
            delete = True
        else:
            delete = self.client.input('Seriously?') in ('yes', 'true', '1')
        if delete:
            self.client.print('Your account and connection are being closed.')
            OutsideMenu.delete_account(self.client.name)
            self.client.close()
        self.client.print('Cancelling ...')

    def do_password(self, args):
        "Change your password."
        old = args[0] if args else self.client.input('Old password:')
        account = self.client.account
        with account.data_lock:
            if account.password != old:
                self.client.print('Old password is not correct.')
                return
        new = args[1] if len(args) > 1 else self.client.input('New password:')
        if new:
            with account.data_lock:
                account.password = new
            self.client.print('Your password has been changed.')
        else:
            self.client.print('Your password may not be empty.')

    def do_purge(self, args):
        "Purge your messages, contacts, or both."
        command = args[0] if args else self.client.input('What?')
        if command == 'messages':
            self.client.account.purge_messages()
            self.client.print('All of your messages have been deleted.')
        elif command == 'contacts':
            self.client.account.purge_contacts()
            self.client.print('All of your contacts have been deleted.')
        elif command == 'both':
            self.client.account.purge_messages()
            self.client.account.purge_contacts()
            self.client.print('Your messages and contacts have been deleted.')
        else:
            self.client.print('Try messages, contacts, or both.')

################################################################################
################################################################################

class MarkVShaney(Handler):

    "MarkVShaney(client, buffer, size, channel) -> MarkVShaney instance"

    markov_chain_length = 3
    max_summary_failing = 5

    def __init__(self, client, buffer, size, channel):
        "Initialize the handler for summarizing the channel."
        super().__init__(client)
        self.buffer = buffer
        self.size = size
        self.channel = channel

    def handle(self):
        "Provide a Mark V Shaney summary of the channel and return."
        arrays = self.prepare()
        mcv_len = self.markov_chain_length
        start = tuple(map(lambda words: tuple(words[:mcv_len-1]), arrays))
        stop = tuple(map(lambda words: tuple(words[-mcv_len:]), arrays))
        chains = self.create_chains(arrays)
        cache = self.create_summary(start, stop, chains)
        self.print_summary(cache)
        self.channel.connect(self.client)

    def prepare(self):
        "Process the text into sentences and return them."
        sentences = []
        for line in self.buffer:
            words = line.message.split()
            if len(words) >= self.markov_chain_length:
                sentences.append(tuple(words))
        self.size = min(self.size, len(sentences))
        return tuple(sentences)

    def create_chains(self, arrays):
        "Create the chains uses to create the randomized sentences."
        chains = {}
        for sentence in arrays:
            length = len(sentence)
            if length >= self.markov_chain_length:
                diff = 1 - self.markov_chain_length
                for index in range(length + diff):
                    end = index - diff
                    key = tuple(sentence[index:end])
                    value = sentence[end]
                    if key in chains:
                        chains[key].append(value)
                    else:
                        chains[key] = [value]
        return chains
            
    def create_summary(self, start, stop, chains):
        "Create the random sentences that make up the summary."
        cache = []
        for sentence in range(self.size):
            for attempt in range(self.max_summary_failing):
                sentence = self.create_sentence(start, stop, chains)
                if sentence not in cache:
                    break
            else:
                return cache
            cache.append(sentence)
        return cache

    def create_sentence(self, start, stop, chains):
        "Create a single Markov V Shaney sentence for the summary."
        choice = random.SystemRandom().choice
        sentence = []
        key = choice(start)
        sentence.extend(key)
        while True:
            sentence.append(choice(chains[key]))
            if tuple(sentence[-self.markov_chain_length:]) in stop:
                return ' '.join(sentence)
            key = tuple(sentence[1-self.markov_chain_length:])

    def print_summary(self, cache):
        "Print the summary provided in the given cache."
        if cache:
            line = '~' * max(map(len, cache))
            self.client.print(line)
            for sentence in cache:
                self.client.print(sentence)
            self.client.print(line)
        else:
            self.client.print('There is nothing worth summarizing.')

################################################################################
################################################################################

class MathExpressionEvaluator(Handler):

    "MathExpressionEvaluator(client) -> MathExpressionEvaluator instance"

    def handle(self):
        "Handle math statements provided by the client by looping."
        local = {}
        while True:
            line = self.client.input('Eval:')
            if line in ('exit', 'quit', 'stop'):
                return
            try:
                self.run(line, local)
            except Exception as error:
                self.client.print(error.args[0])

    def run(self, line, local):
        "Execute the line using the local storage."
        lines = self.tokenize(line)
        self.build_operations(lines)
        self.evaluate(lines, local)

    def tokenize(self, line):
        "Parse the line into its individual tokens."
        lines = []
        # replace ';' with line separators
        string = line.replace(';', '\n')
        # the string will be evaluate line-by-line
        for line in string.split('\n'):
            tokens = []
            # ignore empty lines and comments
            if not line or line[0] == '#':
                continue
            # tokens are separated by white-space
            for token in line.split():
                # operations are processed later
                if token in ('=', '+', '-', '*', '/', '//', '%',
                             '**', '^', 'and', '&', 'or', '|',
                             '==', '!=', '>', '<', '>=', '<='):
                    tokens.append(token)
                else:
                    try:
                        # the token is a constant if it can be converted to a float
                        tokens.append(Constant(float(token)))
                    except:
                        # ... otherwise we assume that it is a variable
                        tokens.append(Variable(token))
            lines.append(tokens)
        return lines

    def build_operations(self, lines):
        "Create an expression tree to execute the math statement."
        # now we work on sorting through operations
        for line_index, line in enumerate(lines):
            # assignment is optional on a line
            if '=' in line:
                # split on '=' so each section can be processed
                tokens = self.split(line)
                # single variables must be on the left of '='
                for section in tokens[:-1]:
                    assert len(section) == 1, 'Must Have Single Token'
                    assert isinstance(section[0], Variable), 'Must Assign to Variable'
                # construct an operation from the last tokens
                tokens[-1] = self.flatten(tokens[-1])
                # create as many assignment operations as needed
                op = Operation(tokens[-2][0], '=', tokens[-1])
                for token_index in range(len(tokens) - 3, -1, -1):
                    op = Operation(tokens[token_index][0], '=', op)
                # replace the line with the final operation
                lines[line_index] = op
            else:
                # no assignment? assume evaluation and printing
                op = self.flatten(line)
                lines[line_index] = Print(op, self.client.print)

    def split(self, line):
        "Divide the given tokens on the equal sign."
        # split the tokens in the line on '='
        tokens = []
        while '=' in line:
            index = line.index('=')
            tokens.append(line[:index])
            line = line[index+1:]
        return tokens + [line]

    def flatten(self, tokens):
        "Flatten the operations into a single operation."
        # check for odd number of tokens
        assert len(tokens) % 2 == 1, 'Must Have Odd Number of Tokens'
        toggle = True
        # check the token construction sequence
        for token in tokens:
            if toggle:
                assert isinstance(token, (Constant, Variable)), 'Must Have Constant or Variable'
            else:
                assert isinstance(token, str), 'Must Have Operation'
            toggle = not toggle
        # if there is only one token, it does not need to be flattened
        if len(tokens) == 1:
            return tokens[0]
        # construct the needed operations starting from the beginning
        op = Operation(*tokens[:3])
        for index in range(3, len(tokens), 2):
            op = Operation(op, tokens[index], tokens[index+1])
        return op

    def evaluate(self, lines, local):
        "Execute an evalutation on all of the math expression lines."
        # evaluate the lines in order with the local dictionary
        for line in lines:
            local['_'] = line.Evaluate(local)

################################################################################

class Expression:

    "Expression() -> NotImplementedError exception"

    def __init__(self):
        "This is a base class for math expressions."
        raise NotImplementedError()

    def __repr__(self):
        "Provide a useful representation of the expression object."
        klass = type(self).__name__
        private = '_{}__'.format(klass)
        args = []
        for name in self.__dict__:
            if name.startswith(private):
                value = self.__dict__[name]
                name = name[len(private):]
                args.append('{}={!r}'.format(name, value))
        return '{}({})'.format(klass, ', '.join(args))
    
    def Evaluate(self, dictionary):
        "Expressions should be able to evaluate themselves."
        raise NotImplementedError()

################################################################################

class Constant(Expression):

    "Constant(value) -> Constant instance"

    def __init__(self, value):
        "Initialize the constant with its value."
        self.__value = value

    def Evaluate(self, dictionary):
        "Return the value when evaluated."
        return self.__value

################################################################################

class Variable(Expression):

    "Variable(name) -> Variable instance"

    def __init__(self, name):
        "Initialize the variable with its name."
        self.__name = name

    def Evaluate(self, dictionary):
        "Try to find and return the value of the variable."
        if self.__name not in dictionary:
            raise Exception('Unknown variable: ' + self.__name)
        return dictionary[self.__name]

################################################################################

class Operation(Expression):

    "Operation(left, op, right) -> Operation instance"

    def __init__(self, left, op, right):
        "Initialize the operation with the left and right sides and operator."
        self.__left = left
        self.__op = op
        self.__right = right

    def Evaluate(self, dictionary):
        "Evaluate the operation based on the stored operator."
        if self.__op == '=':
            assert isinstance(self.__left, Variable), 'Must Assign to Variable'
            name = self.__left._Variable__name
            value = self.__right.Evaluate(dictionary)
            dictionary[name] = value
            return value
        x = self.__left.Evaluate(dictionary)
        y = self.__right.Evaluate(dictionary)
        if self.__op == '+':
            return x + y
        if self.__op == '-':
            return x - y
        if self.__op == '*':
            return x * y
        if self.__op == '/':
            return x / y
        if self.__op == '//':
            return x // y
        if self.__op == '%':
            return x % y
        if self.__op == '**':
            return x ** y
        if self.__op == '^':
             return float(int(x) ^ int(y))
        if self.__op == 'and':
            return x and y
        if self.__op == '&':
            return float(int(x) & int(y))
        if self.__op == 'or':
            return x or y
        if self.__op == '|':
            return float(int(x) | int(y))
        if self.__op == '==':
            return float(x == y)
        if self.__op == '!=':
            return float(x != y)
        if self.__op == '>':
            return float(x > y)
        if self.__op == '<':
            return float(x < y)
        if self.__op == '>=':
            return float(x >= y)
        if self.__op == '<=':
            return float(x <= y)
        raise Exception('Unknown operator: ' + self.__op)

################################################################################

class Print(Expression):

    "Print(expression, printer) -> Print instance"

    def __init__(self, expression, printer):
        "Intialize the Print instance with an expression and printer object."
        self.__expression = expression
        self.__print = printer

    def Evaluate(self, dictionary):
        "Print the expression with the printer and return."
        value = self.__expression.Evaluate(dictionary)
        self.__print(value)
        return value

################################################################################
################################################################################

class MathEvaluator2(Handler):

    "MathEvaluator2(client) -> MathEvaluator2 instance"

    def handle(self):
        "Create a math evaluation loop for interacting with the client."
        local = {}
        while True:
            line = self.client.input('>>> ')
            if line in 'exit quit stop'.split():
                break
            try:
                self.evaluate(line, local)
            except Exception:
                error = traceback.format_exception_only(*sys.exc_info()[:2])
                self.client.print(error[-1], end='')

    def evaluate(self, source, local):
        "Execute all math operations found in the source."
        for expression in self.expressions(source):
            local['_'] = self.tokens(expression).evaluate(local)

    def expressions(self, source):
        "Separate expressions and yield each individually."
        lines = source.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        uncommented = map(lambda line: line.split('#', 1)[0], lines)
        for line in uncommented:
            if line and not line.isspace():
                for expression in line.split(';'):
                    yield expression

    def tokens(self, string):
        "Build an expression tree by tokenizing expression."
        evaluator = self._tokens(string)
        if isinstance(evaluator, Operation2) and \
           evaluator._Operation2__symbol == Operation2.ASSIGNMENT:
            return evaluator
        return Print2(evaluator, self.client.print)

    def _tokens(self, string):
        "Private module function: recursively builds a tree."
        expression = string.strip()
        if not expression:
            raise SyntaxError('empty expression')
        divisions = Operation2.split(expression)
        if divisions:
            left, symbol, right = divisions
            return Operation2(self._tokens(left), symbol, self._tokens(right))
        if len(expression.split()) > 1:
            raise SyntaxError(expression)
        if expression.startswith('0x'):
            return Constant2(int(expression[2:], 16))
        if expression.startswith('0d'):
            return Constant2(int(expression[2:], 10))
        if expression.startswith('0o'):
            return Constant2(int(expression[2:], 8))
        if expression.startswith('0q'):
            return Constant2(int(expression[2:], 4))
        if expression.startswith('0b'):
            return Constant2(int(expression[2:], 2))
        if expression.isdigit():
            return Constant2(int(expression))
        if expression.isidentifier():
            return Variable2(expression)
        raise SyntaxError(expression)

################################################################################

class Expression2:

    "Abstract class for Expression objects."

    def __init__(self):
        "Initialize the Expression object."
        raise NotImplementedError()

    def __repr__(self):
        "Return a representation of this object."
        klass = type(self).__name__
        private = '_{}__'.format(klass)
        args = []
        for name in vars(self):
            if name.startswith(private):
                key = name[len(private):]
                value = getattr(self, name)
                args.append('{}={!r}'.format(key, value))
        return '{}({})'.format(klass, ', '.join(args))

    def evaluate(self, bindings):
        "Calculate the value of this object."
        raise NotImplementedError()

################################################################################

class Constant2(Expression2):

    "Class for storing all math constants."

    def __init__(self, value):
        "Initialize the Constant object."
        self.__value = value

    def evaluate(self, bindings):
        "Calculate the value of this object."
        return self.__value

################################################################################

class Variable2(Expression2):

    "Class for storing all math variables."

    def __init__(self, name):
        "Initialize the Variable object."
        self.__name = name

    def evaluate(self, bindings):
        "Calculate the value of this object."
        if self.__name not in bindings:
            raise NameError(self.__name)
        return bindings[self.__name]

################################################################################

class Operation2(Expression2):

    "Class for executing math operations."

    ASSIGNMENT = '->'
    OPERATORS = {ASSIGNMENT: lambda a, b: None,
                 '&&': lambda a, b: a and b,
                 '||': lambda a, b: a or b,
                 '+': operator.add,
                 '-': operator.sub,
                 '*': operator.mul,
                 '/': operator.floordiv,
                 '%': operator.mod,
                 '**': operator.pow,
                 '&': operator.and_,
                 '|': operator.or_,
                 '^': operator.xor,
                 '>>': operator.rshift,
                 '<<': operator.lshift,
                 '==': operator.eq,
                 '!=': operator.ne,
                 '>': operator.gt,
                 '>=': operator.ge,
                 '<': operator.lt,
                 '<=': operator.le}

    def __init__(self, left, symbol, right):
        "Initialize the Operation object."
        self.__left = left
        self.__symbol = symbol
        self.__right = right

    def evaluate(self, bindings):
        "Calculate the value of this object."
        if self.__symbol == self.ASSIGNMENT:
            if not isinstance(self.__right, Variable2):
                raise TypeError(self.__right)
            key = self.__right._Variable2__name
            value = self.__left.evaluate(bindings)
            bindings[key] = value
            return value
        return self.__operate(bindings)

    def __operate(self, bindings):
        "Execute operation defined by symbol."
        if self.__symbol not in self.OPERATORS:
            raise SyntaxError(self.__symbol)
        a = self.__left.evaluate(bindings)
        b = self.__right.evaluate(bindings)
        return self.OPERATORS[self.__symbol](a, b)

    __operators = sorted(OPERATORS, key=len, reverse=True)

    @classmethod
    def split(cls, expression):
        "Split expression on rightmost symbol."
        tail = cls.__split(expression)
        if tail:
            symbol, right = tail
            return expression[:-sum(map(len, tail))], symbol, right

    @classmethod
    def __split(cls, expression):
        "Private class method: help with split."
        for symbol in cls.__operators:
            if symbol in expression:
                right = expression.rsplit(symbol, 1)[1]
                tail = cls.__split(right)
                if tail is None:
                    return symbol, right
                return tail

################################################################################

class Print2(Expression2):

    "Class for printing all math results."

    def __init__(self, expression, printer):
        "Initialize the Print object."
        self.__expression = expression
        self.__print = printer

    def evaluate(self, bindings):
        "Calculate the value of this object."
        value = self.__expression.evaluate(bindings)
        self.__print(value)
        return value

################################################################################
################################################################################

if __name__ == '__main__':
    main('.')
