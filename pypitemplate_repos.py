"""This script lists repos created with from ssb-pypitemplate with cruft."""

import argparse
import json
import logging
import sys
from pathlib import Path

from github import Github, GithubException, UnknownObjectException


repo_list_filename = "ssb-pypitemplate-repos.json"

logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler("ssb-pypitemplate-repos.log", mode="w", encoding="utf-8"),
        logging.StreamHandler(),
    ],
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main(token):
    logging.info("Script started")
    g = Github(token)
    org = g.get_organization("statisticsnorway")

    pypi_repos = []
    if not Path(repo_list_filename).is_file():
        logging.info("Scanning for repos created with ssb-pypitemplate ...")
        # repo = org.get_repo("ssb-pypitemplate-instance")
        number = 1
        found = 0
        for repo in org.get_repos():
            try:
                print(f"Checking repo {number}, found: {found}")
                number += 1
                contents = repo.get_contents(".cruft.json")
                if contents and "pypitemplate" in contents.decoded_content.decode(
                    "utf-8"
                ):
                    logging.info(
                        f"{repo.full_name} contains .cruft.json from ssb-pypitemplate"
                    )
                    pypi_repos.append(repo)
                    found += 1
            except UnknownObjectException:
                pass  # If the file is not found, an exception is raised
            except GithubException as e:
                if e.status != 404:
                    raise e

        repo_names = [repo.full_name for repo in pypi_repos]
        Path(repo_list_filename).write_text(json.dumps(repo_names))
    else:
        logging.info(f"Reading repos from {repo_list_filename}...")
        repo_names = json.loads(Path(repo_list_filename).read_text())
        for repo_name in repo_names:
            if "libtest" not in repo_name:
                print(repo_name)
                repo = g.get_repo(repo_name)
                pypi_repos.append(repo)

    logging.info(f"There are {len(pypi_repos)} repos created from ssb-pypitemplate")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    parser.add_argument("token", help="GitHub Personal Access Token")
    args = parser.parse_args()

    main(args.token)
