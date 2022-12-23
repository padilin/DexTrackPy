from __future__ import annotations

import json
import time
from io import BytesIO
from pathlib import Path

from typing import Tuple, List

import httpx as httpx
from bs4 import BeautifulSoup
from PIL import Image

from loguru import logger


def get_sv_pokedex() -> List[str]:
    pokedex_name = "Paldea Pokédex"
    response = get_url("https://www.serebii.net/pokedex-sv/")

    dex_soup = BeautifulSoup(response.content.decode(response.encoding), "lxml")
    raw_dex_list = dex_soup.find("option", string=pokedex_name).parent
    return [
        x["value"] for x in raw_dex_list.find_all("option") if x.text != pokedex_name
    ]


def get_pkmn_page(url: str):
    response = get_url(url)
    pkmn_dict = {}
    pkmn_soup = BeautifulSoup(response.content.decode(response.encoding), "lxml")

    get_name_no_gender_from_serebii(pkmn_dict, pkmn_soup)
    get_forms_from_serebii(pkmn_dict, pkmn_soup)
    get_form_images_name(pkmn_dict, pkmn_soup)
    return pkmn_dict


def get_form_images_name(pkmn_dict, pkmn_soup):
    if pkmn_dict["Alt Forms"]:
        pkmn_dict["Form_to_Img"] = []
        for form in pkmn_dict["Alt Forms"]:
            form_image = pkmn_soup.find("img", attrs={"alt": form})
            if form_image is not None:
                pkmn_dict["Form_to_Img"].append(
                    (form, f"{form_image['src'].split(' / ')[-1]:03}")
                )
                logger.debug(f"Looking at {form} found {form_image}")
            else:
                logger.warning(
                    f"No src tag for alt form: {pkmn_dict['Name']} {form} {form_image}"
                )


def get_name_no_gender_from_serebii(pkmn_dict, pkmn_soup):
    # <table> <- .parent.parent (holds all the rows in tr tags)
    #     <tr> <- .parent (holds all the headers in td tags) AKA parent.parent.find_all(tr)[0]
    #         <td> Headers
    #     <tr> <- parent.parent.find_all(tr)[1]
    #          <td> Data
    name_no_gender_row = pkmn_soup.find(
        "td", class_="fooevo", string="Name"
    ).parent.parent
    headers = [x.text for x in name_no_gender_row.find_all("tr")[0].find_all("td")]
    for header in headers:
        # Headers might differ, so build off existing
        pkmn_dict[header] = None
    data = name_no_gender_row.find_all("tr")[1].find_all("td")
    pkmn_dict["Name"] = data[0].text
    pkmn_dict["No."] = {"Paldea": None, "National": None}
    pkmn_dict["Gender Ratio"] = {"Male": None, "Female": None}
    for idx, item in enumerate(data):
        if item.text.startswith(tuple(["Paldea:", "National:"])):
            pkmn_dict["No."][item.text.rstrip(": ")] = int(
                data[idx + 1].text.replace("#", "")
            )
        if item.text.startswith("Male ♂:"):
            pkmn_dict["Gender Ratio"]["Male"] = data[idx + 1].text
        if item.text.startswith("Female ♀:"):
            pkmn_dict["Gender Ratio"]["Female"] = data[idx + 1].text


def get_forms_from_serebii(pkmn_dict, serebii_soup: BeautifulSoup):
    # Set default gender form for when pokemon don't have gender differences
    gender_forms = ["Uniform"]
    alt_forms = None
    if forms := _get_specific_form(serebii_soup, "Alternate Forms"):
        alt_forms = forms
    if forms := _get_specific_form(serebii_soup, "Gender Differences"):
        gender_forms = forms
    pkmn_dict["Gender Forms"] = gender_forms
    pkmn_dict["Alt Forms"] = alt_forms


def _get_specific_form(serebii_soup, search_string) -> List[str] | None:
    # tbody <- alt_form_header.parent.parent
    #     tr <- alt_form_header.parent
    #         td "Alternate Forms" or "Gender Forms" <- alt_form_header
    #     tr
    #         td
    #             table
    #                 tbody <- alt_form_row.parent.parent / alt_form_table_names
    #                     tr <- alt_form_row.parent, this row contains all the forms
    #                         td class pkmn <- alt_form_row / alt_form_header.parent.parent.find(td, class pkmn)
    #                     tr <- second row

    # searches for header
    if alt_form_header := serebii_soup.find(
        "td", class_="fooevo", string=search_string
    ):
        # first .parent is the row, second .parent is the table
        alt_form_table = alt_form_header.parent.parent
        if alt_form_table:
            alt_form_table_names = alt_form_table.find(
                "td", class_="pkmn"
            ).parent.parent
            alt_form_name_rows = alt_form_table_names.find_all("tr")
            temp_combined_rows = []
            for row in alt_form_name_rows:
                found_form_names = row.find_all("td", class_="pkmn")
                if found_form_names:
                    logger.debug(
                        f"Found name in this row: {[form.b.text for form in found_form_names if form.b]}"
                    )
                    # this section is a pattern of 3 rows, 1 = name, 2 = img, 3 = blank
                    # only pattern 1, the name, has the b tag. so only if b exists in list comprehension
                    temp_combined_rows.extend(
                        [form.b.text for form in found_form_names if form.b]
                    )
            return temp_combined_rows
            # alt_form_row = alt_form_table.find("td", class_="pkmn").parent
            # if alt_form_row:
            #     return [form.b.text for form in alt_form_row]
    return None


# def _get_specific_form(serebii_soup, search_string) -> List[str] | None:
#     # tbody <- alt_form_header.parent.parent
#     #     tr <- alt_form_header.parent
#     #         td "Alternate Forms" or "Gender Forms" <- alt_form_header
#     #     tr
#     #         td
#     #             table
#     #                 tbody <- alt_form_row.parent.parent
#     #                     tr <- alt_form_row.parent, this row contains all the forms
#     #                         td class pkmn <- alt_form_row / alt_form_header.parent.parent.find(td, class pkmn)
#     #                     tr <- second row
#
#     # searches for header
#     if alt_form_header := serebii_soup.find(
#         "td", class_="fooevo", string=search_string
#     ):
#         # first .parent is the row, second .parent is the table
#         alt_form_table = alt_form_header.parent.parent
#         if alt_form_table:
#             # TODO: Support multi line Altername Forms, such as Vivillion
#             alt_form_row = alt_form_table.find("td", class_="pkmn").parent
#             if alt_form_row:
#                 return [form.b.text for form in alt_form_row]
#     return None


def get_url(url: str) -> httpx.Response:
    with httpx.Client(
        event_hooks={"request": [_log_request], "response": [_log_response]}
    ) as client:
        response = client.get(url)
        if response.status_code == 200:
            return response


def _log_request(request: httpx.Request):
    delay = 1
    logger.info(f"Resting for {delay} seconds to self-throttle")
    time.sleep(delay)
    logger.info(f"Request Event Hook: {request.method} {request.url}")


def _log_response(response: httpx.Response):
    request = response.request
    logger.info(
        f"Response event hook: {request.method} {request.url} - Status {response.status_code}"
    )


# Manual Intervention.
# Serebii lists some forms not yet available in SV
UNAVAILABLE_IN_SV = [
    ("Pikachu", "Original Cap"),
    ("Pikachu", "Hoenn Cap"),
    ("Pikachu", "Sinnoh Cap"),
    ("Pikachu", "Unova Cap"),
    ("Pikachu", "Kalos Cap"),
    ("Pikachu", "Alola Cap"),
    ("Pikachu", "Partner Cap"),
    ("Pikachu", "World Cap"),
    ("Vivillon", "Meadow Pattern"),
    ("Vivillon", "Polar Pattern"),
    ("Vivillon", "Tundra Pattern"),
    ("Vivillon", "Continental Pattern"),
    ("Vivillon", "Garden Pattern"),
    ("Vivillon", "Elegant Pattern"),
    ("Vivillon", "Icy Snow Pattern"),
    ("Vivillon", "Modern Pattern"),
    ("Vivillon", "Marine Pattern"),
    ("Vivillon", "Archipelago Pattern"),
    ("Vivillon", "High Plains Pattern"),
    ("Vivillon", "Sandstorm Pattern"),
    ("Vivillon", "River Pattern"),
    ("Vivillon", "Monsoon Pattern"),
    ("Vivillon", "Savanna Pattern"),
    ("Vivillon", "Sun Pattern"),
    ("Vivillon", "Ocean Pattern"),
    ("Vivillon", "Jungle Pattern"),
    ("Vivillon", "Poké Ball Pattern"),
    ("Raichu", "Alola Form"),
    ("Lilligant", "Hisuian Form"),
    ("Basculin", "White-Striped Form"),
    ("Meowth", "Alola Form"),
    ("Persian", "Alola Form"),
    ("Diglett", "Alola Form"),
    ("Dugtrio", "Alola Form"),
    ("Sliggoo", "Hisuian Form"),
    ("Goodra", "Hisuian Form"),
    ("Grimer", "Alola Form"),
    ("Muk", "Alola Form"),
    ("Voltorb", "Hisuian Form"),
    ("Electrode", "Hisuian Form"),
    ("Growlithe", "Hisuian Form"),
    ("Arcanine", "Hisuian Form"),
    ("Zorua", "Hisuian Form"),
    ("Zoroark", "Hisuian Form"),
    ("Sneasel", "Hisuian Form"),
    ("Mimikyu", "Busted Form"),
    ("Eiscue", "Noice Face"),
    ("Slowpoke", "Galarian Form"),
    ("Slowbro", "Galarian Form"),
    ("Slowking", "Galarian Form"),
    ("Qwilfish", "Hisuian Form"),
    ("Avalugg", "Hisuian Form"),
    ("Braviary", "Hisuian Form"),
    ("Gimmighoul", "Roaming Form"),
    ("Tauros", "Kantonian Form"),
    ("Tauros", "Paldean FormCombat Breed"),
    ("Tauros", "Paldean FormBlaze Breed"),
    ("Tauros", "Paldean FormAqua Breed"),
]
# Due to unavailable forms, some pkmn get skipped because their original form isn't listed
# Or in Tauros case, Paladean Form\nCombat Breed gets smooshed together Paladean FormCombat Breed
TO_ADD = [
    {
        "Name": "Pikachu",
        "Form": "Male",
        "PDex": 74,
        "NDex": 25,
        "Complete": False,
        "Form_Image": "025.png",
    },
    {
        "Name": "Pikachu",
        "Form": "Female",
        "PDex": 74,
        "NDex": 25,
        "Complete": False,
        "Form_Image": "025-f.png",
    },
    {
        "Name": "Tauros",
        "Form": "Uniform+Paldean Form Combat Breed",
        "PDex": 223,
        "NDex": 128,
        "Complete": False,
        "Form_Image": "128-p.png",
    },
    {
        "Name": "Tauros",
        "Form": "Uniform+Paldean Form Blaze Breed",
        "PDex": 223,
        "NDex": 128,
        "Complete": False,
        "Form_Image": "128-b.png",
    },
    {
        "Name": "Tauros",
        "Form": "Uniform+Paldean Form Aqua Breed",
        "PDex": 223,
        "NDex": 128,
        "Complete": False,
        "Form_Image": "128-a.png",
    },
]


def _generate_form_img(form, pkmn):
    national_dex = pkmn["No."]["National"]
    file_ext = ".png"
    logger.debug(f"Form {form}")
    if form in ["Uniform", "Male"]:
        return f"{national_dex:03}{file_ext}"
    elif "female" in form.lower():
        return f"{national_dex:03}-f{file_ext}"
    else:
        logger.debug(
            f"Filtering forms: {[x[1] for x in pkmn['Form_to_Img'] if x[0] == form.split('+')[1]]} with form {form}"
        )
        return [x[1] for x in pkmn["Form_to_Img"] if x[0] == form.split("+")[1]][0]


def generate_data(data_file: str | Path):
    # Pull list of pkmn urls from serebii
    # TODO: expose way to start from specific pkmn number, perhaps by index slice list from get_sv_pokedex?
    list_of_pkmn_urls = [
        f"https://serebii.net/{url}" for url in get_sv_pokedex()
    ]  # [222:223] slice to test range
    logger.debug(f"Found {len(list_of_pkmn_urls)} Pokemon urls")
    for pkmn_url in list_of_pkmn_urls:
        # process each url
        pkmn_list = []
        pkmn = get_pkmn_page(pkmn_url)
        # Open/close on each url because ths is 400 requests and saving progress is nice.
        with open(data_file, "r", encoding="windows-1252") as pkmn_json:
            if pkmn_json:
                pkmn_list = json.load(pkmn_json)
        # For perfect living dex, need each gender form (if different) and also each alt form (red flabebe, blue, etc)
        all_forms = pkmn["Gender Forms"]
        if pkmn["Alt Forms"]:
            modify_all_forms = []
            for alt_form in pkmn["Alt Forms"]:
                logger.debug(f"DEBUG FORMS: {alt_form}")
                # Skip any forms shown on Serebii, but not available
                if (pkmn["Name"], alt_form) in UNAVAILABLE_IN_SV:
                    continue
                for gender_form in pkmn["Gender Forms"]:
                    modify_all_forms.append(f"{gender_form}+{alt_form}")
            all_forms = modify_all_forms
        # Fill out an entry for each unique gender + alt form
        for form in all_forms:
            if (pkmn["Name"], form.replace(" ", "")) not in [
                (x["Name"], x["Form"].replace(" ", "")) for x in pkmn_list
            ]:
                pkmn_list.append(
                    {
                        "Name": pkmn["Name"],
                        "Form": form,
                        "PDex": pkmn["No."]["Paldea"],
                        "NDex": pkmn["No."]["National"],
                        "Complete": False,
                        "Form_Image": _generate_form_img(form, pkmn),
                    }
                )
            else:
                logger.debug(f"Found duplicate {pkmn['Name']} {form}")
        # Save file. Encoding is from Serebii webpage.
        with open(data_file, "w", encoding="windows-1252") as pkmn_json:
            json.dump(pkmn_list, pkmn_json, indent=2)
    # Correct missing data
    with open(data_file, "r", encoding="windows-1252") as pkmn_json:
        pkmn_list = json.load(pkmn_json)
        # Missing data on Serebii
        for manual_added in TO_ADD:
            if (manual_added["Name"], manual_added["Form"]) not in [
                (x["Name"], x["Form"]) for x in pkmn_list
            ]:
                pkmn_list.append(manual_added)
    with open(data_file, "w", encoding="windows-1252") as pkmn_json:
        json.dump(pkmn_list, pkmn_json, indent=2)


def generate_images(data_file: str | Path, img_file: str | Path):
    pkmn_list = []
    with open(data_file, "r", encoding="windows-1252") as pkmn_json:
        pkmn_list = json.load(pkmn_json)
    logger.debug(f"Starting image checking and downloading.")
    for pkmn in pkmn_list:
        image_file_suffix = pkmn["Form_Image"]

        image_file_url = (
            f"https://serebii.net/scarletviolet/pokemon/new/{image_file_suffix}"
        )
        image_file_path = f"{img_file}\\normal\\{image_file_suffix}"
        if (
            not Path(image_file_path).exists()
            and not Path(f"{image_file_path}.err").exists()
        ):
            logger.debug(f"{pkmn['Name']} checking image")
            image_file_content = get_url(image_file_url)
            if image_file_content:
                image_file_pillow = Image.open(BytesIO(image_file_content.content))
                image_file_pillow.save(image_file_path)
            else:
                Path(f"{image_file_path}.err").touch(exist_ok=True)
        else:
            logger.debug(f"Image exists {pkmn['Name']} at {image_file_path}")

        shiny_file_url = f"https://www.serebii.net/Shiny/SV/new/{image_file_suffix}"
        shiny_file_path = f"{img_file}\\shiny\\{image_file_suffix}"
        if (
            not Path(shiny_file_path).exists()
            and not Path(f"{shiny_file_path}.err").exists()
        ):
            shiny_file_content = get_url(shiny_file_url)
            if shiny_file_content:
                image_file_pillow = Image.open(BytesIO(shiny_file_content.content))
                image_file_pillow.save(shiny_file_path)
            else:
                Path(f"{shiny_file_path}.err").touch(exist_ok=True)

        sprite_file_url = f"https://serebii.net/pokedex-sv/icon/new/{image_file_suffix}"
        sprite_file_path = f"{img_file}\\sprite\\{image_file_suffix}"
        if (
            not Path(sprite_file_path).exists()
            and not Path(f"{sprite_file_path}.err").exists()
        ):
            sprite_file_content = get_url(sprite_file_url)
            if sprite_file_content:
                image_file_pillow = Image.open(BytesIO(sprite_file_content.content))
                image_file_pillow.save(sprite_file_path)
            else:
                sprite_file_content = get_url(sprite_file_url.replace("-f", ""))
                if sprite_file_content:
                    image_file_pillow = Image.open(BytesIO(sprite_file_content.content))
                    image_file_pillow.save(sprite_file_path)
                else:
                    Path(f"{sprite_file_path}.err").touch(exist_ok=True)
