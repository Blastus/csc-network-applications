#! /usr/bin/env python3
from _thread import allocate_lock

################################################################################

class CATServer:

    __slots__ = '_mutex _index _group _value'.split()

    def __init__(self, *, _parent=None, _value=''):
        "Intitalize the CATServer object."
        if _parent is None:
            self._mutex = allocate_lock()
            self._index = dict()
            self._group = dict()
        else:
            self._mutex = _parent._mutex
            self._index = _parent._index
            self._group = _parent._group
        self._value = _value

    def __repr__(self):
        "Return representation of this object."
        return '{}(){}'.format(type(self).__name__, \
                               self._value and '.' + self._value or '')

    def __getattr__(self, name):
        "Get a CATServer subcategory."
        value = self._value and self._value + '.' + name or name
        return CATServer(_parent=self, _value=value)

    def __delattr__(self, name):
        "Delete a CATServer subcategory."
        value = self._value and self._value + '.' + name or name
        with self._mutex:
            if value in self._group:
                for item in self._group[value]:
                    del self._index[item]
                del self._group[value]

    def __call__(self):
        "Split a _CATShard object."
        pass

    def __len__(self):
        "Get this category's size."
        with self._mutex:
            if self._value in self._group:
                return len(self._group[self._value])
        return 0

    def __getitem__(self, item):
        "Store item in category."
        with self._mutex:
            assert item not in self._index, 'Item Was Already Categorized'
            self._index[item] = self._value
            if self._value in self._group:
                self._group[self._value].add(item)
            else:
                self._group[self._value] = {item}
        return item

    def __delitem__(self, item):
        "Delete item in category."
        with self._mutex:
            assert item in self._index and self._index[item] == self._value, \
                   'Item Is Not In This Category'
            self._group[self._value].remove(item)
            del self._index[item]

    def __iter__(self):
        "Return a category iterator."
        with self._mutex:
            if self._value in self._group:
                return iter(tuple(self._group[self._value]))
        return iter(())
        

    def __contains__(self, item):
        "Check for item's presence."
        with self._mutex:
            if item in self._index:
                return self._index[item] == self._value
        return False

################################################################################

class _CATShard:

    __slots__ = '_mutex _index _group _value'.split()

    def __init__(self, *, _parent=None, _value=''):
        "Intitalize the _CATShard object."
        if _parent is None:
            self._mutex = allocate_lock()
            self._index = dict()
            self._group = dict()
        else:
            self._mutex = _parent._mutex
            self._index = _parent._index
            self._group = _parent._group
        self._value = _value

    def __repr__(self):
        "Return representation of this object."
        return '{}(){}'.format(type(self).__name__, \
                               self._value and '.' + self._value or '')

    def __getattr__(self, name):
        "Get a _CATShard subcategory."
        value = self._value and self._value + '.' + name or name
        return CATServer(_parent=self, _value=value)

    def __delattr__(self, name):
        "Delete a _CATShard subcategory."
        value = self._value and self._value + '.' + name or name
        with self._mutex:
            if value in self._group:
                for item in self._group[value]:
                    del self._index[item]
                del self._group[value]

    def __call__(self):
        "Join parent CATServer object."
        pass

    def __len__(self):
        "Get this category's size."
        with self._mutex:
            if self._value in self._group:
                return len(self._group[self._value])
        return 0

    def __getitem__(self, item):
        "Store item in category."
        with self._mutex:
            assert item not in self._index, 'Item Was Already Categorized'
            self._index[item] = self._value
            if self._value in self._group:
                self._group[self._value].add(item)
            else:
                self._group[self._value] = {item}
        return item

    def __delitem__(self, item):
        "Delete item in category."
        with self._mutex:
            assert item in self._index and self._index[item] == self._value, \
                   'Item Is Not In This Category'
            self._group[self._value].remove(item)
            del self._index[item]

    def __iter__(self):
        "Return a category iterator."
        with self._mutex:
            if self._value in self._group:
                return iter(tuple(self._group[self._value]))
        return iter(())
        

    def __contains__(self, item):
        "Check for item's presence."
        with self._mutex:
            if item in self._index:
                return self._index[item] == self._value
        return False
