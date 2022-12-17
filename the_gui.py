import json
from pathlib import Path

import PySimpleGUI as sg
from loguru import logger

from serebii_scrape import generate_data


JSON_FILE = "data/dex.json"
if not Path(JSON_FILE).exists():
    with open(f"data/dex.json", "w", encoding="windows-1252") as pkmn_json:
        json.dump([], pkmn_json, indent=2)
    generate_data(JSON_FILE)

sg.theme("Dark Green 7")

pkmn_dex = []
pkmn_rows = []
with open(f"data/dex.json", "r", encoding="windows-1252") as pkmn_json:
    pkmn_dex = json.load(pkmn_json)


def generate_pkmn_rows():
    for pkmn in pkmn_dex:
        current_form = pkmn["Form"].replace("Uniform", "Uni").split("+")
        pkmn_rows.append([
            sg.Checkbox("Caught?", default=pkmn["Complete"]),
            sg.Text(f"{pkmn['PDex']} / {pkmn['NDex']} - {pkmn['Name']} - {' '.join(current_form)}", background_color="dark slate gray")
        ])
    halfway = int(len(pkmn_rows) / 2)
    return [sg.Column(pkmn_rows[:halfway], vertical_scroll_only=True, scrollable=True, size=(500, 300),),
            sg.Column(pkmn_rows[halfway:], vertical_scroll_only=True, scrollable=True, size=(500, 300))]


list_pkmn = generate_pkmn_rows()

layout = [[sg.Text("Gotta Catch them all!")],
          list_pkmn,
          [sg.Save(), sg.Exit()]]

window = sg.Window("Perfect Living Dex", layout)

while True:
    event, values = window.read()
    logger.debug(f"GUI > event {event} with {values}")
    if event == "Save":
        for k, v in values.items():
            pkmn_dex[k]["Complete"] = v
        with open(f"data/dex.json", "w", encoding="windows-1252") as pkmn_json:
            json.dump(pkmn_dex, pkmn_json, indent=2)
    if event == sg.WIN_CLOSED or event == "Exit":
        break

window.close()
