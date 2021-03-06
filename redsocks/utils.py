# -*- coding: utf-8 -*-
import six

# Try to import uwsgi. When running the dev server via redsocks.runserver.server,
# this is not needed. So we can simply set it to none to make imports heppy.
try:
    import uwsgi
except:
    uwsgi = None


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
