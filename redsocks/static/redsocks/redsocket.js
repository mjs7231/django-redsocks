/*----------------------------------------------------------
 * modified version of ws4redis from django-websocket-redis
 * Source: https://github.com/jrief/django-websocket-redis/blob/master/ws4redis/static/js/ws4redis.js
 *------------------------------------------------------- */

function Redsocket(options) {
  'use strict';
  if (options.uri === undefined)
		throw new Error('No Websocket URI in options');

  var ws, deferred, timer;
  var attempts = 1;
  var heartbeat_interval = null;
  var missed_heartbeats = 0;
  var opts = $.extend({heartbeat_msg:null}, options);
  connect(opts.uri);
  
  function connect(uri) {
		try {
			deferred = $.Deferred();
			ws = new WebSocket(uri);
			ws.onopen = on_open;
			ws.onmessage = on_message;
			ws.onerror = on_error;
			ws.onclose = on_close;
			timer = null;
		} catch (err) {
			deferred.reject(new Error(err));
		}
	}
  
  function send_heartbeat() {
		try {
			missed_heartbeats += 1;
			if (missed_heartbeats > 3)
				throw new Error('Too many missed heartbeats.');
			ws.send(opts.heartbeat_msg);
		} catch(err) {
			clearInterval(heartbeat_interval);
			heartbeat_interval = null;
			console.warn('Closing connection: '+ err.message);
			ws.close();
		}
	}
  
  function on_open() {
		attempts = 1;
		deferred.resolve();
		if (opts.heartbeat_msg && heartbeat_interval === null) {
			missed_heartbeats = 0;
			heartbeat_interval = setInterval(send_heartbeat, 5000);
		}
		if ($.type(opts.connected) === 'function') {
			opts.connected();
    }
	}

	function on_close(evt) {
		console.warn('Connection closed.');
		if (!timer) {
			var interval = generate_inteval(attempts);
			timer = setTimeout(function() {
				attempts += 1;
				connect(ws.url);
			}, interval);
		}
	}

	function on_error(evt) {
		console.error('Websocket connection broken.');
		deferred.reject(new Error(evt));
	}

	function on_message(evt) {
		if (opts.heartbeat_msg && evt.data === opts.heartbeat_msg) {
			missed_heartbeats = 0;
		} else if ($.type(opts.receive_message) === 'function') {
			return opts.receive_message(evt.data);
		}
	}
  
  function generate_inteval(k) {
		var maxInterval = (Math.pow(2, k) - 1) * 1000;
    maxInterval = Math.min(maxInterval, 30*1000);
		return Math.random() * maxInterval;
	}
  
  this.send_message = function(message) {
		ws.send(message);
	};
}
