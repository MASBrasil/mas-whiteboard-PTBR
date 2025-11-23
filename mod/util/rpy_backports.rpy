init -9999 python in _fom_rpy_backports:
    # https://github.com/renpy/renpy/blob/4b4aa38455b32b1fc985db102c0a09c8b6f89ad2/renpy/common/00action_data.rpy#L307
    # Not pure.
    def ToggleLocalVariable(name, true_value=None, false_value=None):
        """
        :doc: data_action

        Toggles the value of `name` in the current local context.

        This function is only useful in a screen that has been use by
        another scene, as it provides a way of setting the value of a
        variable inside the used screen. In all other cases,
        :func:`ToggleScreenVariable` should be preferred, as it allows more
        of the screen to be cached.

        This must be created in the context that the variable is set
        in - it can't be passed in from somewhere else.

        `true_value`
            If not None, then this is the true value used.
        `false_value`
            If not None, then this is the false value used.
        """
        from store import ToggleDict
        import sys
        return ToggleDict(sys._getframe(1).f_locals, name, true_value=true_value, false_value=false_value)
