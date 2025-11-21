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
    if mas_getEVL_shown_count("fom_whiteboard_show") == 0:
        m 1hua "Sure!{w=0.3} Just a moment, let me bring it for you..."
    else:
        m 1hua "Sure, just a moment~"

    # Hide textbox and hide Monika with dissolve effect
    window hide
    with dissolve
    call spaceroom(hide_monika=True, dissolve_all=True, scene_change=False, show_emptydesk=False)

    # Setup whiteboard canvas, calls canvas screen with dissolve and hides with dissolve
    $ whiteboard_canvas = store._fom_whiteboard.Whiteboard()
    $ label_init_ts = datetime.datetime.now()
    call screen fom_whiteboard_screen(whiteboard_canvas)
    $ label_time_spent = datetime.datetime.now() - label_init_ts

    # Dispose canvas and remove from global store
    $ whiteboard_canvas.dispose()
    $ del whiteboard_canvas

    # Restore textbox and show Monika with dissolve effect
    window auto
    with dissolve
    call spaceroom(hide_monika=False, dissolve_all=True, scene_change=False, show_emptydesk=False)

    if label_time_spent < datetime.timedelta(seconds=10):
        m 1hua "Done already? Ahaha~"
    elif mas_getEVL_shown_count("fom_whiteboard_show") == 0:
        m 3eua "Just tell me if you'll need a whiteboard again, [mas_get_player_nickname()]~"

    $ del label_init_ts, label_time_spent
    return
