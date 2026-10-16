from phyelds.libraries.utils import min_with_default, PathValue, non_looping_paths, path_coherence
from phyelds.data import NeighborhoodField
import pytest

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


def test_path_value_properties_and_extension():
    empty_path = PathValue(distance=0.0, data="src")
    assert empty_path.source is None
    assert empty_path.next_hop is None
    assert empty_path.length == 0
    assert 1 not in empty_path

    step_1 = empty_path.extend(1, 2.5, lambda from_src, edge, d: f"{d}->1")
    assert step_1.distance == 2.5
    assert step_1.data == "src->1"
    assert step_1.hops == (1,)
    assert step_1.source == 1
    assert step_1.next_hop == 1
    assert step_1.length == 1
    assert 1 in step_1

    step_2 = step_1.extend(2, 1.5, lambda from_src, edge, d: f"{d}->2")
    assert step_2.distance == 4.0
    assert step_2.hops == (1, 2)
    assert step_2.source == 1
    assert step_2.next_hop == 2


def test_path_value_rejects_triangle_inequality_violation():
    path = PathValue(distance=5.0, data="x", hops=(1,))
    with pytest.raises(ValueError):
        path.extend(2, -1.0, lambda _s, _e, d: d)


def test_non_looping_paths_filters_loops_diameter_and_shortcuts():
    # Node 3 receives paths from neighbors 1 and 2
    neighbor_data = NeighborhoodField(
        {
            3: None,
            1: PathValue(distance=1.0, data="via1", hops=(0,)),
            2: PathValue(distance=5.0, data="via2_with_shortcut", hops=(0, 1)),
            4: PathValue(distance=1.0, data="looping", hops=(0, 3)),
            5: PathValue(distance=1.0, data="too_long", hops=(0, 6, 7)),
        },
        node_id=3,
    )
    distances = NeighborhoodField({3: 0.0, 1: 1.0, 2: 1.0, 4: 1.0, 5: 1.0}, node_id=3)
    paths = non_looping_paths(
        neighbor_data=neighbor_data,
        distances=distances,
        local_id=3,
        max_diameter=2,
        accumulate_data=lambda _s, _e, d: d,
    )
    assert len(paths) == 1
    assert paths[0].data == "via1"
    assert paths[0].distance == 2.0
    assert paths[0].hops == (0, 1)


def test_path_coherence_drops_longer_path_with_inverted_hops():
    short_path = PathValue(distance=2.0, data="short", hops=(0, 1, 2))
    inverted_long = PathValue(distance=4.0, data="inverted", hops=(0, 2, 1, 4))
    coherent = path_coherence([short_path, inverted_long])
    assert coherent == [short_path]

