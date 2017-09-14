# -*- coding: utf-8 -*-
"""
Django-Redsox Project 2016
"""
import django
django.setup()

import re
import gevent.select
from collections import deque
from django import http
from django.conf import settings
from django.contrib.auth import get_user
from django.core.handlers.wsgi import WSGIRequest
from django.utils.encoding import force_str
from django.utils.functional import SimpleLazyObject
from importlib import import_module
from redis import StrictRedis
from redsocks import log, utils
from redsocks import settings as rsettings
from redsocks.exceptions import HandshakeError
from redsocks.utils import uwsgi
from redsocks.websocket import uWSGIWebsocket
from six.moves import http_client

BYTES_HEARTBEAT = utils.to_bytes(settings.REDSOCKS_HEARTBEAT)


class uWSGIWebsocketServer(object):
    
    def __init__(self, redis_client=None):
        self._subscribers = [(re.compile(p), s) for p,s in rsettings.REDSOCKS_SUBSCRIBERS.items()]
        self.redis_client = redis_client or StrictRedis(**rsettings.REDSOCKS_CONNECTION)

    def assert_protocol_requirements(self, environ):
        if environ.get('REQUEST_METHOD') != 'GET':
            raise HandshakeError('HTTP method must be a GET')
        if environ.get('SERVER_PROTOCOL') != 'HTTP/1.1':
            raise HandshakeError('HTTP server protocol must be 1.1')
        if environ.get('HTTP_UPGRADE', '').lower() != 'websocket':
            raise HandshakeError('Client does not wish to upgrade to a websocket')

    def find_subscriber(self, request):
        """ Lookup subscriber class from facility string. """
        facility = request.path_info.replace(rsettings.WEBSOCKET_URL, '', 1)
        for pattern, substr in self._subscribers:
            matches = [pattern.match(facility)]
            if list(filter(None, matches)):
                comps = str(substr).split('.')
                module = import_module('.'.join(comps[:-1]))
                subcls = getattr(module, comps[-1])
                return subcls(self.redis_client)
        # Found no matching subscribers, raise error
        raise HandshakeError('Unknown facility: %s' % facility)
    
    def process_request(self, request):
        request.session = None
        request.user = None
        session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME, None)
        if session_key is not None:
            engine = import_module(settings.SESSION_ENGINE)
            request.session = engine.SessionStore(session_key)
            request.user = SimpleLazyObject(lambda: get_user(request))
            
    def process_channels(self, request, subscriber):
        channels, echo = [], False
        for channel in request.GET:
            if channel == 'echo':
                echo = True; continue
            channel = channel.strip().lower()
            channels.append(channel)
        # allow the subscriber class to limit channels
        channels = subscriber.allowed_channels(request, channels)
        log.info('Subscribed to channels: %s', ','.join(channels))
        return channels, echo
    
    def select(self, rlist, wlist, xlist, timeout=None):
        return gevent.select.select(rlist, wlist, xlist, timeout)
        
    def upgrade_websocket(self, environ, start_response):
        uwsgi.websocket_handshake(environ['HTTP_SEC_WEBSOCKET_KEY'], environ.get('HTTP_ORIGIN', ''))
        return uWSGIWebsocket()

    def __call__(self, environ, start_response):
        """ Hijack the main loop and listen on events on the Redis and the Websocket fds. """
        websocket = None
        request = WSGIRequest(environ)
        subscriber = self.find_subscriber(request)
        try:
            self.assert_protocol_requirements(environ)
            self.process_request(request)
            channels, echo = self.process_channels(request, subscriber)
            websocket = self.upgrade_websocket(environ, start_response)
            subscriber.set_pubsub_channels(request, channels)
            websocket_fd = websocket.get_file_descriptor()
            redis_fd = subscriber.get_file_descriptor()
            listening_fds = [fd for fd in (websocket_fd, redis_fd) if fd]
            subscriber.on_connect(request, websocket)
            recent = deque(maxlen=10)
            while websocket and not websocket.closed:
                ready = self.select(listening_fds, [], [], 4.0)[0]
                if not ready:
                    websocket.flush()
                for fd in ready:
                    if fd == websocket_fd:
                        recvmsg = utils.to_bytes(websocket.receive())
                        if recvmsg and recvmsg == BYTES_HEARTBEAT:
                            websocket.send(recvmsg)
                        elif recvmsg:
                            recvmsg = subscriber.on_receive_message(request, websocket, recvmsg)
                            subscriber.publish_message(recvmsg)
                            recent.append(recvmsg)
                    elif fd == redis_fd:
                        sendmsg = subscriber.subscription.parse_response()
                        sendmsg = utils.to_bytes(sendmsg[2])
                        if sendmsg and (echo or sendmsg not in recent):
                            sendmsg = subscriber.on_send_message(request, websocket, sendmsg)
                            websocket.send(sendmsg)
                    else:
                        log.error('Invalid file descriptor: %s', fd)
            response = http.HttpResponse()
        except Exception as err:
            response = subscriber.on_error(request, websocket, err)
        finally:
            subscriber.on_disconnect(request, websocket)
            if websocket:
                websocket.close(code=1001, message='Websocket closed.')
                return response
            log.warning('Starting late response on websocket')
            status_text = http_client.responses.get(response.status_code, 'UNKNOWN_STATUS_CODE')
            status = '%s %s' % (response.status_code, status_text)
            start_response(force_str(status), list(response._headers.values()))
            log.info('Finish non-websocket response with status code: %s', response.status_code)
            return response
