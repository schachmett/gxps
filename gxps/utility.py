"""Provides utility classes for Observer pattern and Singleton pattern."""
# pylint: disable=logging-format-interpolation

import logging


LOG = logging.getLogger(__name__)


class Event:
    """Stores variables during emitting.
    """
    # pylint: disable=too-few-public-methods
    def __init__(self, signal):
        self.properties = {}

        self._signal = signal
        self.source = []

    @property
    def signal(self):
        """Expose the signal."""
        return self._signal


class EventList(Event):
    """A list of events that behaves like an event but has all the
    childrens' attribute values.
    """
    # pylint: disable=too-few-public-methods
    def __init__(self, eventlist):
        self._list = eventlist
        super().__init__(self._list[0].signal)
        for event in self._list:
            if event.signal != self._list[0].signal:
                raise AttributeError("EventList has only one signal")
            for prop in event.properties:
                if prop not in self.properties:
                    self.properties[prop] = []
                if isinstance(event.properties[prop], list):
                    self.properties[prop].extend(event.properties[prop])
                else:
                    self.properties[prop].append(event.properties[prop])
            self.source.extend(event.source)


class EventBus:
    """Context manager for queuing Events emitted by Observables so they
    are not emitted multiple times by one method call.
    """
    _policies = [
        "ignore",
        "accumulate",
        "fire"
    ]

    def __init__(self, default_policy):
        if default_policy not in self._policies:
            raise ValueError("Unknown Event Queue policy")
        self._policy = {"default": default_policy, "all": None}
        self._subscribers = {}
        self._queue = {}

    def subscribe(self, callback, signal):
        """Connects a callback to the queue.
        """
        if signal == "all":
            raise ValueError("Cannot subscribe to all signals")
        if signal not in self._subscribers:
            self._subscribers[signal] = []
        self._subscribers[signal].append(callback)

    def unsubscribe(self, callback, signal="all"):
        """Disconnects a callback from the queue, by default for all signals.
        """
        if signal == "all":
            for sub_list in self._subscribers:
                if callback in sub_list:
                    sub_list.remove(callback)
        else:
            if callback in self._subscribers[signal]:
                self._subscribers[signal].remove(callback)

    def enqueue(self, event):
        """Enqueues event.
        """
        LOG.debug("enqueue event with signal {}".format(event.signal))
        policy = self._policy.get(event.signal, self._policy["default"])
        if self._policy["all"]:
            policy = self._policy["all"]

        elif policy == "ignore":
            return
        if event.signal not in self._queue:
            self._queue[event.signal] = []
        self._queue[event.signal].append(event)
        if "noqueue" in event.properties or policy == "fire":
            self.fire(event.signal)

    def fire(self, signal="all"):
        """Fires all accumulated events of given signal.
        """
        if signal == "all":
            for specific_signal in self._queue:
                if specific_signal == "all":
                    continue
                self.fire(specific_signal)
        else:
            LOG.debug("Fire signal {}".format(signal))
            if signal not in self._queue or not self._queue[signal]:
                return
            event_list = EventList(self._queue[signal])
            self._queue[signal].clear()
            for callback in self._subscribers[signal]:
                callback(event_list)

    def set_policy(self, policy, signal="all"):
        """Sets a policy for how to act on incoming events.
        """
        if policy not in self._policies:
            raise ValueError("Unknown Event Queue policy")
        self._policy[signal] = policy

    def get_policy(self, signal="all"):
        """Get specific policy. Useful if it is unknown if the signal exists.
        """
        if signal not in self._policy:
            return self._policy["default"]
        return self._policy[signal]



class Observable:
    """Provides methods for observing these objects via callbacks.
    """
    # pylint: disable=invalid-name
    _signals = ()
    # _signals = (
    #     "changed",
    #     "changed-spectra",
    #     "changed-spectrum",
    #     "changed-metadata",
    #     "changed-fit",
    #     "changed-peak",
    #     "changed-peak-meta"
    # )

    def __init__(self):
        self._observers = dict((signal, dict()) for signal in self._signals)
        self._queues = []

    @property
    def signals(self):
        """Makes signals accessible.
        """
        signals = list(self._signals).copy()
        return signals

    @property
    def queues(self):
        """Exposes queues.
        """
        return self.queues.copy()

    def register_queue(self, queue):
        """Registers a queue where events are sent to.
        """
        self._queues.append(queue)

    def unregister_queue(self, queue):
        """Unregisters a queue.
        """
        self._queues.remove(queue)

    def unregister_all_queues(self):
        """Unregisters all queues.
        """
        self._queues.clear()

    def emit(self, signal, **kwargs):
        """Emit a signal: call all corresponding observers with an event
        object as argument. Also make the propagators propagate.
        """
        if signal not in self._signals:
            raise ValueError("{} cannot emit signal '{}'".format(self, signal))
        event = Event(signal)
        event.source.append(self)
        for key, value in kwargs.items():
            event.properties[key] = value

        for queue in self._queues:
            queue.enqueue(event)
