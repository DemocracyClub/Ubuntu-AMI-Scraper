import json
import requests
import urllib.parse
from collections import OrderedDict
from commitment import GitHubCredentials
from commitment import GitHubClient as CommitHelper


def get_github_credentials(repo, branch):
    return GitHubCredentials(
        repo=repo,
        branch=branch,
        name=os.environ['MORPH_GITHUB_USERNAME'],
        email=os.environ['MORPH_GITHUB_EMAIL'],
        api_key=os.environ['MORPH_GITHUB_API_KEY']
    )


class PullRequestHelper:

    def __init__(self, credentials):
        if not isinstance(credentials, GitHubCredentials):
            raise TypeError('expected GitHubCredentials object')
        self.credentials = credentials
        self.base_url = 'https://api.github.com/'

    def _get_target_sha(self):
        url = self.base_url + 'repos/%s/git/refs/heads/%s' % (
            urllib.parse.quote(self.credentials.repo),
            urllib.parse.quote(self.credentials.branch)
        )
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        return data['object']['sha']

    def create_branch(self, branchname):
        url = self.base_url + 'repos/%s/git/refs' % (
            urllib.parse.quote(self.credentials.repo)
        )
        payload = json.dumps({
            "ref": "refs/heads/%s" % (branchname),
            "sha": self._get_target_sha()
        })
        r = requests.post(
            url,
            data=payload,
            headers={'Authorization': 'token %s' % (self.credentials.api_key)}
        )
        if r.status_code not in [200, 201]:
            print(r.json())
        r.raise_for_status()
        return r.status_code

    def open_pull_request(self, branchname, title, body):
        url = self.base_url + 'repos/%s/pulls' % (
            urllib.parse.quote(self.credentials.repo)
        )
        payload = json.dumps({
            "title": title,
            "body": body,
            "head": branchname,
            "base": self.credentials.branch,
            "maintainer_can_modify": True,
        })
        r = requests.post(
            url,
            data=payload,
            headers={'Authorization': 'token %s' % (self.credentials.api_key)}
        )
        if r.status_code not in [200, 201]:
            print(r.json())
        r.raise_for_status()
        return r.status_code


def get_json(repo, branch, filename):
    url = 'https://raw.githubusercontent.com/%s/%s/%s' % (
        urllib.parse.quote(repo),
        urllib.parse.quote(branch),
        urllib.parse.quote(filename)
    )
    r = requests.get(url)
    r.raise_for_status()
    return json.loads(r.text, object_pairs_hook=OrderedDict)


def open_pull_request(repo, release):
    newbranch = release['ami_id']
    commit_message = 'Update ubuntu_ami_id to %s' % (release['ami_id'])

    pr = PullRequestHelper(get_github_credentials(repo, 'master'))
    pr.create_branch(newbranch)

    filename = 'packer-vars.json'
    packer_vars = get_json(repo, newbranch, filename)
    packer_vars['ubuntu_ami_id'] = release['ami_id']

    c = CommitHelper(get_github_credentials(repo, newbranch))
    c.push_file(json.dumps(packer_vars, indent=2), filename, commit_message)

    body = "Found new Ubuntu {version} ({instance_type}) image in {zone}: `{ami_id}`".format(
        version=release['version'],
        instance_type=release['instance_type'],
        zone=release['zone'],
        ami_id=release['ami_id'],
    )
    pr.open_pull_request(newbranch, commit_message, body)
