from unittest import mock
import pytest

from broqer.op import Cache, Just, Sink
from broqer import Publisher, StatefulPublisher

from .helper import check_single_operator, NONE

@pytest.mark.parametrize('args, input_vector, output_vector', [
    ((-1,), (0, 1, 2, 3), (0, 1, 2, 3)),
    ((-1,), (-1, -1, -1, -1), (NONE, NONE, NONE, NONE)),
    ((-1,), (1, 1, -1, -1), (1, NONE, -1, NONE)),
    (('a',), (None, None, 'b', -1), (None, NONE, 'b', -1)),
    ((1,2), ((1,2), (1,3), (1,3)), (NONE, (1,3), NONE)),
    ((), (0, 1, 2, 3), (0, 1, 2, 3)),
    ((), (-1, -1, -1, 1), (-1, NONE, NONE, 1)),
])
def test_with_publisher(args, input_vector, output_vector):
    init = args if args else None
    check_single_operator(Cache, args, {}, input_vector, output_vector, initial_state=init, has_state=True)

def test_uninitialised_with_publisher():
    source = Publisher()
    dut = Cache(source)
    cb = mock.Mock()
    Sink(dut, cb)

    cb.assert_not_called()

    source.notify(1)
    cb.assert_called_once_with(1)

    source.notify(1)
    cb.assert_called_once_with(1)


def test_initialised_with_publisher():
    source = Publisher()
    dut = Cache(source, 1)
    cb = mock.Mock()
    Sink(dut, cb)

    cb.assert_called_once_with(1)
    cb.reset_mock()

    source.notify(2)
    cb.assert_called_once_with(2)

    source.notify(2)
    cb.assert_called_once_with(2)

def test_uninitialised_with_stateful():
    source = StatefulPublisher(1)
    dut = Cache(source)
    cb = mock.Mock()
    Sink(dut, cb)

    cb.assert_called_once_with(1)
    source.notify(1)
    cb.assert_called_once_with(1)

    cb.reset_mock()
    source.notify(2)

    cb.assert_called_once_with(2)

def test_initialised_with_stateful():
    source = StatefulPublisher(1)
    dut = Cache(source, 2)
    cb = mock.Mock()
    Sink(dut, cb)

    cb.assert_called_once_with(1)

    source.notify(1)
    cb.assert_called_once_with(1)

    cb.reset_mock()

    source.notify(2)
    cb.assert_called_once_with(2)