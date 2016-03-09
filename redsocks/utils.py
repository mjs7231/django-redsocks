# -*- coding: utf-8 -*-
import six


def to_bytes(value):
    if six.PY3 and isinstance(value, bytes): return value
    if six.PY3 and isinstance(value, str): return value.encode()
    if six.PY2 and isinstance(value, six.string_types): return value
    return None
    

def to_str(value):
    if six.PY3 and isinstance(value, bytes): return value.decode()
    if six.PY3 and isinstance(value, str): return value
    if six.PY2 and isinstance(value, six.string_types): return value
    return None
