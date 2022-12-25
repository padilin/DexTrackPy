import base64
import io
import json
from pathlib import Path
from typing import Tuple, List

import PIL.Image
import PySimpleGUI as sg
from loguru import logger

from serebii_scrape import generate_data


# JSON_FILE = "data/dex_with_img.json"
JSON_FILE = "data/delete_me.json"
if not Path(JSON_FILE).exists():
    with open(JSON_FILE, "w", encoding="windows-1252") as pkmn_json:
        json.dump([], pkmn_json, indent=2)
    generate_data(JSON_FILE)

sg.theme("Dark Green 7")

pkmn_dex = []
pkmn_rows = []
with open(JSON_FILE, "r", encoding="windows-1252") as pkmn_json:
    pkmn_dex = json.load(pkmn_json)
    pkmn_dex = sorted(pkmn_dex, key=lambda d: d["PDex"])


SETTINGS_FILE = "data/settings.json"
STARTING_PC_BOX = 1
if Path(SETTINGS_FILE).exists():
    with open(SETTINGS_FILE, "r") as settings_json:
        settings = json.load(settings_json)
        STARTING_PC_BOX = settings["-BOXOFFSET-"]


def calculate_box_row_pos(count: int) -> Tuple[int, int, int]:
    # floor value of division, then + 1 because PC boxes aren't 0-index
    box = count // 30 + STARTING_PC_BOX
    # Find position inside box
    _box_index = count % 30
    # Row finds how many times 6 goes into index rounded down to find row number 0 index. Then 1 index answer.
    row = _box_index // 6 + 1
    # Pos uses modulo to count 0 to 5 then start over 0 to 5 to find column in pc box. Then 1 index answer.
    pos = _box_index % 6 + 1

    return box, row, pos


def generate_pkmn_rows() -> List[sg.Element]:
    for count, pkmn in enumerate(pkmn_dex):
        # Make string description of form nicer to read
        current_form = pkmn["Form"].replace("Uniform", "Uni").split("+")
        background_color = sg.DEFAULT_BACKGROUND_COLOR
        if count % 2 == 0:
            background_color = "dark slate gray"
        box, row, pos = calculate_box_row_pos(count)
        pkmn_rows.append(
            [
                sg.Checkbox(
                    "Caught?",
                    default=pkmn["Complete"],
                    background_color=background_color,
                ),
                sg.Text(
                    f"{pkmn['PDex']} / {pkmn['NDex']} - {pkmn['Name']} - {' '.join(current_form)}",
                    background_color=background_color,
                ),
                sg.Push(background_color=background_color),
                sg.Text(
                    f"Box {box:02}, Row {row:02}, Position {pos:02}",
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


def make_window1():
    layout = [
        [sg.Text("Gotta Catch them all!")],
        list_pkmn,
        [
            sg.Save(),
            sg.Exit(),
            sg.Push(),
            sg.Text("Progress:"),
            sg.ProgressBar(
                max_value=len(pkmn_dex), key="-PROGRESS-", size=(50, 10), style="clam"
            ),
            sg.Text(
                f"{len([x for x in pkmn_dex if x['Complete']])}/{len(pkmn_dex)}",
                key="-PROGRESS-TEXT-",
            ),
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
    return sg.Window("Perfect Living Dex", layout, finalize=True)


def convert_to_bytes(file_or_bytes, resize=None):
    '''
    Will convert into bytes and optionally resize an image that is a file or a base64 bytes object.
    Turns into  PNG format in the process so that can be displayed by tkinter
    :param file_or_bytes: either a string filename or a bytes base64 image object
    :type file_or_bytes:  (Union[str, bytes])
    :param resize:  optional new size
    :type resize: (Tuple[int, int] or None)
    :return: (bytes) a byte-string object
    :rtype: (bytes)
    '''
    if isinstance(file_or_bytes, str):
        img = PIL.Image.open(file_or_bytes)
    else:
        try:
            img = PIL.Image.open(io.BytesIO(base64.b64decode(file_or_bytes)))
        except Exception as e:
            dataBytesIO = io.BytesIO(file_or_bytes)
            img = PIL.Image.open(dataBytesIO)

    cur_width, cur_height = img.size
    if resize:
        new_width, new_height = resize
        scale = min(new_height/cur_height, new_width/cur_width)
        img = img.resize((int(cur_width*scale), int(cur_height*scale)), PIL.Image.ANTIALIAS)
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    del img
    return bio.getvalue()
    pass


def make_window2():
    pkmn_name_location = []
    longest_name = 0
    # Pulling information for ease of use
    for count, pkmn in enumerate(pkmn_dex):
        if len(pkmn["Name"]) > 0:
            longest_name = len(pkmn["Name"])
        box, row, pos = calculate_box_row_pos(count)
        pkmn_name_location.append((pkmn["Name"], pkmn["Form_Image"], box, row, pos, pkmn["Form"], pkmn["Complete"]))
    # Get important information to creating boxes
    first_box_no = min([x[2] for x in pkmn_name_location])
    last_box_no = max([x[2] for x in pkmn_name_location])
    box_nos = range(first_box_no, last_box_no + 1)
    row_nos = range(1, 5+1)
    pos_nos = range(1, 6+1)
    tab_group_contents = []
    # Each box is a sg.Tab("Box {No}", [list of 10 lists. 5 text and 5 image each])
    for box_no in box_nos:
        tab_contents = []
        for row_no in row_nos:
            # Make the sets of 2 rows. Text and image
            header_row_contents = [sg.Push()]
            image_row_contents = [sg.Push()]
            form_row_contents = [sg.Push()]
            for pos_no in pos_nos:
                if found_pkmn := [(x[0], x[1], x[5], x[6]) for x in pkmn_name_location if x[2] == box_no and x[3] == row_no and x[4] == pos_no]:
                    pkmn_name, img_path_suffix, form_name, is_complete = found_pkmn[0]
                    border = 0
                    if is_complete:
                        border = 4
                    # image_row_contents.append(sg.Image(convert_to_bytes(f"images\\sprite\\{img_path_suffix}")))
                    image_row_contents.append(sg.Button("", image_data=convert_to_bytes(f"images\\sprite\\{img_path_suffix}"), key=img_path_suffix, button_color=(sg.theme_text_color(), sg.theme_background_color()), border_width=border))
                    header_row_contents.append(sg.Text(f"{pkmn_name}", justification="c", size=(longest_name, None)))
                    form_row_contents.append(sg.Text(f"{form_name}", justification="c", size=(longest_name, None)))
                    image_row_contents.append(sg.Push())
                    header_row_contents.append(sg.Push())
                    form_row_contents.append(sg.Push())
            if image_row_contents:
                tab_contents.append(image_row_contents)
                tab_contents.append(header_row_contents)
                tab_contents.append(form_row_contents)
        if tab_contents:
            tab_group_contents.append(sg.Tab(f"Box {box_no:02}", tab_contents, element_justification="c"))
    return sg.Window("Boxes", [[sg.TabGroup([tab_group_contents])]], finalize=True)


def make_info_window():
    return sg.Window("Pokemon Image", [[sg.Exit()]], grab_anywhere=True, no_titlebar=True, finalize=True)


def main():
    window1, window2, info_window = make_window1(), make_window2(), None

    try:
        while True:
        # Check for events. Will fire off a __TIMEOUT__ every TIMEOUT milliseconds if no events happen
            window, event, values = sg.read_all_windows(timeout=10000)
            logger.debug(f"GUI > windows {window} event {event} with {values}")
            if event == "-BOXOFFSET-":
                if window == window1:
                    STARTING_PC_BOX = values["-BOXOFFSET-"]
                    for count in range(len(pkmn_dex)):
                        box, row, pos = calculate_box_row_pos(count)
                        window1[f"-POSITION-{count}-"].update(value=f"Box {box:02}, Row {row:02}, Position {pos:02}")
                    window1.refresh()
            elif event == "Save" and window == window1:
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
            elif (window == window1 or window == window2) and (event == sg.WIN_CLOSED or event == "Exit"):
                break
            elif window == window2 and ".png" in event:
                image_suffix = event
                pkmn_info_layout = [[sg.Push(), sg.Image(convert_to_bytes(f"images\\normal\\{image_suffix}")), sg.Push()], [sg.Push(), sg.Text("Normal image", justification="c"),sg.Push()], [sg.Push(), sg.Image(convert_to_bytes(f"images\\shiny\\{image_suffix}")), sg.Push()], [sg.Push(), sg.Text("Shiny image", justification="c"), sg.Push()], [sg.Push(), sg.Exit(), sg.Push()]]
                logger.info(f"Displaying Pokemon image {image_suffix}")
                info_window = sg.Window("Pokemon Image", pkmn_info_layout, grab_anywhere=True, no_titlebar=True, finalize=True)
            elif window == info_window and event == "Exit":
                info_window.close()
            if True:
                window1["-PROGRESS-"].update(len([x for x in pkmn_dex if x["Complete"]]))
                window1["-PROGRESS-TEXT-"].update(
                    f"{len([x for x in pkmn_dex if x['Complete']])}/{len(pkmn_dex)}"
                )
                window2.refresh()
    except Exception as e:
        sg.Print("Exception in the program: ", sg.__file__, e, keep_on_top=True, wait=True)

    window1.close()
    window2.close()
    if info_window is not None:
        info_window.close()


if __name__ == "__main__":
    main()
