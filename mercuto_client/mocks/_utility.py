import logging
from types import FunctionType
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EnforceOverridesMeta(type):
    """
    Helper for patching mock implementations.

    Assign this as a metaclass when overriding a single base class, and all of the base class' methods
    must be overridden and cannot be called.

    Example usage:

    ```
    class BaseClass():
        def method1(self):
            pass
        def method2(self):
            pass

    class MockClass(BaseClass, metaclass=EnforceOverridesMeta):
        def method1(self):
            return "Mocked!"

    mock = MockClass()
    mock.method1() # Okay
    mock.method2() # Raises NotImplementedError
    ```

    To exclude specific methods from requiring overrides, add them to the `__exclude_enforce__` set:

    ```
    class MockClass(BaseClass, metaclass=EnforceOverridesMeta):
        __exclude_enforce__ = {BaseClass.method2}

        def method1(self):
            return "Mocked!"

    mock = MockClass()
    mock.method1() # Okay
    mock.method2() # Okay
    ```
    """
    def __init__(cls: type[Any], name: str, bases: tuple[type, ...], namespace: dict[str, Any]) -> None:
        type.__init__(cls, name, bases, namespace)

        # Assumes single inheritance from Base
        if len(bases) != 1:
            raise TypeError("EnforceOverridesMeta can only be used with a single base class.")

        base = bases[0]

        excluded: set[FunctionType] = getattr(cls, "__exclude_enforce__", set())

        for attr in dir(base):
            if attr.startswith('__'):
                continue

            base_method = getattr(base, attr)
            if isinstance(base_method, FunctionType) and base_method not in excluded and attr not in namespace:
                def make_error_method(attr_name: str) -> Callable[..., None]:
                    def error_method(self: Any, *args: Any, **kwargs: Any) -> None:
                        raise NotImplementedError(f"Mocker '{cls.__name__}' does not currently support method '{attr_name}'")
                    return error_method

                setattr(cls, attr, make_error_method(attr))
