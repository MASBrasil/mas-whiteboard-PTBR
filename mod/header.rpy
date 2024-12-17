# This file is part of Whiteboard submod by Friends of Monika.
# Report issues and ask questions at https://github.com/friends-of-monika/mas-whiteboard/issues


init -990 python:
    store.mas_submod_utils.Submod(
        author="Friends of Monika",
        name="Whiteboard",
        description=_("This is a template submod for other people to reuse."),
        version="1.0.0"
    )

init -989 python:
    if store.mas_submod_utils.isSubmodInstalled("Submod Updater Plugin"):
        store.sup_utils.SubmodUpdater(
            submod="Whiteboard",
            user_name="friends-of-monika",
            repository_name="mas-whiteboard",
            extraction_depth=2
        )
