from apte import ApteSession

session = ApteSession()
session.register_default_plugins()


@session.test()
def test_passing() -> None:
    assert True


@session.test()
def test_also_passing() -> None:
    assert 1 + 1 == 2
