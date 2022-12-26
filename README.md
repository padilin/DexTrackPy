# DexTrackPy
A simple python project to track dex progress. It currently pulls all gen 9 and will even track gender and alt forms. It may pull extra forms, such as Pikachu with Hats.

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
---
## TODO
### Scraper
- [x] Clean up code
- [x] Convert data internally to dataclass
- [x] Reduce number of data transforms
- [x] Add comments (Ongoing as well)
- [ ] Add support for other types of tracking
  - [ ] Shiny
  - [ ] Pokedex Completion
  - [ ] Simple living dex
- [x] Support images
- [ ] CLI?
- [ ] Documentation
### Gui (Make the gui less ugly)
- [ ] Pre-load window to allow choosing image + data folders
- [ ] Output progress
- [ ] Support multiple types of tracking
- [x] Clean up grid of pkmn in boxes
- [ ] Clean up text display in boxes
- [x] BUG: opening more than 1 image bugs wont let you close

## Development
1. Install dev dependencies, either:
   - `poetry install --with dev`
   - `pip install -r requirements-dev.txt`
2. Install pre-commit hooks with either:
   - `poetry run pre-commit install`
   - `pre-commit install`

Running tools, add `poetry run` in front:
- pre-commit
  - `pre-commit run --all-files`
- black (configured by pyproject.toml)
  - `black {file(s), ex *.py}`
- mypy (configured by pyproject.toml)
  - `mypy`
- isort (configured by pyproject.toml)
  - `isort {file(s), ex pysvgui\serebii.scrape.py}`
