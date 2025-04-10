from fieldpy.calculus import aggregate, remember, neighbors
from fieldpy.libraries.utils import min_with_default


@aggregate
def distance_to(source, distances):
    gradient = remember(float("inf"))
    neighbors_gradients = neighbors(gradient) + distances
    return gradient.update(
        0.0
        if source
        else min_with_default(neighbors_gradients.exclude_self(), float("inf"))
    )


@aggregate
def cast_from(source, data, distances):
    cast_area = remember(data)
    potential = distance_to(source, distances)
    neighbors_value = neighbors(cast_area)
    # neighbors potential
    neighbors_potential = neighbors(potential)
    # take the value from the minimum potential
    values = zip(neighbors_potential, neighbors_value)
    # select the minimum potential
    _, result = min(values, key=lambda x: x[0])
    return cast_area.update(data if source else result)
