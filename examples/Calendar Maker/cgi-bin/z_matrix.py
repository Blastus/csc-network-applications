'''Module for arrays and matrices.

This module provides the Array and Matrix classes
which create mutable storage with immutable size.'''

__version__ = 1.0

################################################################################

class Array:

    'Array(length[, value]) -> Array'

    def __init__(self, length, value=None):
        'Initialize the Array object.'
        assert isinstance(length, int) and length > 0
        self.__data = [value] * length

    def __repr__(self):
        'Return the object\'s representation.'
        return repr(self.__data)

    def __len__(self):
        'Return the object\'s length.'
        return len(self.__data)

    def __getitem__(self, key):
        'Return the specified item.'
        return self.__data[key]

    def __setitem__(self, key, value):
        'Assign the value to the key.'
        self.__data[key] = value

    def __delitem__(self, key):
        'Delete the specified item.'
        self.__data[key] = None

    def __itet__(self):
        'Return the object\'s iterator.'
        return iter(self.__data)

    def __contains__(self, item):
        'Return the item\'s membership status.'
        return item in self.__data

class Matrix:

    'Matrix(rows, columns[, value]) -> Matrix'

    def __init__(self, rows, columns, value=None):
        'Initialize the Matrix object.'
        assert isinstance(rows, int) and rows > 0
        self.__data = [Array(columns, value) for row in range(rows)]
        
    def __repr__(self):
        'Return the object\'s representation.'
        return repr(self.__data)

    def __len__(self):
        'Return the object\'s length.'
        return len(self.__data)

    def __getitem__(self, key):
        'Return the specified item.'
        return self.__data[key]

    def __setitem__(self, key, value):
        'Assign the value to the key.'
        self.__data[key] = Array(len(self.__data[key]), value)

    def __delitem__(self, key):
        'Delete the specified item.'
        self.__data[key] = Array(len(self.__data[key]))

    def __iter__(self):
        'Return the object\'s iterator.'
        return iter(self.__data)

    def __contains__(self, item):
        'Return the item\'s membership status.'
        for row in self.__data:
            if item in row:
                return True
        return False

################################################################################

if __name__ == '__main__':
    import sys
    sys.stdout.write('Content-Type: text/plain\n\n' + file(sys.argv[0]).read())
