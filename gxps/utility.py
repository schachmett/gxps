"""Provides utility classes for Observer pattern and Singleton pattern."""
# pylint: disable=logging-format-interpolation

import logging
import copy


LOG = logging.getLogger(__name__)


class MetaDataContainer:
    """For inheriting: enables quick access to a metadata dictionary
    that prevents the object attributes from becoming too cluttered while
    at the same time offering a hook for doing something upon
    changing or calling a meta datum.
    """
    def __init__(self):
        self._meta = {}
        self._default_meta_value = "RAISE"
        super().__init__()

    def _get_meta(self, attr):
        """Hook being invoked on every self.get_meta call."""
        pass

    def get_meta(self, attr, silent=False):
        """Gives a datum from the dictionary and executes the self._get_meta
        hook.
        """
        if not silent:
            self._get_meta(attr)
        if attr not in self._meta:
            if self._default_meta_value == "RAISE":
                raise AttributeError(
                    "No meta-attribute '{}' exists in {}"
                    "".format(attr, self)
                )
            return self._default_meta_value
        return self._meta[attr]

    def _set_meta(self, attr, value):
        """Hook being invoked on every self.set_meta call."""
        pass

    def set_meta(self, attr, value, silent=False):
        """Sets a datum in the dictionary and executes the self._set_meta
        hook afterwards.
        """
        if not silent:
            self._set_meta(attr, value)
        self._meta[attr] = value


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
    Structure:
    self._policy[signal] = policy
        if signal not in self._policy, apply default_policy
    self._queue[signal] = [event, ...]
        key "signal" is created when the first event enqueues for it
        when the signal is fired, it's queue is emptied
    self._subscribers[signal] = [(callback, prio), ...]
        upon firing a signal, all appropriate callbacks are called
        ordered by prio
    TODO: don't call the same subscriber multiple times in one "all" firing
    """
    _policies = (
        "ignore",
        "accumulate",
        "fire"
    )

    def __init__(self, default_policy):
        if default_policy not in self._policies:
            raise ValueError("Unknown Event Queue policy")
        self._policy = {"default": default_policy, "all": None}
        self._subscribers = {}
        self._queue = {}
        super().__init__()

    def subscribe(self, callback, signal, priority=5):
        """Connects a callback to the queue.
        """
        if signal == "all":
            raise ValueError("Cannot subscribe to all signals")
        if signal not in self._subscribers:
            self._subscribers[signal] = []
        self._subscribers[signal].append((callback, priority))
        LOG.debug(
            "{} subscribed to signal '{}' on {}"
            "".format(callback, signal, self)
        )

    def unsubscribe(self, callback, signal="all"):
        """Disconnects a callback from the queue, by default for all signals.
        """
        if signal == "all":
            for sub_list in self._subscribers:
                dict(sub_list).pop(callback, None)
                # if callback in sub_list:
                #     sub_list.remove(callback)
            LOG.debug(
                "{} unsubscribed from all signals on {}"
                "".format(callback, self)
            )
        else:
            dict(self._subscribers[signal]).pop(callback, None)
            # if callback in self._subscribers[signal]:
            #     self._subscribers[signal].remove(callback)
            LOG.debug(
                "{} unsubscribed from signal '{}' on {}"
                "".format(callback, signal, self)
            )

    def enqueue(self, event):
        """Enqueues event.
        """
        LOG.debug("Enqueue signal '{}' to {}".format(event.signal, self))
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
            if signal not in self._queue or not self._queue[signal]:
                return
            if signal not in self._subscribers:
                return
            LOG.debug("Fire signal '{}' on {}".format(signal, self))
            event_list = EventList(self._queue[signal])
            self._queue[signal].clear()
            subs = self._subscribers[signal]
            for callback, _prio in sorted(subs, key=lambda x: x[1]):
                callback(event_list)

    def set_policy(self, policy, signal="all"):
        """Sets a policy for how to act on incoming events.
        """
        if policy not in self._policies:
            raise ValueError("Unknown Event Queue policy")
        self._policy[signal] = policy
        LOG.debug(
            "Set policy to '{}' (signal '{}') on {}"
            "".format(policy, signal, self)
        )

    def get_policy(self, signal="all"):
        """Get specific policy. Useful if it is unknown if the signal exists.
        """
        if signal not in self._policy:
            return self._policy["default"]
        return self._policy[signal]



class Observable:
    """Provides methods for observing these objects via callbacks.
    """
    _signals = ()
    _default_signals = ("registered-observable", )

    def __init__(self, *args, **kwargs):
        self._signals = self._signals + self._default_signals
        self._observers = dict((signal, dict()) for signal in self._signals)
        self._queues = []
        super().__init__(*args, **kwargs)

    @property
    def children(self):
        """To be implemented by inherited classes. All references to
        other Observable objects held inside the class should be given here.
        Has to be strictly hierarchical!
        """
        return []

    def deepcopy(self):
        """Disconnect from all Observer stuff, copy and then reconnect."""
        queues = self.queues
        children_queues = {}
        def unregister_children(obs):
            """Recursively unregister children and following generations.
            """
            for child in obs.children:
                children_queues[child] = child.queues
                child.unregister_all_queues()
                unregister_children(child)
        unregister_children(self)
        self.unregister_all_queues()
        other = copy.deepcopy(self)
        for queue in queues:
            self.register_queue(queue)
        for child, child_queues in children_queues.items():
            for queue in child_queues:
                child.register_queue(queue)
        return other

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
        return self._queues.copy()

    def register_queue(self, queue):
        """Registers a queue where events are sent to.
        """
        self._queues.append(queue)
        # TODO breaks older version
        # self.emit("registered-observable")
        LOG.debug("{} registered to queue {}".format(self, queue))

    def register_children_to_queue(self, queue):
        """Registers the children with the given queue.
        """
        for child in self.children:
            child.register_children_to_queue(queue)
            child.register_queue(queue)

    def unregister_queue(self, queue):
        """Unregisters a queue.
        """
        self._queues.remove(queue)
        LOG.debug("{} unregistered from queue {}".format(self, queue))

    def unregister_all_queues(self):
        """Unregisters all queues.
        """
        self._queues.clear()
        LOG.debug("{} unregistered all from queues".format(self))

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
