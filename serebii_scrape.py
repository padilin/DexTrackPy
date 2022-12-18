from __future__ import annotations

import json
import time
from pathlib import Path

from typing import Tuple, List

import httpx as httpx
from bs4 import BeautifulSoup

from loguru import logger


def get_sv_pokedex() -> List[str]:
    pokedex_name = "Paldea Pokédex"
    response = get_url("https://www.serebii.net/pokedex-sv/")

    dex_soup = BeautifulSoup(response.content.decode(response.encoding), "lxml")
    raw_dex_list = dex_soup.find("option", string=pokedex_name).parent
    return [x["value"] for x in raw_dex_list.find_all("option") if x.text != pokedex_name]


def get_pkmn_page(url: str):
    response = get_url(url)
    pkmn_dict = {}
    pkmn_soup = BeautifulSoup(response.content.decode(response.encoding), "lxml")

    get_name_no_gender_from_serebii(pkmn_dict, pkmn_soup)
    get_forms_from_serebii(pkmn_dict, pkmn_soup)
    return pkmn_dict


def get_name_no_gender_from_serebii(pkmn_dict, pkmn_soup):
    # <table> <- .parent.parent (holds all the rows in tr tags)
    #     <tr> <- .parent (holds all the headers in td tags) AKA parent.parent.find_all(tr)[0]
    #         <td> Headers
    #     <tr> <- parent.parent.find_all(tr)[1]
    #          <td> Data
    name_no_gender_row = pkmn_soup.find("td", class_="fooevo", string="Name").parent.parent
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
            pkmn_dict["No."][item.text.rstrip(": ")] = int(data[idx + 1].text.replace("#", ""))
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
    #                 tbody
    #                     tr <- alt_form_row.parent, this row contains all the forms
    #                         td class pkmn <- alt_form_row / alt_form_header.parent.parent.find(td, class pkmn)

    # searches for header
    if alt_form_header := serebii_soup.find(
        "td", class_="fooevo", string=search_string
    ):
        # first .parent is the row, second .parent is the table
        alt_form_table = alt_form_header.parent.parent
        if alt_form_table:
            alt_form_row = alt_form_table.find("td", class_="pkmn").parent
            if alt_form_row:
                return [form.b.text for form in alt_form_row]
    return None


def get_url(url: str) -> httpx.Response:
    with httpx.Client(event_hooks={"request": [_log_request], "response": [_log_response]}) as client:
        response = client.get(url)
        if response.status_code == 200:
            return response


def _log_request(request: httpx.Request):
    delay = 2
    logger.info(f"Resting for {delay} seconds to self-throttle")
    time.sleep(delay)
    logger.info(f"Request Event Hook: {request.method} {request.url}")


def _log_response(response: httpx.Response):
    request = response.request
    logger.info(f"Response event hook: {request.method} {request.url} - Status {response.status_code}")


def generate_data(data_file: str | Path):
    # Pull list of pkmn urls from serebii
    # TODO: expose way to start from specific pkmn number, perhaps by index slice list from get_sv_pokedex?
    list_of_pkmn_urls = [f"https://serebii.net/{url}" for url in get_sv_pokedex()]
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
                for gender_form in pkmn["Gender Forms"]:
                    modify_all_forms.append(f"{gender_form}+{alt_form}")
            all_forms = modify_all_forms
        # Fill out an entry for each unique gender + alt form
        for form in all_forms:
            pkmn_list.append({
                "Name": pkmn["Name"],
                "Form": form,
                "PDex": pkmn["No."]["Paldea"],
                "NDex": pkmn["No."]["National"],
                "Complete": False,
            })
        # Save file. Encoding is from Serebii webpage.
        with open(data_file, "w", encoding="windows-1252") as pkmn_json:
            json.dump(pkmn_list, pkmn_json, indent=2)
