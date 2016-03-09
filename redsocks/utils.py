# -*- coding: utf-8 -*-
import six


def to_bytes(value):
    if six.PY3 and isinstance(value, bytes): return value
    if six.PY3 and isinstance(value, str): return value.encode()
    return value
    

def to_str(value):
    if six.PY3 and isinstance(value, bytes): return value.decode()
    if six.PY3 and isinstance(value, str): return value
    return value
