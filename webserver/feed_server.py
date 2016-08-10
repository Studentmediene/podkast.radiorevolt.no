import base64

import hashlib

from generator.generate_feed import PodcastFeedGenerator
from generator.no_such_show_error import NoSuchShowError
from generator import metadata_sources
from . import settings, logo, url_service
from .alternate_show_names import ALTERNATE_ALL_EPISODES_FEED_NAME
from flask import Flask, abort, make_response, redirect, url_for, request,\
    Response, jsonify
import sqlite3
from werkzeug.contrib.fixers import ProxyFix
import urllib.parse
import os.path

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)
app.debug = settings.DEBUG


def url_for_feed(canonical_slug):
    return url_for("output_feed", show_name=canonical_slug, _external=True)


def xslt_url():
    return url_for('static', filename="style.xsl")


@app.before_request
def ignore_get():
    if request.base_url != request.url:
        return redirect(request.base_url, 301)


@app.route('/all')
def output_all_feed():
    gen = PodcastFeedGenerator(quiet=True, xslt=xslt_url(), pretty_xml=True)
    gen.register_redirect_services(get_redirect_sound, get_redirect_article)

    feed = gen.generate_feed_with_all_episodes()
    return _prepare_feed_response(feed, 10 * 60)


@app.route('/<show_name>')
def output_feed(show_name):
    # Replace image so it fits iTunes' specifications
    metadata_sources.SHOW_METADATA_SOURCES.append(logo.ReplaceImageURL)
    # Make it pretty, so curious people can learn from it
    gen = PodcastFeedGenerator(quiet=True, xslt=xslt_url(), pretty_xml=True)
    try:
        show, canonical_slug = \
            url_service.get_canonical_slug_for_slug(show_name, gen)
    except NoSuchShowError:
        # Are we perhaps supposed to redirect to /all?
        if show_name.lower() in (name.lower() for name in ALTERNATE_ALL_EPISODES_FEED_NAME):
            return redirect(url_for("output_all_feed"))
        else:
            abort(404)
            return  # trick IDE; abort(404) will halt execution either way
    show = gen.show_source.shows[show]

    if not show_name == canonical_slug:
        return redirect(url_for_feed(canonical_slug))

    PodcastFeedGenerator.register_redirect_services(get_redirect_sound, get_redirect_article)

    feed = gen.generate_feed(show.id)
    return _prepare_feed_response(feed, 60 * 60)


def _prepare_feed_response(feed, max_age) -> Response:
    resp = make_response(feed)
    resp.headers['Content-Type'] = 'application/xml'
    resp.cache_control.max_age = max_age
    resp.cache_control.public = True
    return resp


@app.route('/api/url/<show>')
def api_url_show(show):
    try:
        return url_for_feed(url_service.create_slug_for(int(show), PodcastFeedGenerator(quiet=True)))
    except (NoSuchShowError, ValueError):
        abort(404)


@app.route('/api/url/')
def api_url_help():
    return "<pre>Format:\n/api/url/&lt;DigAS ID&gt;</pre>"


@app.route('/api/slug/')
def api_slug_help():
    return "<pre>Format:\n/api/slug/&lt;show name&gt;</pre>"


@app.route('/api/slug/<show_name>')
def api_slug_name(show_name):
    return url_for('output_feed', show_name=url_service.sluggify(show_name),
                   _external=True)


@app.route('/api/id/')
def api_id():
    json_dict = {"episode": dict(), "article": dict()}
    with sqlite3.connect(settings.REDIRECT_DB_FILE) as c:
        r = c.execute("SELECT proxy, original FROM sound")

        for row in r:
            json_dict['episode'][row[0]] = row[1]

        r = c.execute("SELECT proxy, original FROM article")

        for row in r:
            json_dict['article'][row[0]] = row[1]

    return jsonify(**json_dict)


@app.route('/api/')
def api_help():
    alternatives = [
        ("URL from Digas ID:", "/api/url/"),
        ("Predict URL from show name:", "/api/slug/"),
        ("Get JSON list which maps episode or article identifier to URL:",
         "/api/id/")
    ]
    return "<pre>API for podcast-feed-gen\nFormat:\n" + \
           ("\n".join(["{0:<20}{1}".format(i[0], i[1]) for i in alternatives])) \
           + "</pre>"


@app.route('/episode/<show>/<episode>/<title>')
def redirect_episode(show, episode, title):
    try:
        return redirect(get_original_sound(episode))
    except ValueError:
        abort(404)


@app.route('/artikkel/<show>/<article>')
def redirect_article(show, article):
    try:
        return redirect(get_original_article(article))
    except ValueError:
        abort(404)


@app.route('/')
def redirect_homepage():
    return redirect(settings.OFFICIAL_WEBSITE)


def get_original_sound(episode):
    with sqlite3.connect(settings.REDIRECT_DB_FILE) as c:
        r = c.execute("SELECT original FROM sound WHERE proxy=?", (episode,))
        row = r.fetchone()
        if not row:
            abort(404)
        else:
            return row[0]


def get_original_article(article):
    with sqlite3.connect(settings.REDIRECT_DB_FILE) as c:
        r = c.execute("SELECT original FROM article WHERE proxy=?", (article,))
        row = r.fetchone()
        if not row:
            abort(404)
        else:
            return row[0]


def get_redirect_sound(original_url, episode):
    show = episode.show
    with sqlite3.connect(settings.REDIRECT_DB_FILE) as c:
        try:
            r = c.execute("SELECT proxy FROM sound WHERE original=?", (original_url,))
            row = r.fetchone()
            if not row:
                raise KeyError(episode.media.url)
            return redirect_url_for(episode, row[0])
        except KeyError:
            new_uri = get_url_hash(original_url)
            e = c.execute("INSERT INTO sound (original, proxy) VALUES (?, ?)", (original_url, new_uri))
            return redirect_url_for(episode, new_uri)


def redirect_url_for(episode, identifier):
    filename = os.path.basename(urllib.parse.urlparse(episode.media.url).path)
    return url_for("redirect_episode", show=url_service.sluggify(episode.show.name), episode=identifier,
                   title=filename, _external=True)


def get_redirect_article(original_url, episode):
    show = episode.show
    try:
        with sqlite3.connect(settings.REDIRECT_DB_FILE) as c:
            try:
                r = c.execute("SELECT proxy FROM article WHERE original=?", (original_url,))
                row = r.fetchone()
                if not row:
                    raise KeyError(episode.link)
                return url_for("redirect_article", show=url_service.sluggify(show.name), article=row[0], _external=True)
            except KeyError:
                new_uri = get_url_hash(original_url)
                e = c.execute("INSERT INTO article (original, proxy) VALUES (?, ?)", (original_url, new_uri))
                return url_for("redirect_article", show=url_service.sluggify(show.name), article=new_uri, _external=True)
    except sqlite3.IntegrityError:
        # Either the entry was added by someone else between the SELECT and the INSERT, or the uuid was duplicate.
        # Trying again should resolve both issues.
        return get_redirect_article(original_url, episode)


def get_url_hash(original_url):
    m = hashlib.md5(original_url.encode("UTF-8")).digest()
    return base64.urlsafe_b64encode(m).decode("UTF-8")[:-2]


@app.before_first_request
def init_db():
    with sqlite3.connect(settings.REDIRECT_DB_FILE) as c:
        c.execute("CREATE TABLE IF NOT EXISTS sound (original text primary key, proxy text unique)")
        c.execute("CREATE TABLE IF NOT EXISTS article (original text primary key, proxy text unique)")
