#! /usr/bin/env python3
"""Provide a GUI for easy interactions with Multichat servers.

This program provides a simple way to connect to a Multichat server, send
and receive text, and automatically discover menus the server may support."""

__author__ = 'Stephen "Zero" Chappell <Noctis.Skytower@gmail.com>'
__date__ = '11 October 2012'
__version__ = 1, 0, 0

################################################################################

from safetkinter import *
from tkinter.constants import *
import tkinter.messagebox
import socket
import sys
import os
import logging
import traceback
import _thread
import threadbox
import json

################################################################################

APP_TITLE = 'Multichat Client 1.1'

################################################################################

class MultichatClient(Frame):

    "MultichatClient(master) -> MultichatClient instance"

    after_handle = None

    @classmethod
    def main(cls):
        "Create a GUI root and demonstrate the MultichatClient widget."
        root = Tk()
        root.title(APP_TITLE)
        root.minsize(670, 370)
        cls(root).grid(row=0, column=0, sticky=NSEW)
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
        root.mainloop()

    def __init__(self, master):
        "Initialize the MultichatClient instance with its internal widgets."
        super().__init__(master)
        self.message_area = ScrolledText(self, width=81, height=21,
                                         wrap=WORD, state=DISABLED)
        self.message_area.grid(row=0, column=0, sticky=NSEW, columnspan=2)
        self.send_area = Entry(self)
        self.send_area.bind('<Return>', self.send)
        self.send_area.grid(row=1, column=0, sticky=EW)
        Sizegrip(self).grid(row=1, column=1, sticky=SE)
        self.send_area.focus_set()
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.after_idle(self.setup_start)

    def destroy(self):
        "Cancel any updates before destructing this widget."
        if self.after_handle:
            self.after_cancel(self.after_handle)
        super().destroy()

    def setup_start(self):
        "Begin by creating a prompt window and registering a callback."
        root = self._root()
        root.withdraw()
        Prompt(root, self.setup_stop)

    def setup_stop(self, connection):
        "Close the widget if there was no connection; else begin chatting."
        root = self._root()
        if connection:
            self.options = Option(root, connection)
            self.after_handle = self.after_idle(self.refresh)
            root.deiconify()
            self.last_x, self.last_y = root.winfo_x(), root.winfo_y()
            root.after(1, root.bind, '<Configure>', self.move_options)
        else:
            root.destroy()

    def refresh(self):
        "Try to update the message area ten times a second."
        try:
            s = self.options.input()
        except socket.error:
            pass
        else:
            self.message_area['state'] = NORMAL
            self.message_area.insert(END, s)
            self.message_area['state'] = DISABLED
            self.message_area.see(END)
        self.after_handle = self.after(100, self.refresh)

    def send(self, event):
        "Send a message across the connection and clear the input area."
        self.options.print(self.send_area.get())
        self.send_area.delete(0, END)

    def move_options(self, event):
        "Move the Option window with the root as the root is adjusted."
        self.options.geometry('+{}+{}'.format(
            self.options.winfo_x() + event.x - self.last_x,
            self.options.winfo_y() + event.y - self.last_y))
        self.last_x, self.last_y = event.x, event.y

################################################################################

class Entry(Entry):

    "Entry(master, **kw) -> Entry instance"

    def __init__(self, master, **kw):
        "Initialize the Entry widget with custom default bindings."
        super().__init__(master, **kw)
        self.bind('<Control-a>', self.handle_control_a)
        self.bind('<Control-/>', lambda event: 'break')

    @staticmethod
    def handle_control_a(event):
        "Select all of the text in the widget."
        event.widget.selection_range(0, END)
        return 'break'

################################################################################

class ScrolledText(ScrolledText):

    "ScrolledText(master, **kw) -> ScrolledText instance"

    def __init__(self, master, **kw):
        "Initialize the ScrolledText widget with custom default bindings."
        super().__init__(master, **kw)
        self.bind('<Control-a>', self.handle_control_a)
        self.bind('<Control-/>', lambda event: 'break')

    @staticmethod
    def handle_control_a(event):
        "Select all of the text in the widget."
        event.widget.tag_add(SEL, 1.0, END + '-1c')
        return 'break'

################################################################################

def debug(function, *args, **kwargs):
    "Run a function with debugging enabled (automatic exception logging)."
    try:
        return function(*args, **kwargs)
    except Exception:
        basename = os.path.basename(sys.argv[0])
        filename = os.path.splitext(basename)[0] + '.log'
        logging.basicConfig(filename=filename)
        etype, value, tb = sys.exc_info()
        lines = traceback.format_exception(etype, value, tb.tb_next)
        logging.error(''.join(lines))
        raise

def thread(function, *args, **kwargs):
    "Run a function in a new thread of execution with debug support."
    _thread.start_new_thread(debug, (function,) + args, kwargs)

################################################################################

class Prompt(Toplevel):

    "Prompt(master, callback) -> Prompt instance"

    def __init__(self, master, callback):
        "Initialize the Prompt window with its widgets."
        super().__init__(master)
        self.callback = callback
        self.response = None
        self.title(APP_TITLE)
        self.resizable(False, False)
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        self.geometry('+{}+{}'.format(master.winfo_rootx() + 50,
                                      master.winfo_rooty() + 50))
        Label(self, text="What is the server's IP address?")\
            .grid(padx=40, pady=5)
        self.address = Entry(self)
        self.address.grid(padx=40, pady=5)
        self.address.focus_set()
        Button(self, text='Connect', width=10, command=self.connect_start,
               default=ACTIVE).grid(sticky=E, padx=5, pady=5)
        self.bind('<Return>', self.connect_start)
        self.bind('<Escape>', self.destroy)

    def destroy(self, event=None):
        "Run the callback with the collected response and destruct."
        self.master.after_idle(self.callback, self.response)
        super().destroy()

    def connect_start(self, event=None):
        "Create a Status window to handle the connection process."
        self.withdraw()
        Status(self, self.connect_stop, self.address.get())

    def connect_stop(self, connection):
        "Collect the response from the Status window and proceed."
        if isinstance(connection, socket.socket):
            self.response = connection
            self.destroy()
        else:
            self.deiconify()
            if isinstance(connection, Exception):
                Message(self, title='Connection Error',
                        icon=tkinter.messagebox.ERROR,
                        type=tkinter.messagebox.OK,
                        message=connection.args[0]).show()

################################################################################

class Status(Toplevel):

    "Status(master, callback, host) -> Status instance"

    def __init__(self, master, callback, host):
        "Initialize the Status window with its widgets and try connecting."
        super().__init__(master)
        self.callback = callback
        self.title(APP_TITLE)
        self.resizable(False, False)
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        self.geometry('+{}+{}'.format(master.winfo_rootx() + 50,
                                      master.winfo_rooty() + 50))
        Label(self, text='Trying to connect to address ...')\
            .grid(sticky=W, padx=40, pady=5)
        indicator = Progressbar(self, orient=HORIZONTAL,
                                mode='indeterminate', maximum=30)
        indicator.grid(sticky=EW, padx=40, pady=5)
        indicator.start()
        thread(self.connect, host)

    def destroy(self, result=None):
        "Send a response back to the Prompt window when finished."
        if not self.destroyed:
            self.master.after_idle(self.callback, result)
            super().destroy()

    @property
    def destroyed(self):
        "Find out if this window has already been destroyed."
        return self._tclCommands is None

    @threadbox.MetaBox.thread
    def connect(self, host):
        "Try connecting to the host using a thread and return the result."
        try:
            result = socket.create_connection((host, 8989), 10)
        except socket.gaierror:
            result = Exception('Could not find host {!r}.'.format(host))
        except socket.error:
            result = Exception('Could not connect to host {!r}.'.format(host))
        self.destroy(result)

################################################################################

class Option(Toplevel):

    "Option(master, connection) -> Option instance"

    response = ''

    def __init__(self, master, connection):
        "Initialize the Option instance with a connection it should handle."
        super().__init__(master)
        connection.setblocking(False)
        self.connection = connection
        self.title('Menu')
        self.resizable(False, False)
        self.protocol('WM_DELETE_WINDOW', self.master.destroy)
        self.geometry('+{}+{}'.format(master.winfo_rootx() +
                                      master.winfo_width() + 13,
                                      master.winfo_rooty() - 25))
        self.refreshing = _thread.allocate_lock()
        self.after(200, thread, self.refresh)

    def print(self, value):
        "Try sending a value over the connection."
        with self.refreshing:
            self.send(value)
            self.after(200, thread, self.refresh)

    def input(self):
        "Try receiving some data from the server."
        with self.refreshing:
            return self.recv()

    @threadbox.MetaBox.thread
    def refresh(self):
        "Refresh the menu if appropriate at the time."
        response = self.response.strip()
        if any(response.endswith(suffix) for suffix in
               ('Command:', 'is connected.')):
            self.refreshing.acquire()
            self.connection.settimeout(1)
            try:
                self.send(':__json_help__')
                commands = json.loads(self.recv().strip())
            except (ValueError, socket.timeout):
                commands = None
            self.connection.setblocking(False)
            self.refreshing.release()
            if commands:
                self.remove_widgets()
                self.create_widgets(commands,
                    ':' if response.endswith('is connected.') else '')

    @threadbox.MetaBox.thread
    def send(self, value):
        "Send a properly encoded string over the connection."
        self.connection.sendall(value.encode() + b'\r\n')

    @threadbox.MetaBox.thread
    def recv(self):
        "Decode and format incoming data from the connection."
        self.response = self.connection.recv(1 << 12).decode()\
                        .replace('\r\n', '\n').replace('\r', '\n')
        return self.response

    def remove_widgets(self):
        "Destroy all widgets this window contains."
        for widget in tuple(self.children.values()):
            widget.destroy()

    def create_widgets(self, commands, prefix):
        "Create the buttons and labels that make up the menu."
        bind = lambda name: lambda: self.print(prefix + name)
        for row, name in enumerate(sorted(commands)):
            Button(self, text=name, command=bind(name))\
                .grid(row=row, column=0, padx=2, pady=2)
            Label(self, text=commands[name])\
                .grid(row=row, column=1, padx=2, pady=2, sticky=W)

################################################################################

if __name__ == '__main__':
    debug(MultichatClient.main)
