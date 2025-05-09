"""
Collect library
functions that are used to collect information from the network to source nodes.
"""

from phyelds.calculus import neighbors, aggregate, remember


@aggregate
def find_parent(potential: float) -> any:
    """
    Find the parent of a path giving a potential field
    :param potential:
    :return:
    """
    neighbors_potential = neighbors(potential)
    min_value = min(neighbors_potential.data.items(), key=lambda x: x[1])
    if min_value[1] >= potential:
        return None
    return min_value[0]


@aggregate
def collect_with(context, potential, local, accumulation):
    """
    TODO
    :param context:
    :param potential:
    :param local:
    :param accumulation:
    :return:
    """
    collections = remember(local)
    n_collections = neighbors(collections)
    parents = neighbors(find_parent(potential))
    zip_operation = zip(parents, n_collections)
    operations = local
    for parent, value in zip_operation:
        if context.id == parent:
            operations = accumulation(operations, value)
    return collections.update(operations)


@aggregate
def count_nodes(context, potential):
    """
    TODO
    :param context:
    :param potential:
    :return:
    """
    return collect_with(context, potential, 1, lambda x, y: x + y)


@aggregate
def sum_values(context, potential, local):
    """
    TODO
    :param context:
    :param potential:
    :param local:
    :return:
    """
    return collect_with(context, potential, local, lambda x, y: x + y)


@aggregate
def collect_or(context, potential, local):
    """
    TODO
    :param context:
    :param potential:
    :param local:
    :return:
    """
    return collect_with(context, potential, local, lambda x, y: x or y)
