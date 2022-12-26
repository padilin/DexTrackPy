from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import List, Tuple

import PIL.Image
import PySimpleGUI as sg
from loguru import logger

from pysvscrape.serebii_scrape import (
    PkmnEntry,
    generate_data,
    generate_images,
    load_dex,
    save_dex,
)

# JSON_FILE = "data/dex_with_img.json"
JSON_FILE = "data/dex_v3.1.json"
IMAGE_FOLDER = "images"
generate_data(JSON_FILE)
generate_images(JSON_FILE, IMAGE_FOLDER)
pkmn_dex = load_dex(JSON_FILE)

sg.theme("Dark Green 7")


SETTINGS_FILE = "data/settings.json"
# Defaults
STARTING_PC_BOX = 1


def load_settings(settings_file: str | Path):
    # Fun fact, Path(Path()) works the same as Path(str), and it makes mypy pass
    settings_path = Path(settings_file)
    if settings_path.exists():
        with open(settings_path) as settings_json:
            settings = json.load(settings_json)
            if "-BOXOFFSET-" in settings:
                STARTING_PC_BOX = settings["-BOXOFFSET-"]


load_settings(SETTINGS_FILE)


def calculate_box_row_pos(count: int) -> tuple[int, int, int]:
    # floor value of division, then + 1 because PC boxes aren't 0-index
    box = count // 30 + STARTING_PC_BOX
    # Find position inside box
    _box_index = count % 30
    # Row finds how many times 6 goes into index rounded down to find row number 0 index. Then 1 index answer.
    row = _box_index // 6 + 1
    # Pos uses modulo to count 0 to 5 then start over 0 to 5 to find column in pc box. Then 1 index answer.
    pos = _box_index % 6 + 1

    return box, row, pos


class RecordedPkmnTuple:
    """This is data/format that is important to the GUI"""

    def __init__(
        self,
        pkmn: PkmnEntry,
        form_name: str,
        form_img: str,
        form_complete: bool,
        box: int,
        row: int,
        pos: int,
        count: int,
    ):
        self.pkmn = pkmn
        self.form_name = form_name
        self.form_img = form_img
        self.form_complete = form_complete
        self.box = box
        self.row = row
        self.pos = pos
        self.count = count
        self.key = f"-POSITION-{self.count}-"

    def update_box_row_pos(self):
        self.box, self.row, self.pos = calculate_box_row_pos(self.count)

    @property
    def box_location_text(self):
        return f"Box {self.box:02}, Row {self.row:02}, Position {self.pos:02}"

    @property
    def pdex_name_form_text(self):
        return f"{self.pkmn.pdex} / {self.pkmn.ndex} - {self.pkmn.name} - {self.form_name.replace('|', ' ')}"


record_pkmn: list[RecordedPkmnTuple] = []


def generate_pkmn_layout() -> list[sg.Element]:
    background_color = sg.DEFAULT_BACKGROUND_COLOR
    alt_background_color = "dark slate gray"
    pkmn_layout = []
    count = 0
    for pkmn in pkmn_dex:
        for unique_model in pkmn.unique_model_images:
            if count % 2 == 0:
                # Highlight every other row
                background_color = alt_background_color
            split_form_name = unique_model.form_name.replace("|", " ")
            box, row, pos = calculate_box_row_pos(count)
            this_form = RecordedPkmnTuple(
                pkmn,
                unique_model.form_name,
                unique_model.img_name,
                unique_model.complete,
                box,
                row,
                pos,
                count,
            )
            record_pkmn.append(this_form)
            # Generate: {check box for caught} {Dex number} {National dex number} {name} {push right} {box, row, pos}
            pkmn_layout.append(
                [
                    sg.Checkbox(
                        "Caught?",
                        default=unique_model.complete,
                        background_color=background_color,
                        key=f"-CAUGHT-{this_form.count}",
                        enable_events=True,
                    ),
                    sg.Text(
                        this_form.pdex_name_form_text,
                        background_color=background_color,
                    ),
                    sg.Push(background_color=background_color),
                    sg.Text(
                        this_form.box_location_text,
                        background_color=background_color,
                        key=f"-POSITION-{count}-",
                    ),
                ]
            )
            count += 1
    halfway = int(len(pkmn_layout) / 2)
    return [
        sg.Column(
            pkmn_layout[:halfway],
            vertical_scroll_only=True,
            scrollable=True,
            size=(600, 300),
            key="-PKMN-0-",
        ),
        sg.Column(
            pkmn_layout[halfway:],
            vertical_scroll_only=True,
            scrollable=True,
            size=(600, 300),
            key="-PKMN-1-",
        ),
    ]


def generate_complete_progress() -> tuple[int, int]:
    return int(len([x for x in record_pkmn if x.form_complete])), int(len(record_pkmn))


def generate_box_entry(
    box: int, row: int, pos: int
) -> tuple[list[sg.Element], list[sg.Element], list[sg.Element]]:
    # Pull exact box, row, pos out of loaded in dex
    entry = [x for x in record_pkmn if x.box == box and x.row == row and x.pos == pos]
    if len(entry) < 1:
        return (
            [
                sg.Button(
                    "",
                    image_data=convert_to_bytes(f"images\\sprite\\blank.png", (40, 40)),
                ),
                sg.Push(),
            ],
            [sg.VPush(), sg.Text(""), sg.Push()],
            [sg.VPush(), sg.Text(""), sg.Push()],
        )
    if len(entry) > 1:
        logger.warning(
            f"Found more than 1 match for Box {box} Row {row} Pos {pos} in {entry}"
        )
        return (
            [
                sg.Button(
                    "",
                    image_data=convert_to_bytes(f"images\\sprite\\blank.png", (40, 40)),
                ),
                sg.Push(),
            ],
            [sg.VPush()],
            [sg.VPush()],
        )
    found_entry = entry[0]
    border = 0
    if found_entry.form_complete:
        # Make completed forms stand out
        border = 4
    image = [
        sg.Button(
            "",
            image_data=convert_to_bytes(f"images\\sprite\\{found_entry.form_img}"),
            key=found_entry.form_img,
            button_color=(sg.theme_text_color(), sg.theme_background_color()),
            border_width=border,
        ),
        sg.Push(),
    ]
    name = [sg.Text(f"{found_entry.pkmn.name}"), sg.Push()]
    form = [sg.Text(f"{found_entry.form_name}"), sg.Push()]
    return image, name, form


def make_window1():
    current_progress, total_length = generate_complete_progress()
    layout = [
        [sg.Text("Gotta Catch them all!")],
        generate_pkmn_layout(),
        [
            sg.Save(),
            sg.Push(),
            sg.Text("Progress:"),
            sg.ProgressBar(
                max_value=len(pkmn_dex), key="-PROGRESS-", size=(50, 10), style="clam"
            ),
            sg.Text(
                f"{current_progress} / {total_length}",
                key="-PROGRESS-TEXT-",
            ),
            sg.Push(),
            sg.Exit(),
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
    """
    Will convert into bytes and optionally resize an image that is a file or a base64 bytes object.
    Turns into  PNG format in the process so that can be displayed by tkinter
    :param file_or_bytes: either a string filename or a bytes base64 image object
    :type file_or_bytes:  (Union[str, bytes])
    :param resize:  optional new size
    :type resize: (Tuple[int, int] or None)
    :return: (bytes) a byte-string object
    :rtype: (bytes)
    """
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
        scale = min(new_height / cur_height, new_width / cur_width)
        img = img.resize(
            (int(cur_width * scale), int(cur_height * scale)),
            PIL.Image.Resampling.LANCZOS,
        )
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    del img
    return bio.getvalue()
    pass


def make_window2():
    # pkmn_name_location = []
    # Pulling information for ease of use
    # for count, pkmn in enumerate(pkmn_dex):
    #     if len(pkmn.name) > 0:
    #         longest_name = len(pkmn.name)
    #     box, row, pos = calculate_box_row_pos(count)
    #     pkmn_name_location.append((pkmn.name, pkmn["Form_Image"], box, row, pos, pkmn["Form"], pkmn.complete))
    # Get important information to creating boxes
    box_nos, pos_nos, row_nos = generate_box_stats()
    boxes_layout = [
        [sg.TabGroup(generate_all_boxes(box_nos, pos_nos, row_nos), key="-BOXES-")]
    ]
    return sg.Window("Boxes", boxes_layout, finalize=True)


def generate_box_stats():
    first_box_no = min([x.box for x in record_pkmn])
    last_box_no = max([x.box for x in record_pkmn])
    box_nos = range(first_box_no, last_box_no + 1)
    row_nos = range(1, 5 + 1)
    pos_nos = range(1, 6 + 1)
    return box_nos, pos_nos, row_nos


def generate_all_boxes(box_nos, pos_nos, row_nos):
    tab_group_contents = []
    # Each box is a sg.Tab("Box {No}", [list of 15 lists. 5 name, 5 form names, and 5 image each])
    for box_no in box_nos:
        tab_contents = []
        for row_no in row_nos:
            # Make the sets of 2 rows. Text and image
            name_row_contents = [sg.Push()]
            image_row_contents = [sg.Push()]
            form_name_row_contents = [sg.Push()]
            for pos_no in pos_nos:
                image, name, form = generate_box_entry(box_no, row_no, pos_no)
                name_row_contents.extend(name)
                image_row_contents.extend(image)
                form_name_row_contents.extend(form)
            if image_row_contents:
                tab_contents.append(image_row_contents)
                tab_contents.append(name_row_contents)
                tab_contents.append(form_name_row_contents)
        if tab_contents:
            tab_group_contents.append(
                sg.Tab(f"Box {box_no:02}", tab_contents, element_justification="c")
            )
    return [tab_group_contents]


def make_info_window():
    info_layout = [
        [
            sg.Push(),
            sg.Image(
                convert_to_bytes(f"images\\normal\\blank.png"), key="-NORMAL-DETAIL-"
            ),
            sg.Push(),
        ],
        [sg.Push(), sg.Text("Normal image", justification="c"), sg.Push()],
        [
            sg.Push(),
            sg.Image(
                convert_to_bytes(f"images\\shiny\\blank.png"), key="-SHINY-DETAIL-"
            ),
            sg.Push(),
        ],
        [sg.Push(), sg.Text("Shiny image", justification="c"), sg.Push()],
        [
            sg.Push(),
            sg.Button("Exit", enable_events=True, key="-CLOSE-DETAIL-"),
            sg.Push(),
        ],
    ]
    return sg.Window(
        "Pokemon Image",
        info_layout,
        grab_anywhere=True,
        no_titlebar=True,
        finalize=True,
    )


def main():
    window1, window2, info_window = make_window1(), make_window2(), make_info_window()

    info_window.disappear()

    progress, maximum = generate_complete_progress()
    window1["-PROGRESS-"].update(f"{progress}")
    window1["-PROGRESS-TEXT-"].update(f"{progress} / {maximum}")
    window1.refresh()

    try:
        while True:
            # Check for events. Will fire off a __TIMEOUT__ every TIMEOUT milliseconds if no events happen
            window, event, values = sg.read_all_windows(timeout=10000)
            logger.debug(f"GUI > windows {window} event {event} with {values}")
            if event == "-BOXOFFSET-":
                STARTING_PC_BOX = values["-BOXOFFSET-"]
                for pkmn in record_pkmn:
                    pkmn.update_box_row_pos()
                    window1[pkmn.key].update(pkmn.box_location_text)
                window1.refresh()

                group_of_boxes = window2.find_element("-BOXES-")
                box_nos, pos_nos, row_nos = generate_box_stats()
                group_of_boxes.update(generate_all_boxes(box_nos, pos_nos, row_nos))
                window2.refresh()
            elif event == "Save":
                save_everything(values)
            elif event in [f"-CAUGHT-{x.count}" for x in record_pkmn]:
                save_everything(values)
            elif (window == window1 or window == window2) and (
                event == sg.WIN_CLOSED or event == "Exit"
            ):
                break
            elif event == "-CLOSE-DETAIL-":
                info_window.disappear()
            elif window == window2 and ".png" in event:
                image_suffix = event
                update_info_window(image_suffix, info_window)
            elif window == info_window and event == "Exit":
                info_window.close()
            if True:
                progress, maximum = generate_complete_progress()
                window1["-PROGRESS-"].update(f"{progress}")
                window1["-PROGRESS-TEXT-"].update(f"{progress} / {maximum}")
                window2.refresh()
    except Exception as e:
        sg.Print(
            "Exception in the program: ", sg.__file__, e, keep_on_top=True, wait=True
        )

    window1.close()
    window2.close()
    info_window.close()


def update_info_window(image_suffix, info_window):
    image_info = info_window.find_element("-NORMAL-DETAIL-")
    image_info.update(convert_to_bytes(f"images\\normal\\{image_suffix}"))
    shiny_info = info_window.find_element("-SHINY-DETAIL-")
    shiny_info.update(convert_to_bytes(f"images\\shiny\\{image_suffix}"))
    info_window.reappear()
    info_window.refresh()
    info_window.force_focus()


def save_everything(values):
    settings = {}
    for k, v in values.items():
        if k == "-BOXOFFSET-":
            settings[k] = v
        elif k.startswith("-CAUGHT-"):
            entry_no = int(k.lstrip("-CAUGHT-"))
            entry = [x for x in record_pkmn if x.count == entry_no][0]
            entry.form_complete = v
            for unique in entry.pkmn.unique_model_images:
                if unique.form_name == entry.form_name:
                    unique.complete = entry.form_complete
    save_dex(JSON_FILE, pkmn_dex)
    with open(SETTINGS_FILE, "w") as settings_json:
        json.dump(settings, settings_json, indent=2)


if __name__ == "__main__":
    main()
