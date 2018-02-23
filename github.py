import os
import json
from collections import OrderedDict
from commitment import GitHubCredentials, GitHubClient


def open_pull_request(repo, release):
    newbranch = release['ami_id']
    commit_message = 'Update ubuntu_ami_id to %s' % (release['ami_id'])

    creds = GitHubCredentials(
        repo=repo,
        name=os.environ['MORPH_GITHUB_USERNAME'],
        email=os.environ['MORPH_GITHUB_EMAIL'],
        api_key=os.environ['MORPH_GITHUB_API_KEY']
    )
    g = GitHubClient(creds)
    g.create_branch(newbranch)

    filename = 'packer-vars.json'
    packer_vars = json.loads(
        g.get_file_str(filename, branch=newbranch),
        object_pairs_hook=OrderedDict
    )
    packer_vars['ubuntu_ami_id'] = release['ami_id']

    g.push_file(
        json.dumps(packer_vars, indent=2),
        filename,
        commit_message,
        branch=newbranch
    )

    body = "Found new Ubuntu {version} ({instance_type}) image in {zone}: `{ami_id}` :penguin:".format(
        version=release['version'],
        instance_type=release['instance_type'],
        zone=release['zone'],
        ami_id=release['ami_id'],
    )
    g.open_pull_request(newbranch, commit_message, body)
