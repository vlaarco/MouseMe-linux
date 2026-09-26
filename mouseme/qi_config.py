from dataclasses import dataclass, field
from typing import Dict, List, Tuple

Point = Tuple[float, float]


# X keysym names for the keys MouseMe listens for; mapped to keycodes at startup
class Key:
    space = "space"
    escape = "Escape"
    b = "b"
    c = "c"
    d = "d"
    e = "e"
    f = "f"
    m = "m"
    p = "p"
    r = "r"
    s = "s"
    t = "t"
    v = "v"
    x = "x"
    y = "y"
    z = "z"


@dataclass(frozen=True)
class QIAction:
    label: str

    # Clicked only when this key differs from the previous QI key
    setup: List[Point] = field(default_factory=list)

    # Clicked on every press
    clicks: List[Point] = field(default_factory=list)


# All coordinates are root-window pixels with the origin at the top-left of the screen
class QIConfig:
    keys = [
        Key.space,
        Key.escape,
        Key.b,
        Key.c,
        Key.d,
        Key.e,
        Key.f,
        Key.m,
        Key.p,
        Key.s,
        Key.t,
        Key.v,
        Key.x,
        Key.y,
        Key.z,
    ]

    # Space and X are handled separately: Space picks a building to confirm, X stops QI
    actions: Dict[str, QIAction] = {
        Key.b: QIAction("Brewery", setup=[(239, 954), (16, 1225), (175, 1223)], clicks=[(158, 1127)]),
        Key.c: QIAction("Church", setup=[(240, 1025), (13, 1223)], clicks=[(157, 1136)]),
        Key.d: QIAction("Doctor", setup=[(242, 1023), (13, 1223), (176, 1225)], clicks=[(58, 969)]),
        Key.e: QIAction("Estate", setup=[(241, 919), (12, 1224), (174, 1223)], clicks=[(55, 1133)]),
        Key.escape: QIAction("Cancel", clicks=[(1355, 307)]),
        Key.f: QIAction("Flat Mode", clicks=[(1300, 307)]),
        Key.m: QIAction("Multistory", setup=[(241, 919), (12, 1224)], clicks=[(55, 975)]),
        Key.p: QIAction("Pillory", setup=[(241, 1026), (12, 1222)], clicks=[(57, 1131)]),
        Key.s: QIAction("Sell", clicks=[(1206, 307)]),
        Key.t: QIAction("Tannery", setup=[(239, 952), (15, 1226)], clicks=[(55, 1124)]),
        Key.v: QIAction("Move", clicks=[(1260, 307)]),
        Key.y: QIAction("Bakery", setup=[(237, 953), (11, 1223)], clicks=[(56, 975)]),
        Key.z: QIAction("Build", clicks=[(26, 1278)]),
    }

    building_confirm: Dict[str, List[Point]] = {
        Key.b: [(1100, 930), (1400, 975)],
        Key.c: [(1100, 970), (1400, 1020)],
        Key.d: [(1097, 945), (1400, 1002)],
        Key.e: [(1100, 970), (1400, 1020)],
        Key.m: [(1100, 970), (1400, 1015)],
        Key.t: [(1100, 935), (1400, 985)],
        Key.y: [(1100, 950), (1400, 1000)],
    }

    # Actions whose label reverts to "QI" after a few seconds; every other label stays until the next key
    transient_keys = {Key.escape, Key.f, Key.z}
    transient_label_seconds = 3

    # The toolbar buttons by QI key as (left, top, width, height), each 43 x 43 and 50 apart.
    # Clicking one yourself changes the game's mode just like its QI key does, so the label follows either way.
    toolbar_buttons = {
        Key.s: (1184, 286, 43, 43),
        Key.v: (1234, 286, 43, 43),
        Key.f: (1284, 286, 43, 43),
        Key.escape: (1334, 286, 43, 43),
    }

    # The build menu the Build button opens (with the panel below it) and the category tabs down its right side,
    # as (left, top, width, height). Clicking in either yourself ends the game's Sell or Move mode, so those labels go back to "QI".
    build_menu_areas = [
        (0, 856, 223, 534),
        (223, 902, 35, 244),
    ]

    mode_keys = {Key.s, Key.v}

    gbg_click: Point = (1300, 1052)

    # A physical click above this line is in the browser tab strip
    tab_strip_max_y = 106
