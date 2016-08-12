from time import strptime
import logging

from .. import ShowMetadataSource
from ..base_manual_changes import BaseManualChanges
from ...settings import METADATA_SOURCE
from cached_property import threaded_cached_property as cached_property
import json
import os.path
import sys
from podgen import Person, Category


logger = logging.getLogger(__name__)


class ManualChanges(BaseManualChanges, ShowMetadataSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @cached_property
    def _is_episode_source(self):
        return False

    @cached_property
    def _config_file_settings_key(self):
        return "SHOW_CONFIG"

    @staticmethod
    def _get_key(show):
        return str(show.id)

    def accepts(self, show) -> bool:
        return super().accepts(show)

    def populate(self, show) -> None:
        metadata = self.data[self._get_key(show)]

        for attribute, value in metadata.items():
            if hasattr(show, attribute):
                if attribute in ("publication_date", "last_updated"):
                    try:
                        setattr(show, attribute, strptime(value, "%Y-%m-%d %H:%M:%S %z"))
                    except ValueError:
                        logger.warning("Date %(date)s in file %(file)s could not be parsed, so it was ignored.\n"
                              "Make sure it's on the following form (±HHMM being timezone offset):\n"
                              "    YYYY-MM-DD HH:MM:SS ±HHMM", {"date": metadata['date'], "file": self._config_file})
                elif attribute == "authors":
                    authors = [Person(p.get('name'), p.get('email')) for p in value]
                    show.authors = authors
                elif attribute == "web_master":
                    show.web_master = Person(value.get('name'), value.get('email'))
                elif attribute == "category":
                    if len(value) == 2:
                        show.category = Category(value[0], value[1])
                    else:
                        show.category = Category(value[0])
                else:
                    setattr(show, attribute, value)
            else:
                logger.warning("Attribute %(keys)s for %(id)s was not recognized."
                      , {"id": show.id, "keys": attribute})
