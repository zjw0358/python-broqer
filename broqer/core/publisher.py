""" Implementing Publisher and StatefulPublisher """

import asyncio
from typing import TYPE_CHECKING, Any, Callable, Union

from broqer.core import UNINITIALIZED, SubscriptionDisposable

if TYPE_CHECKING:
    from broqer.core import Subscriber  # noqa: F401


class SubscriptionError(ValueError):
    """ Special exception raised when subscription is failing (subscriber
    already subscribed) or on unsubscribe when subscriber is not subscribed
    """
    pass


class Publisher():
    """ In broqer a subscriber can subscribe to a Publisher. Subscribers
    are notified about emitted values from the publisher. In other frameworks
    publisher/subscriber are referenced as observable/observer.

    As information receiver use following method to interact with Publisher
    .subscribe(subscriber) to subscribe for events on this publisher
    .unsubscribe(subscriber) to unsubscribe
    .get() to get the current state (will raise ValueError if not stateful)

    When implementing a Publisher use the following methods:
    .notify(value) calls .emit(value) on all subscribers
    """
    def __init__(self):
        self._subscriptions = list()

    def subscribe(self, subscriber: 'Subscriber',
                  prepend: bool = False) -> SubscriptionDisposable:
        """ Subscribing the given subscriber.

        :param subscriber: subscriber to add
        :param prepend: For internal use - usually the subscribers will be
            added at the end of a list. When prepend is True, it will be added
            in front of the list. This will habe an effect in the order the
            subscribers are called.
        :raises SubscriptionError: if subscriber already subscribed
        """

        if any(subscriber is s for s in self._subscriptions):
            raise SubscriptionError('Subscriber already registered')

        if prepend:
            self._subscriptions.insert(0, subscriber)
        else:
            self._subscriptions.append(subscriber)

        return SubscriptionDisposable(self, subscriber)

    def unsubscribe(self, subscriber: 'Subscriber') -> None:
        """ Unsubscribe the given subscriber

        :param subscriber: subscriber to unsubscribe
        :raises SubscriptionError: if subscriber is not subscribed (anymore)
        """
        # here is a special implementation which is replacing the more
        # obvious one: self._subscriptions.remove(subscriber) - this will not
        # work because list.remove(x) is doing comparision for equality.
        # Applied to publishers this will return another publisher instead of
        # a boolean result
        for i, _s in enumerate(tuple(self._subscriptions)):
            if _s is subscriber:
                self._subscriptions.pop(i)
                return
        raise SubscriptionError('Subscriber is not registered')

    def get(self):  # pylint: disable=useless-return, no-self-use
        """Return the value of a (possibly simulated) subscription to this
        publisher.

        :raises ValueError: when the publisher is stateless.
        """
        raise ValueError('No value available')

    def notify(self, value: Any) -> asyncio.Future:
        """ Calling .emit(value) on all subscribers. A synchronouse subscriber
        will just return None, a asynchronous one may returns a future. Futures
        will be collected. If no future was returned None will be returned by
        this method. If one futrue was returned that future will be returned.
        When multiple futures were returned a gathered future will be returned.
        """
        results = tuple(s.emit(value, who=self) for s
                        in tuple(self._subscriptions))
        futures = tuple(r for r in results if r is not None)

        if futures:
            if len(futures) == 1:
                return futures[0]  # return the received single future
            return asyncio.gather(*futures)
        return None

    @property
    def subscriptions(self):
        """ property returning a tuple with all current subscribers """
        return tuple(self._subscriptions)

    def __or__(self, apply: Callable[
            ['Publisher'], Union['Publisher', SubscriptionDisposable]]) \
            -> Union['Publisher', SubscriptionDisposable]:
        """ Publishers can be "piped" to subscribers. This is usefull when
        working with operators.

        Example:
        >>> from broqer import Publisher, op
        >>> p = Publisher()
        >>> disposable = p | op.sink(print)

        :param apply: A function taking the actual publisher as argument and
            returning a new publisher when applied to an operator or a
            SubscriptionDisposable when applied to a subscriber.
        :return: A new publisher (for operators) or a SubscriptionDisposable (
            for subscribers)
        """
        return apply(self)

    def __await__(self):
        """ Publishers are awaitable. This is done be applying the ToFuture
        operator (see ToFuture for more information) """
        from broqer.op import ToFuture  # lazy import due circular dependency
        return ToFuture(self).__await__()

    def to_future(self, timeout=None):
        """ When a timeout should be applied for awaiting use this method """
        from broqer.op import ToFuture  # lazy import due circular dependency
        return ToFuture(self, timeout)

    def __bool__(self):
        """ A new Publisher is the result of a comparision between a publisher
        and something else (may also be a second publisher). This result should
        never be used in a boolean sense (e.g. in `if p1 == p2:`). To prevent
        this __bool__ is overwritten to raise a ValueError.
        """
        raise ValueError('Evaluation of comparison of publishers is not '
                         'supported')


class StatefulPublisher(Publisher):
    """ A StatefulPublisher is keeping it's state. This changes the behavior
    compared to a non-stateful Publisher:
    - when subscribing the subscriber will be notified with the actual state
    - .get() is returning the actual state

    :param init: the initial state. As long the state is UNINITIALIZED, the
        behavior will be equal to a stateless Publisher.
    """
    def __init__(self, init=UNINITIALIZED):
        Publisher.__init__(self)
        self._state = init

    def subscribe(self, subscriber: 'Subscriber',
                  prepend: bool = False) -> 'SubscriptionDisposable':
        disposable = Publisher.subscribe(self, subscriber, prepend=prepend)
        if self._state is not UNINITIALIZED:
            subscriber.emit(self._state, who=self)
        return disposable

    def get(self):
        if self._state is not UNINITIALIZED:
            return self._state
        return Publisher.get(self)

    def notify(self, value: Any) -> asyncio.Future:
        if self._state != value:
            self._state = value
            return Publisher.notify(self, value)
        return None

    def reset_state(self, value=UNINITIALIZED):
        """ resets the state. Behavior for .subscribe() and .get() will be
        like a stateless Publisher.
        """
        self._state = value
