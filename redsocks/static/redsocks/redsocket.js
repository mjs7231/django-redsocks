/*----------------------------------------------------------
 * modified version of ws4redis from django-websocket-redis
 * Source: https://github.com/jrief/django-websocket-redis/blob/master/ws4redis/static/js/ws4redis.js
 *------------------------------------------------------- */

function Redsocket(options) {
  'use strict';
  if (options.uri === undefined)
		throw new Error('No Websocket URI in options');

  var ws, deferred;               // websocket and deferred objects
  var connect_attempts = 1;       // attempts to create socket connection
  var connect_timer = null;       // connection timer
  var heartbeat_sent = null;      // timestamp last heartbeat sent
  var heartbeat_timer = null;     // heartbeat timer
  var heartbeats_missed = 0;      // count of heartbeats missed
  var latency = null;             // current latency in ms
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
			connect_timer = null;
		} catch (err) {
			deferred.reject(new Error(err));
		}
	}
  
  function send_heartbeat() {
		try {
			heartbeats_missed += 1;
			if (heartbeats_missed > 3)
				throw new Error('Too many missed heartbeats.');
      heartbeat_sent = Date.now();
			ws.send(opts.heartbeat_msg);
		} catch(err) {
			clearInterval(heartbeat_timer);
			heartbeat_timer = null;
			console.warn('Closing connection: '+ err.message);
			ws.close();
		}
	}
  
  function on_open() {
		connect_attempts = 1;
		deferred.resolve();
		if (opts.heartbeat_msg && heartbeat_timer === null) {
			heartbeats_missed = 0;
			heartbeat_timer = setInterval(send_heartbeat, 5000);
      setTimeout(send_heartbeat, 100);
		}
		if ($.type(opts.connected) === 'function') {
			opts.connected();
    }
	}

	function on_close(evt) {
		console.warn('Connection closed.');
		if (!connect_timer) {
			var interval = generate_interval(connect_attempts);
			connect_timer = setTimeout(function() {
				connect_attempts += 1;
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
			latency = Date.now() - heartbeat_sent;
      heartbeats_missed = 0;
      return opts.receive_heartbeat(latency);
		} else if ($.type(opts.receive_message) === 'function') {
			return opts.receive_message(evt.data);
		}
	}
  
  function generate_interval(k) {
		var maxint = (Math.pow(2, k) - 1) * 1000;
    maxint = Math.min(maxint, 30*1000);
		return Math.random() * maxint;
	}
  
  this.send_message = function(message) {
		ws.send(message);
	};
}
