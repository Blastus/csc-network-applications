#! /usr/bin/env python3
import threading
import heapq

################################################################################

class Group:

    def __init__(self, keyword, euphemisms):
        self.keyword = keyword
        self.euphemisms = euphemisms

    def copy(self):
        return Group(self.keyword, self.euphemisms.copy())

################################################################################

class DoubleTalk:

    def __init__(self, max_frag=0.1):
        assert 0 <= max_frag <= 0.9
        self.__max_frag = max_frag
        self.__index = {}
        self.__table = []
        self.__empty = []
        self.__mutex = threading.Lock()

    def word_count(self):
        with self.__mutex:
            return len(self.__index)

    def group_count(self):
        with self.__mutex:
            return len(self.__table) - len(self.__empty)

    def word_iter(self):
        with self.__mutex:
            return iter(self.__index)

    def group_iter(self):
        with self.__mutex:
            return map(Euphemism.copy, filter(None, self.__table))

    def __contains__(self, key):
        with self.__mutex:
            return key in self.__index

    def __getitem__(self, key):
        with self.__mutex:
            return self.__table[self.__index[key]].euphemisms.copy()

    def __setitem__(self, key, value):
        self.group(key, value)

    def group(self, key, value, merge=False):
        with self.__mutex:
            if key not in self.__index:
                key, value = value, key
            if key not in self.__index:
                if self.__empty:
                    index = heapq.heappop(self.__empty)
                    self.__table[index] = Group(value, {key, value})
                else:
                    index = len(self.__table)
                    self.__table.append(Group(value, {key, value}))
                self.__index[key] = index
                self.__index[value] = index
            elif value not in self.__index:
                index = self.__index[key]
                self.__table[index].euphemisms.add(value)
                self.__index[value] = index
            else:
                key = self.__index[key]
                value = self.__index[value]
                if key != value:
                    assert merge, 'Cannot Merge Separate Groups'
                    if key > value:
                        key, value = value, key
                        self.__table[key].keyword = self.__table[value].keyword
                    group = self.__table[value]
                    self.__table[key].euphemisms.update(group.euphemisms)
                    for obj in group.euphemisms:
                        self.__index[obj] = key
                    self.__delete(value)

    def __delitem__(self, key):
        with self.__mutex:
            index = self.__index[key]
            group = self.__table[index]
            if key == group.keyword and len(group.euphemisms) > 1:
                raise KeyError('Cannot Delete Keyword')
            del self.__index[key]
            group.euphemisms.remove(key)
            if not group.euphemisms:
                self.__delete(index)

    def __delete(self, index):
        self.__table[index] = None
        heapq.heappush(self.__empty, index)
        table = len(self.__table)
        empty = len(self.__empty)
        if empty / table > self.__max_frag:
            for index in range(table - empty):
                if self.__table[index] is None:
                    for table in range(table - 1, index, -1):
                        if self.__table[table] is not None:
                            break
                    group = self.__table[index] = self.__table[table]
                    for obj in group.euphemisms:
                        self.__index[obj] = index
            del self.__table[-empty:]
            del self.__empty[:]

    def translate(self, key):
        with self.__mutex:
            if key in self.__index:
                return self.__table[self.__index[key]].keyword
            return key

    def set_keyword(self, key):
        with self.__mutex:
            self.__table[self.__index[key]].keyword = key
