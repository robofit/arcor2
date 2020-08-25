from arcor2.source.utils import parse_def, tree_to_str
from arcor2_arserver.object_types.source import function_implemented, new_object_type
from arcor2_arserver_data.objects import ObjectTypeMeta


def test_meta_to_source() -> None:

    parent = ObjectTypeMeta(type="Generic")
    child = ObjectTypeMeta(type="NewType", description="blabla bla", base="Generic")

    source = tree_to_str(new_object_type(parent, child))

    assert "class NewType(Generic)" in source


class TestType:
    def func_1(self) -> None:
        """
        Test subject
        :return:
        """
        return None

    def func_2(self) -> None:
        """
        Test subject
        :return:
        """

        raise NotImplementedError("This function is not implemented.")

    def func_3(self) -> None:

        var = 1 + 2
        raise NotImplementedError(f"{var}")

    def func_4(self, param: int) -> bool:
        """Exceptions different from NotImplementedError are ok.

        :param param:
        :return:
        """

        if param == 1:
            raise Exception("Exception!")
        return True

    def func_5(self) -> None:
        raise NotImplementedError

    def func_6(self) -> None:
        raise NotImplementedError(1)


module_tree = parse_def(TestType)


def test_function_implemented():

    assert function_implemented(module_tree, TestType.func_1.__name__)
    assert not function_implemented(module_tree, TestType.func_2.__name__)
    assert not function_implemented(module_tree, TestType.func_3.__name__)
    assert function_implemented(module_tree, TestType.func_4.__name__)
    assert not function_implemented(module_tree, TestType.func_5.__name__)
    assert not function_implemented(module_tree, TestType.func_6.__name__)
