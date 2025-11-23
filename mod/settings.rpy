# This file is part of Whiteboard submod by Friends of Monika.
# Report issues and ask questions at https://github.com/friends-of-monika/mas-whiteboard/issues

default persistent._fom_whiteboard_show_tips = True

screen fom_whiteboard_settings_pane():
    $ tooltip = renpy.get_screen("submods", "screens").scope["tooltip"]

    vbox:
        box_wrap False
        xfill True
        xmaximum 800

        hbox:
            style_prefix "check"
            box_wrap False

            textbutton _("Show random tips"):
                selected persistent._fom_whiteboard_show_tips
                action ToggleField(persistent, "_fom_whiteboard_show_tips")
                hovered SetField(tooltip, "value", _("Choose whether to display random tips when using the whiteboard."))
                unhovered SetField(tooltip, "value", tooltip.default)
