from __future__ import annotations

import json
import shelve
import time
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import List, Literal

import httpx as httpx
from PIL import Image
from bs4 import BeautifulSoup
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
    pkmn_entry = PkmnEntry()
    pkmn_soup = BeautifulSoup(response.content.decode(response.encoding), "lxml")

    get_name_no_gender_from_serebii(pkmn_entry, pkmn_soup)
    get_forms_from_serebii(pkmn_entry, pkmn_soup)
    get_form_images_name(pkmn_entry, pkmn_soup)
    if len(pkmn_entry.unique_model_images) < 1:
        # This means there were no forms left after filtering by list of unavailable in sv or wierd serebii format
        # Weird serebii formats are manually added later
        return None
    logger.debug(f"Made pkmn {pkmn_entry}")
    return pkmn_entry


@dataclass
class PkmnEntry:
    name: str = "Not yet set"
    pdex: int = 0
    ndex: int = 0
    male: float = 0
    female: float = 0
    japanese: str = ""
    french: str = ""
    german: str = ""
    korean: str = ""
    complete: bool = False
    # types: None = None

    gender_models: List[Literal["Uniform", "Male", "Female"]] = field(
        default_factory=list
    )
    form_models: List[str] = field(default_factory=list)

    unique_model_images: List[FormTuple] = field(default_factory=list)

    def get_unique_models(self):
        # There is always a gender model. Uniform, Male, or Female
        # There may not be a form model.
        # To get a unique name for each model, we combine Gender|Form or just use Gender
        # This drives actual # of unique pokemon and images for them
        unique_models = []
        if len(self.form_models) > 0:
            for gender in self.gender_models:
                for form in self.form_models:
                    unique_models.append(f"{gender}|{form}")
        else:
            unique_models = self.gender_models
        return unique_models

    def asdict(self):
        unique_model_images_list = []
        for unique in self.unique_model_images:
            unique_model_images_list.append((unique.form_name, unique.img_name))
        return {
            "name": self.name,
            "pdex": self.pdex,
            "ndex": self.ndex,
            "male": self.male,
            "female": self.female,
            "japanese": self.japanese,
            "french": self.french,
            "german": self.german,
            "korean": self.korean,
            "complete": self.complete,
            # "types": self.types,
            "gender_models": self.gender_models,
            "form_models": self.form_models,
            "unique_model_images": unique_model_images_list,
        }

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return (
            f"{self.name} / Japan: {self.japanese} / French: {self.french} / German: {self.german} / "
            f"Korean: {self.korean} | N #{self.ndex} | P #{self.pdex} | Male: {self.male}% Female: {self.female}% "
            f"| Models: Gender {self.gender_models} Form {self.form_models} Unique {self.unique_model_images}"
        )


def _convert_to_at_least_3_digit(img_name: str) -> str:
    """Sometimes Serebii alt text has the wrong, less than 3 digit, number"""
    pulled_apart = []
    if "-" in img_name:
        # Form image, so it has NNN-F.png
        pulled_apart = img_name.split("-")
    else:
        pulled_apart = img_name.split(".")
    # 91.png = ["91", "png"] or 25-f.png = ["25", "f.png"]
    if len(pulled_apart[0]) < 3:
        # Z-fill works perfect.
        # "3".zfill(3) = "003", "40".zfill(3) = "040", "500".zfill(3) = "500", "1000".zfill(3) = "1000"
        return img_name.replace(pulled_apart[0], pulled_apart[0].zfill(3))
    else:
        return img_name


class FormTuple:
    def __init__(self, form_name: str, img_name: str):
        self.form_name = form_name
        self.img_name = _convert_to_at_least_3_digit(img_name)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return f"{self.form_name} image file {self.img_name}"


def get_name_no_gender_from_serebii(pkmn_entry, pkmn_soup):
    # <table> <- .parent.parent (holds all the rows in tr tags)
    #     <tr> <- .parent (holds all the headers in td tags) AKA parent.parent.find_all(tr)[0]
    #         <td> Headers
    #     <tr> <- parent.parent.find_all(tr)[1]
    #          <td> Data
    name_no_gender_row = pkmn_soup.find(
        "td", class_="fooevo", string="Name"
    ).parent.parent
    # headers = [x.text for x in name_no_gender_row.find_all("tr")[0].find_all("td")]
    # for header in headers:
    #     # Headers might differ, so build off existing
    #     pkmn_dict[header] = None
    data = name_no_gender_row.find_all("tr")[1].find_all("td")
    pkmn_entry.name = data[0].text
    for idx, item in enumerate(data):
        # Loop through all the text. The next index, idx + 1, after a header will be the data under the header
        # There is some repeats, but we skip those. Requires more complicated bs4 filters to avoid
        # example sprigatito:
        #   start at index for "Other Names" just for this example <- Skip
        #   index + 1 = ALL langugaes in one block of text <- Skip
        #   index + 2 = the full japanese line of " Japan: \nニャオハ" <- Skip
        #   index + 3 = "Japan:" <- Match this, set pkmn_entry.japanese to next index
        #   index + 4 = "ニャオハ" <- Skip because it was set last item
        name = item.text
        if type(name) == str:
            if name.startswith("Paldea:"):
                pkmn_entry.pdex = int(data[idx + 1].text.replace("#", ""))
            if name.startswith("National:"):
                pkmn_entry.ndex = int(data[idx + 1].text.replace("#", ""))
            if name.startswith("Male ♂:"):
                male_ratio = data[idx + 1].text.replace("%", "")
                male_ratio2 = male_ratio.replace("*", "")  # thanks oinkologne
                pkmn_entry.male = float(male_ratio2)
            if name.startswith("Female ♀:"):
                female_ratio = data[idx + 1].text.replace("%", "")
                female_ratio2 = female_ratio.replace("*", "")  # thanks oinkologne
                pkmn_entry.male = float(female_ratio2)
            if name.startswith("Japan:"):
                pkmn_entry.japanese = data[idx + 1].text
            if name.startswith("French:"):
                pkmn_entry.french = data[idx + 1].text
            if name.startswith("German:"):
                pkmn_entry.german = data[idx + 1].text
            if name.startswith("Korean:"):
                pkmn_entry.korean = data[idx + 1].text
        else:
            logger.warning(f"Not string: {name}")


def get_forms_from_serebii(pkmn_entry, pkmn_soup: BeautifulSoup):
    # Set default gender form for when pokemon don't have gender differences
    gender_forms = ["Uniform"]
    alt_forms = []
    if forms := _get_specific_form(pkmn_soup, "Alternate Forms"):
        alt_forms = forms
    if forms := _get_specific_form(pkmn_soup, "Gender Differences"):
        gender_forms = forms
    pkmn_entry.gender_models = gender_forms
    pkmn_entry.form_models = alt_forms


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
    return None


def get_form_images_name(pkmn_entry, pkmn_soup):
    logger.debug(f"Pkmn entry till now: {pkmn_entry}")
    # All images are saved as f"{national dex number}{'-' if not 'Uniform' or 'Male'}{single letter to describe
    # form}.png"
    for model in pkmn_entry.get_unique_models():
        if (pkmn_entry.name, model) in UNAVAILABLE_IN_SV:
            logger.info(f"Skipping {pkmn_entry.name} {form}")
            continue
        # First check if it is an alt form, which has a Gender|Form layout
        if "|" in model:
            form = model.split("|")[1]
            logger.debug(f"Alt form found: {form}")
            # Search html for an img with an alt text of the form
            form_image = pkmn_soup.find("img", attrs={"alt": form})
            if (
                form_image is not None
                and (pkmn_entry.name, form) not in UNAVAILABLE_IN_SV
            ):
                pkmn_entry.unique_model_images.append(
                    FormTuple(model, f"{form_image['src'].split('/')[-1]}")
                )
        elif model in ("Uniform", "Male"):
            pkmn_entry.unique_model_images.append(
                FormTuple(model, f"{pkmn_entry.ndex}.png")
            )
        elif model == "Female":
            pkmn_entry.unique_model_images.append(
                FormTuple(model, f"{pkmn_entry.ndex}-f.png")
            )
        else:
            logger.debug(f"get_form_images_name model didn't match a pattern: {model}")


def download_image(url: str, path: str | Path) -> Path:
    logger.info(f"Processing {url} -> {path}")
    if type(path) == str:
        path = Path(path)
    path_err = path.with_suffix(".err")
    if not path.exists():
        image = get_url(url)
        if image:
            image_file_pillow = Image.open(BytesIO(image.content))
            image_file_pillow.save(path)
            logger.info(f"Found image {path}")
            return path
        else:
            # Since we are going to change the url and try again, use url here
            error_image = url.split("/")[-1]
            # Check if this is a form
            if "-" in error_image:
                logger.warning(f"Did not find {error_image}, trying base form")
                # Grab base image name without -{form}.png, then add .png
                base_image = f"{error_image.split('-')[0]}.png"
                base_form_url = url.replace(error_image, base_image)
                # Try again with {national dex number}.png
                # There is no loop because we strip the form and this block gets skipped without an - in the name
                return download_image(base_form_url, path)
            else:
                path_err.touch(exist_ok=True)
                logger.error(f"Unable to find {url}, created error file {path_err}")
                return path_err
    else:
        logger.info(f"File {path} exists already")
        return path


def load_dex(dex_file: str | Path) -> List[PkmnEntry]:
    if Path(dex_file).exists():
        with open(dex_file, "r", encoding="windows-1252") as dex_json:
            list_of_json = json.load(dex_json)
            for pkmn in list_of_json:
                pkmn["unique_model_images"] = [
                    FormTuple(x[0], x[1]) for x in pkmn["unique_model_images"]
                ]
            return [PkmnEntry(**x) for x in list_of_json]
    else:
        return []


def save_dex(dex_file: str | Path, dex: List[PkmnEntry]) -> None:
    with open(dex_file, "w", encoding="windows-1252") as dex_json:
        logger.debug("Saving json")
        json.dump([x.asdict() for x in dex if x is not None], dex_json, indent=2)


def get_url(url: str) -> httpx.Response:
    cache = shelve.open(".cache")
    if url in cache.keys():
        logger.debug("Found in cache")
        returnable = cache[url]
        cache.close()
        return returnable
    with httpx.Client(
        event_hooks={"request": [_log_request], "response": [_log_response]}
    ) as client:
        response = client.get(url)
        if response.status_code == 200:
            cache[url] = response
            logger.debug(f"Add {url} to cache")
            cache.close()
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
        "name": "Pikachu",
        "pdex": 74,
        "ndex": 25,
        "male": 50,
        "female": 50,
        "japanese": "Pikachuピカチュウ",
        "french": "Pikachu",
        "german": "Pikachu",
        "korean": "피카츄",
        "gender_models": ["Male", "Female"],
        "form_models": [],
        "unique_model_images": [
            FormTuple("Male", "025.png"),
            FormTuple("Female", "025-f.png"),
        ],
        "complete": False,
    },
    {
        "name": "Tauros",
        "pdex": 223,
        "ndex": 128,
        "male": 100,
        "female": 0,
        "japanese": "Kentaurosケンタロス",
        "french": "Tauros",
        "german": "Tauros",
        "korean": "켄타로스",
        "gender_models": ["Uniform"],
        "form_models": [
            "Paldean Form Combat Breed",
            "Paldean Form Blaze Breed",
            "Paldean Form Aqua Breed",
        ],
        "unique_model_images": [
            FormTuple("Uniform|Paldean Form Combat Breed", "128-p.png"),
            FormTuple("Uniform|Paldean Form Blaze Breed", "128-b.png"),
            FormTuple("Uniform|Paldean Form Aqua Breed", "128-a.png"),
        ],
        "complete": False,
    },
]


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
        dex = load_dex(data_file)
        if pkmn is None:
            logger.info("Pokemon is filtered out.")
        elif pkmn.ndex not in [x.ndex for x in dex]:
            logger.info(f"Found new pokemon {pkmn.name} #{pkmn.pdex}")
            dex.append(pkmn)
            save_dex(data_file, dex)
        else:
            logger.info(f"Pokemon already exists in dex {pkmn.name} #{pkmn.pdex}")
    # Correct missing data
    dex = load_dex(data_file)
    changed = False
    for manual_added in TO_ADD:
        pkmn = PkmnEntry(**manual_added)
        if pkmn.ndex not in [x.ndex for x in dex]:
            changed = True
            logger.info(f"Loading Manual pokemon {pkmn.name} # {pkmn.pdex}")
            dex.append(pkmn)
    if changed:
        save_dex(data_file, dex)


def generate_images(data_file: str | Path, img_file: str | Path):
    pkmn_dex = load_dex(data_file)
    logger.debug(f"Starting image checking and downloading.")
    for entry in pkmn_dex:
        for form in entry.unique_model_images:
            image_file_url = f"https://serebii.net/scarletviolet/pokemon/new/{form.img_name}"
            shiny_file_url = f"https://www.serebii.net/Shiny/SV/new/{form.img_name}"
            sprite_file_url = f"https://serebii.net/pokedex-sv/icon/new/{form.img_name}"

            image_file_path = f"{img_file}\\sprite\\{form.img_name}"
            shiny_file_path = f"{img_file}\\sprite\\{form.img_name}"
            sprite_file_path = f"{img_file}\\sprite\\{form.img_name}"

            download_image(image_file_url, image_file_path)
            download_image(shiny_file_url, shiny_file_path)
            download_image(sprite_file_url, sprite_file_path)


# generate_data("data\\dex_v3.json")
# test_dex = load_dex("data\\dex_v3.json")
# logger.debug(f"{test_dex[0]}")
#
# generate_images("data\\dex_v3.json", "images")
