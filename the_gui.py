import json
from pathlib import Path
from typing import Tuple, List

import PySimpleGUI as sg
from loguru import logger

from serebii_scrape import generate_data


JSON_FILE = "data/dex.json"
if not Path(JSON_FILE).exists():
    with open(JSON_FILE, "w", encoding="windows-1252") as pkmn_json:
        json.dump([], pkmn_json, indent=2)
    generate_data(JSON_FILE)

sg.theme("Dark Green 7")

pkmn_dex = []
pkmn_rows = []
with open(JSON_FILE, "r", encoding="windows-1252") as pkmn_json:
    pkmn_dex = json.load(pkmn_json)


SETTINGS_FILE = "data/settings.json"
STARTING_PC_BOX = 1
if Path(SETTINGS_FILE).exists():
    with open(SETTINGS_FILE, "r") as settings_json:
        settings = json.load(settings_json)
        STARTING_PC_BOX = settings["-BOXOFFSET-"]


def calculate_box_row_pos(count: int) -> str:
    # floor value of division, then + 1 because PC boxes arn't 0-index
    box = count // 30 + STARTING_PC_BOX
    # Find position inside box
    _box_index = count % 30
    # Row finds how many times 6 goes into index rounded down to find row number 0 index. Then 1 index answer.
    row = _box_index // 6 + 1
    # Pos uses modulo to count 0 to 5 then start over 0 to 5 to find column in pc box. Then 1 index answer.
    pos = _box_index % 6 + 1

    return f"Box {box:02}, Row {row:02}, Position {pos:02}"


def generate_pkmn_rows() -> List[sg.Element]:
    for count, pkmn in enumerate(pkmn_dex):
        # Make string description of form nicer to read
        current_form = pkmn["Form"].replace("Uniform", "Uni").split("+")
        background_color = sg.DEFAULT_BACKGROUND_COLOR
        if count % 2 == 0:
            background_color = "dark slate gray"
        pkmn_rows.append(
            [
                sg.Checkbox("Caught?", default=pkmn["Complete"], background_color=background_color),
                sg.Text(
                    f"{pkmn['PDex']} / {pkmn['NDex']} - {pkmn['Name']} - {' '.join(current_form)}",
                    background_color=background_color,
                ),
                sg.Push(background_color=background_color),
                sg.Text(
                    calculate_box_row_pos(count),
                    background_color=background_color,
                    key=f"-POSITION-{count}-",
                ),
            ]
        )
    halfway = int(len(pkmn_rows) / 2)
    return [
        sg.Column(
            pkmn_rows[:halfway],
            vertical_scroll_only=True,
            scrollable=True,
            size=(600, 300),
            key="-PKMN-0-",
        ),
        sg.Column(
            pkmn_rows[halfway:],
            vertical_scroll_only=True,
            scrollable=True,
            size=(600, 300),
            key="-PKMN-1-",
        ),
    ]


list_pkmn = generate_pkmn_rows()

layout = [
    [sg.Text("Gotta Catch them all!")],
    list_pkmn,
    [
        sg.Save(),
        sg.Exit(),
        sg.Push(),
        sg.Text("Progress:"),
        sg.ProgressBar(max_value=len(pkmn_dex), key="-PROGRESS-", size=(50, 10), style="clam"),
        sg.Text(f"{len([x for x in pkmn_dex if x['Complete']])}/{len(pkmn_dex)}", key="-PROGRESS-TEXT-"),
        sg.Push(),
        sg.Text("Box Offset", justification="right"),
        sg.Spin(
            values=[x + 1 for x in range(30)],
            initial_value=STARTING_PC_BOX,
            enable_events=True,
            key="-BOXOFFSET-",
        ),
    ],
]

window = sg.Window("Perfect Living Dex", layout)

while True:
    # Check for events. Will fire off a __TIMEOUT__ every TIMEOUT milliseconds if no events happen
    event, values = window.read(timeout=10000)
    logger.debug(f"GUI > event {event} with {values}")
    if event == "-BOXOFFSET-":
        STARTING_PC_BOX = values["-BOXOFFSET-"]
        for count in range(len(pkmn_dex)):
            window[f"-POSITION-{count}-"].update(value=calculate_box_row_pos(count))
        window.refresh()
    elif event == "Save":
        settings = {}
        for k, v in values.items():
            if k == "-BOXOFFSET-":
                settings[k] = v
            if isinstance(k, int):
                pkmn_dex[k]["Complete"] = v
        with open(JSON_FILE, "w", encoding="windows-1252") as pkmn_json:
            json.dump(pkmn_dex, pkmn_json, indent=2)
        with open(SETTINGS_FILE, "w") as settings_json:
            json.dump(settings, settings_json, indent=2)
    elif event == sg.WIN_CLOSED or event == "Exit":
        break
    if True:
        window["-PROGRESS-"].update(len([x for x in pkmn_dex if x["Complete"]]))
        window["-PROGRESS-TEXT-"].update(f"{len([x for x in pkmn_dex if x['Complete']])}/{len(pkmn_dex)}")

window.close()
