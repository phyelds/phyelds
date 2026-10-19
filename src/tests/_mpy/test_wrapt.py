from phyelds._mpy.wrapt import ObjectProxy


def test_object_proxy_forwards_operators_both_ways():
    proxy = ObjectProxy(6)

    assert [proxy + 1, 1 + proxy, proxy - 1, 10 - proxy, proxy * 2, 2 * proxy] == [7, 7, 5, 4, 12, 12]
    assert [proxy / 4, 12 / proxy, proxy // 4, 13 // proxy, proxy % 4, 13 % proxy] == [1.5, 2, 1, 2, 2, 1]
    assert [proxy ** 2, 2 ** proxy, proxy & 3, 3 & proxy, proxy | 1, 1 | proxy] == [36, 64, 2, 2, 7, 7]
    assert [proxy ^ 1, 1 ^ proxy, proxy << 1, proxy >> 1] == [7, 7, 12, 3]
    assert [-proxy, +proxy, abs(ObjectProxy(-2)), ~proxy] == [-6, 6, 2, -7]


def test_object_proxy_compares_like_its_value():
    proxy = ObjectProxy(6)

    assert proxy == 6 and proxy != 5
    assert proxy < 7 and proxy <= 6 and proxy > 5 and proxy >= 6
    assert proxy == ObjectProxy(6)
    assert hash(proxy) == hash(6)


def test_object_proxy_converts_like_its_value():
    proxy = ObjectProxy(6)

    assert (bool(ObjectProxy(0)), int(proxy), float(proxy), [10, 20, 30, 40, 50, 60, 70][proxy]) == (False, 6, 6.0, 70)
    assert (str(proxy), repr(ObjectProxy("a"))) == ("6", "'a'")


def test_object_proxy_forwards_containers_and_attributes():
    proxy = ObjectProxy([3, 4])

    assert (len(proxy), list(proxy), proxy[1], 3 in proxy, proxy.index(4)) == (2, [3, 4], 4, True, 1)
