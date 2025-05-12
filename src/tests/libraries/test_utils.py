import pytest

from phyelds.libraries.utils import min_with_default

def test_min_with_default_dict():
    """
    Test the min_with_default function with a dictionary.
    """
    data = {'a': 3, 'b': 1, 'c': 2}
    default = 0
    result = min_with_default(data, default)
    assert result == 1
    data = dict()
    result = min_with_default(data, default)
    assert result == default


def test_min_with_default_list():
    """
    Test the min_with_default function with a list.
    """
    data = [3, 1, 2]
    default = 0
    result = min_with_default(data, default)
    assert result == 1
    data = []
    result = min_with_default(data, default)
    assert result == default

def test_min_with_default_tuple():
    """
    Test the min_with_default function with a tuple.
    """
    data = (3, 1, 2)
    default = 0
    result = min_with_default(data, default)
    assert result == 1
    data = ()
    result = min_with_default(data, default)
    assert result == default

def test_min_with_default_set():
    """
    Test the min_with_default function with a set.
    """
    data = {3, 1, 2}
    default = 0
    result = min_with_default(data, default)
    assert result == 1
    data = set()
    result = min_with_default(data, default)
    assert result == default

def test_min_with_default_range():
    """
    Test the min_with_default function with a range.
    """
    data = range(3, 10)
    default = 0
    result = min_with_default(data, default)
    assert result == 3
    data = range(0)
    result = min_with_default(data, default)
    assert result == default
