#!/usr/bin/env python3

import os
import sys
import yaml
import dateutil
import feedparser
import getpass
import argparse
import validators

from mastodon import Mastodon
from datetime import datetime, timezone

ID="tootfeed"

# default config file
DEFAULT_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".tootfeed.cfg")

# handle config
config_file = DEFAULT_CONFIG_FILE

def read_config(config_file):
    config = {}
    with open(config_file) as fh:
        config = yaml.load(fh)
        if 'updated' in config:
            config['updated'] = dateutil.parser.parse(config['updated'])
    return config

def save_config(config, config_file, update = False):
    copy = dict(config)
    if update:
        copy['updated'] = datetime.now(tz=timezone.utc).isoformat()
    with open(config_file, 'w') as fh:
        fh.write(yaml.dump(copy, default_flow_style=False))

# handle feed and entry

def get_feed(feed_url, last_update):
    new_entries = 0
    feed = feedparser.parse(feed_url)
    for entry in feed.entries:
        e = get_entry(entry)
        if last_update is None or e['updated'] > last_update:
            new_entries += 1
            yield e
    return new_entries

def get_entry(entry):
    hashtags = []
    for tag in entry.get('tags', []):
        for t in tag['term'].split(' '):
            hashtags.append('#{}'.format(t))
    return {
        'url': entry.link,
        'title': entry.title,
        'summary': entry.get('summary', ''),
        'hashtags': ' '.join(hashtags),
        'updated': dateutil.parser.parse(entry['published']),
    }

# process feed and update status

def main(config_file):
    config = read_config(config_file)

    masto = Mastodon(
        api_base_url=config['url'],
        client_id=config['client_id'],
        client_secret=config['client_secret'],
        access_token=config['access_token']
    )

    last_update = config.get('updated', None)

    for feed in config['feeds']:
        for entry in get_feed(feed['url'], last_update):
            masto.status_post(feed['template'].format(**entry)[0:499])

    save_config(config, config_file, update = True)

# setup mastodon account

def setup(config_file):
    have_app = input('Do you have your app credentials already? [y/n] ')

    if have_app[0] not in ('y', 'Y'):
        print("Quit: may be another time ..")
        return

    mast_url = input('Enter your Mastodon instance URL? ')
    app_name = input('Enter your app name (e.g. tootfeed): ')
    if app_name == '':
        app_name = 'tootfeed'

    client_id, client_secret = Mastodon.create_app(
        client_name=app_name,
        api_base_url=mast_url,
    )

    username = input('Enter Mastodon username (email): ')
    password = getpass.getpass(prompt='Enter mastodon password (not stored): ')

    proxy = Mastodon(client_id=client_id, client_secret=client_secret, api_base_url=mast_url)
    access_token = proxy.log_in(username, password)

    config = read_config(config_file)
    config.update({
        'name': app_name,
        'url': mast_url,
        'client_id': client_id,
        'client_secret': client_secret,
        'access_token': access_token,
    })
    save_config(config, config_file)

# add RSS/Atom feed
def add_rss(config_file):
    have_rss = input('Do you have the RSS feed url ready? [y/n] ')

    if have_rss[0] not in ('y', 'Y'):
        print("Quit: may be another time ..")
        return
    
    feed_url = input('RSS/Atom feed URL to watch: ')

    if not validators.url(feed_url):
        print("Quit: invalid url given ..")
        return

    config = read_config(config_file)

    feeds = config.get('feeds', [])

    # eliminate duplicates
    for x in feeds:
        if x['url'] == feed_url:
            print("Quit: feed is added already ..")
            return

    feeds.append({'url': feed_url, 'template': '{title} {url}'})
    config['feeds'] = feeds
        
    save_config(config, config_file)

def suggestion(config_file):
    print("Add a line like this to your crontab to check every 15 minutes")
    print("*/15 * * * * tootfeed")
    print("")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="An RSS feed to Mastodon toot bot")

    parser.add_argument('--setup',
                        action='store_true',
                        help='setting up mastodon authentication')
    parser.add_argument('--rss',
                        action='store_true',
                        help='adding rss feed')
    parser.add_argument('--config',
                        action='store',
                        help='specifing config file')
    parser.add_argument('--suggest',
                        action='store_true',
                        help='deployment suggestion')
    args = parser.parse_args()

    if args.config:
        config_file = args.config
    
    if args.setup: setup(config_file)
    elif args.rss: add_rss(config_file)
    elif args.suggest: suggestion(config_file)
    else:          main(config_file)
