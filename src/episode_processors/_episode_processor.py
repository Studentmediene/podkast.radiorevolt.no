from abc import ABCMeta, abstractmethod

from utils.date2dt import date2dt

__all__ = ["EpisodeProcessor"]


class EpisodeProcessor(metaclass=ABCMeta):
    """Class which provides metadata for a subset of all episodes."""

    start_date_key = "start_date"
    end_date_key = "end_date"

    def __init__(self, settings, bypass, requests_session, get_global, bypass_shows):
        """Initialize new episode metadata source.

        The default implementation sets self.settings to the value of settings, and self.bypass to the value of bypass.

        Args:
            settings (dict): Settings for this metadata source, taken from generator/settings.py.
            bypass (set): Set of episode URLs which this metadata source should bypass (ie. not accept)
            requests_session: Requests session which will be used when making requests to other servers.
            get_global: Function for obtaining the global instances of classes
                like EpisodeSource, ShowSource, Redirector etc. Should
                normally not be necessary, but some special processors might
                need them.
        """
        self.settings = settings
        """dict: Dictionary with the settings for this episode metadata source (fetched from generator/settings.py)."""
        self.bypass = bypass
        """set: Set of episode.sound_url addresses which this source must bypass (ie. not accept)."""
        self.requests = requests_session
        """Requests session which shall be used when making requests to other servers."""
        self.get_global = get_global
        """Function for obtaining instances of ShowSource, EpisodeSource etc.
        For special purpose processors only."""
        self.bypass_shows = bypass_shows
        """set: Set of episode.show.id which this source must bypass (ie. not accept)."""

    @abstractmethod
    def accepts(self, episode) -> bool:
        """Check if this metadata source has metadata for the given episode.

        The default implementation checks whether the episode should be bypassed, and will also use START_DATE and
        END_DATE if they are present in self.settings.

        Args:
            episode (Episode): Episode which will be evaluated.

        Returns:
            bool: True if this metadata source has metadata for the provided episode, False otherwise.
        """

        if episode.media.url in self.bypass:
            # Bypass, even if start and end dates are set
            return False
        elif episode.show.id in self.bypass_shows:
            # Bypass, due to the show
            return False
        elif self.start_date_key in self.settings \
                or self.end_date_key in self.settings:
            # Settings contains START_DATE and END_DATE, put them to use
            start = date2dt(self.settings.get(self.start_date_key))
            end = date2dt(self.settings.get(self.end_date_key))

            if start and end:
                # Both are present, date must be between them
                return start <= episode.publication_date <= end
            elif start:
                # Only start is present, date must be after start
                return start <= episode.publication_date
            elif end:
                # Only end is present, date must be before end
                return episode.publication_date <= end
            else:
                # None of them are present (wtf?), accept all
                return True
        else:
            # No dates are limiting the scope, so accept this
            return True

    @abstractmethod
    def populate(self, episode) -> None:
        """Populate the provided episode with metadata.

        This method will set the different properties to values fetched from this metadata source.

        The default implementation does nothing.

        Args:
            episode (Episode): Episode which will have its properties populated with new metadata.

        Returns:
            None

        Raises:
            SkipEpisode: When this episode shouldn't be included in the feed.
        """
        pass

    def prepare_batch(self) -> None:
        """Called to signal that information about all available episodes should be downloaded.

        This method should download information about all episodes, so that subsequent calls to
        accept and populate don't cause a network roundtrip. This is done to save time when
        batch generating feeds.

        The default implementation does nothing.
        """
        pass
