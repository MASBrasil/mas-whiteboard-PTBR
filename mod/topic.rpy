# This file is part of Whiteboard submod by Friends of Monika.
# Report issues and ask questions at https://github.com/friends-of-monika/mas-whiteboard/issues


init 5 python:
    addEvent(
        Event(
            persistent.event_database,
            eventlabel="fom_whiteboard_show",
            prompt="Can I use the whiteboard?",
            category=["misc"],
            pool=True,
            unlocked=True
        )
    )

label fom_whiteboard_show:
    m 3hua "Sure!"

    # Hide textbox and hide Monika with dissolve effect
    window hide
    with dissolve
    call spaceroom(hide_monika=True, dissolve_all=True, scene_change=False, show_emptydesk=False)

    # Setup whiteboard canvas, calls canvas screen with dissolve and hides with dissolve
    $ whiteboard_canvas = store._fom_whiteboard.Whiteboard()
    call screen fom_whiteboard_screen(whiteboard_canvas)

    # Dispose canvas and remove from global store
    $ whiteboard_canvas.dispose()
    $ del whiteboard_canvas

    # Restore textbox and show Monika with dissolve effect
    window auto
    with dissolve
    call spaceroom(hide_monika=False, dissolve_all=True, scene_change=False, show_emptydesk=False)
    return
