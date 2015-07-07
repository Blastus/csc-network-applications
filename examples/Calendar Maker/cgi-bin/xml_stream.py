'''Module for XML event streams.

This module provides several classes for creating,
saving, and delaying the processing of XML events.'''

__version__ = '1.0'

import os as _os
import sys as _sys
import xml.sax as _xml_sax

################################################################################

class Event:

    'Event(*args) -> Event'

    def __init__(self, *args):
        'Initialize the Event object.'
        self.__args = args

    def __repr__(self):
        'Return the object\'s representation.'
        return '%s(%s)' % (self.__class__.__name__, ', '.join(map(repr, self.__args)))

    def __call__(self, handler=None):
        'Either return arguments or process handler.'
        if handler is None:
            return self.__args
        else:
            getattr(handler, self.__class__.__name__)(*self.__args)

class setDocumentLocator(Event): pass
class startDocument(Event): pass
class endDocument(Event): pass
class startPrefixMapping(Event): pass
class endPrefixMapping(Event): pass
class startElement(Event): pass
class endElement(Event): pass
class startElementNS(Event): pass
class endElementNS(Event): pass
class characters(Event): pass
class ignorableWhitespace(Event): pass
class processingInstruction(Event): pass
class skippedEntity(Event): pass

################################################################################

class Stream:

    'Stream(filename_or_stream_or_string) -> Stream'

    def __init__(self, filename_or_stream_or_string):
        'Initialize the Stream object.'
        self.__stream = []
        if isinstance(filename_or_stream_or_string, str):
            if _os.path.exists(filename_or_stream_or_string):
                _xml_sax.parse(filename_or_stream_or_string, self)
            else:
                _xml_sax.parseString(filename_or_stream_or_string.encode(), self)
        else:
            _xml_sax.parse(filename_or_stream_or_string, self)
        self.__maximized = self.__minimized = False

    def __getattr__(self, name):
        'Dynamically create and bind Methods.'
        self.__dict__[name] = Method(self.__stream, name)
        return self.__dict__[name]

    def __iter__(self):
        'Return an iterator.'
        return iter(self.__stream)

    def parse(self, handler):
        'Simulate events on a handler.'
        for event in self:
            event(handler)

    def maximize(self, style):
        'Prepare the stream for printing.'
        if not self.__maximized:
            self.minimize()
            self.__minimized = False
            self.__maximized = True
            if isinstance(self.__stream[0], setDocumentLocator):
                index =  2
            else:
                index =  1
            level = 0
            cancel = False
            while True:
                event = self.__stream[index]
                if isinstance(event, (startPrefixMapping, startElement, startElementNS)):
                    self.__stream.insert(index, characters(style * level))
                    index += 2
                    if not isinstance(self.__stream[index], (endDocument, endPrefixMapping, endElement, endElementNS)):
                        self.__stream.insert(index, characters('\n'))
                        index += 1
                        level += 1
                elif isinstance(event, (endPrefixMapping, endElement, endElementNS)):
                    if not isinstance(self.__stream[index - 1], (startDocument, startPrefixMapping, startElement, startElementNS)):
                        level -= 1
                        if cancel:
                            cancel = False
                            index += 1
                        else:
                            self.__stream.insert(index, characters(style * level))
                            index += 2
                    else:
                        index += 1
                    self.__stream.insert(index, characters('\n'))
                    index += 1
                elif isinstance(event, endDocument):
                    break
                elif isinstance(event, characters):
                    del self.__stream[index - 1]
                    cancel = True

    def minimize(self):
        'Prepare the stream for data extraction.'
        if not self.__minimized:
            self.__maximized = False
            self.__minimized = True
            if isinstance(self.__stream[0], setDocumentLocator):
                index = 2
            else:
                index = 1
            inside = True
            while index < len(self.__stream):
                event = self.__stream[index]
                if isinstance(event, (startPrefixMapping, startElement, startElementNS)):
                    inside = True
                    index = self.__prune(index)
                elif isinstance(event, (endDocument, endPrefixMapping, endElement, endElementNS)):
                    if inside:
                        inside = False
                        index = self.__join(index)
                    else:
                        index = self.__prune(index)
                index += 1

    def __prune(self, index):
        'Private class method.'
        temp = index - 1
        event = self.__stream[temp]
        while not isinstance(event, (startDocument, startPrefixMapping, endPrefixMapping, startElement, endElement, startElementNS, endElementNS)):
            if isinstance(event, characters):
                del self.__stream[temp]
                index -= 1
            temp -= 1
            event = self.__stream[temp]
        return index

    def __join(self, index):
        'Private class method.'
        temp = index - 1
        event_1 = self.__stream[temp]
        while not isinstance(event_1, (startDocument, startPrefixMapping, startElement, startElementNS)):
            if isinstance(event_1, characters):
                event_2 = self.__stream[temp - 1]
                if isinstance(event_2, characters):
                    self.__stream[temp] = characters(event_2()[0] + event_1()[0])
                    del self.__stream[temp - 1]
                    index -= 1
            temp -= 1
            event_1 = self.__stream[temp]
        return index

################################################################################

class Method:

    'Method(stream, name) -> Method'

    def __init__(self, stream, name):
        'Initialize the Method object.'
        self.__stream = stream
        self.__name = name

    def __call__(self, *args):
        'Dynamically create and add events to the stream.'
        self.__stream.append(globals()[self.__name](*args))

################################################################################

if __name__ == '__main__':
    _sys.stdout.write('Content-Type: text/plain\n\n')
    _sys.stdout.write(file(_sys.argv[0]).read())
