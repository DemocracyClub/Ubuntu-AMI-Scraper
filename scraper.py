import json5
import lxml.html
import os
import requests
from github import open_pull_request
from polling_bot.brain import SlackClient


# hack to override sqlite database filename
# see: https://help.morph.io/t/using-python-3-with-morph-scraperwiki-fork/148
os.environ['SCRAPERWIKI_DATABASE_NAME'] = 'sqlite:///data.sqlite'
import scraperwiki


SEND_NOTIFICATIONS = True
OPEN_PULL_REQUESTS = True

try:
    SLACK_WEBHOOK_URL = os.environ['MORPH_UBUNTU_BOT_SLACK_WEBHOOK_URL']
except KeyError:
    SLACK_WEBHOOK_URL = None

try:
    GITHUB_API_KEY = os.environ['MORPH_GITHUB_API_KEY']
except KeyError:
    GITHUB_API_KEY = None


REPOS = {
    'DemocracyClub/polling_deploy': {
        'zone': 'eu-west-1',
        'version': '16.04 LTS',
        'instance_type': 'hvm:ebs-ssd',
        'cpu_arch': 'amd64',
    },
    'DemocracyClub/ee_deploy': {
        'zone': 'eu-west-2',
        'version': '18.04 LTS',
        'instance_type': 'hvm:ebs-ssd',
        'cpu_arch': 'amd64',
    },
    'DemocracyClub/who_deploy': {
        'zone': 'eu-west-2',
        'version': '16.04 LTS',
        'instance_type': 'hvm:ebs-ssd',
        'cpu_arch': 'amd64',
    },
}


def post_slack_message(release):
    message = "Found new Ubuntu {version} ({instance_type}) image in {zone}: `{ami_id}`".format(
        version=release['version'],
        instance_type=release['instance_type'],
        zone=release['zone'],
        ami_id=release['ami_id'],
    )
    slack = SlackClient(SLACK_WEBHOOK_URL)
    slack.post_message(message)


def init():
    scraperwiki.sql.execute("""
        CREATE TABLE IF NOT EXISTS data (
            version TEXT,
            date TEXT,
            zone TEXT,
            ami_id TEXT,
            cpu_arch TEXT,
            instance_type TEXT);
    """)
    scraperwiki.sql.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
        data_amiid_unique ON data (ami_id);
    """)


def get_repos_for_image(image):
    repos = []
    for repo, platform in REPOS.items():
        if (
            image['zone'] == platform['zone']
            and image['version'] == platform['version']
            and image['instance_type'] == platform['instance_type']
            and image['cpu_arch'] == platform['cpu_arch']
        ):
            repos.append(repo)
    return repos


def scrape():
    res = requests.get('https://cloud-images.ubuntu.com/locator/ec2/releasesTable')
    if res.status_code != 200:
        res.raise_for_status()
    js = res.text
    data = json5.loads(js)

    for row in data['aaData']:
        link = lxml.html.fromstring(row[6])
        record = {
            'zone': row[0],
            'version': row[2],
            'instance_type': row[4],
            'date': row[5],
            'cpu_arch': row[3],
            'ami_id': link.text,
        }
        repos = get_repos_for_image(record)

        if repos:
            exists = scraperwiki.sql.select(
                "* FROM 'data' WHERE ami_id=?", record['ami_id'])
            if len(exists) == 0:
                print(record)
                if SLACK_WEBHOOK_URL and SEND_NOTIFICATIONS:
                    post_slack_message(record)
                if GITHUB_API_KEY and OPEN_PULL_REQUESTS:
                    for repo in repos:
                        open_pull_request(repo, record)

            scraperwiki.sqlite.save(
                unique_keys=['ami_id'], data=record, table_name='data')
            scraperwiki.sqlite.commit_transactions()


init()
scrape()
