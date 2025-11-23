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
        m 1eua "Sure!{w=0.3} Just a moment, let me bring it for you.{w=0.3}.{w=0.3}.{w=0.3}{nw}"
    else:
        m 1hua "Sure, just a moment.{w=0.3}.{w=0.3}.{w=0.3}{nw}"

    call spaceroom(hide_monika=True, scene_change=True, dissolve_all=True)

    if mas_getEVL_shown_count("fom_whiteboard_show") == 0:
        m "I wouldn't want to seem rude staring at you as you draw, so I'll just stand right beside, okay?~"
    else:
        m "There~"

    # Setup whiteboard canvas, calls canvas screen with dissolve and hides with dissolve
    $ whiteboard_canvas = store._fom_whiteboard.Whiteboard()
    $ label_init_ts = datetime.datetime.now()
    call screen fom_whiteboard_screen(whiteboard_canvas)
    $ label_time_spent = datetime.datetime.now() - label_init_ts

    # Dispose canvas and remove from global store
    $ whiteboard_canvas.dispose()
    $ del whiteboard_canvas

    if label_time_spent < datetime.timedelta(seconds=10):
        m "Done already? Ahaha~"

    m "Let me take it away now.{w=0.3}.{w=0.3}.{w=0.3}{nw}"
    call mas_transition_from_emptydesk("monika 3hua")

    m 3hua "Just tell me if you'll need a whiteboard again, [mas_get_player_nickname()]~"
    $ del label_init_ts, label_time_spent
    return
