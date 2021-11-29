# check-github-repos
Listing and checking GitHub repos for an organization.

## Usage
The script takes one parameter: GitHub Personal Access Token (PAT).

It is tested with a token with the following scopes:
```
read-token — notifications, read:discussion, read:enterprise, read:gpg_key,
read:org, read:public_key, read:repo_hook, read:user, repo, user:email
```

Command example:
```
python main.py ghp_L_lots_of_numbers_2jhK 
```

