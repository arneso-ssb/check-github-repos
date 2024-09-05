"""This script lists repos created with from ssb-pypitemplate with cruft."""

import argparse
import json
import logging
import sys
from pathlib import Path

from github import (
    Github,
    GithubException,
    Organization,
    Repository,
    UnknownObjectException,
)


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


def write_list_to_file(elements: list[str], filename: Path):
    with filename.open("w", encoding="utf8") as file:
        for element in elements:
            file.write(f"{element}\n")


def get_repos(org: Organization) -> list[Repository]:
    logging.info("Retrieving list of repos...")
    repos = org.get_repos()
    repo_full_names = sorted([repo.full_name for repo in repos])
    write_list_to_file(repo_full_names, Path("ssb-all-repos.txt"))
    ssb_prefix_repos = [repo for repo in repo_full_names if repo.startswith("ssb-")]
    write_list_to_file(ssb_prefix_repos, Path("ssb-prefix-repos.txt"))
    return repos


def filter_pypitemplate_repos(repos: list[Repository]) -> list[Repository]:
    logging.info("Scanning for repos created with ssb-pypitemplate...")
    found = 0
    pypitemplate_repos = []
    for index, repo in enumerate(repos, start=1):
        try:
            print(f"Checking repo {index}, found: {found}")
            contents = repo.get_contents(".cruft.json")
            if contents and "pypitemplate" in contents.decoded_content.decode("utf-8"):
                logging.info(
                    f"{repo.full_name} contains .cruft.json from ssb-pypitemplate"
                )
                pypitemplate_repos.append(repo)
                found += 1
        except UnknownObjectException:
            pass  # If the file is not found, an exception is raised
        except GithubException as e:
            if e.status != 404:
                raise e

    repo_names = sorted([repo.full_name for repo in pypitemplate_repos])
    Path(repo_list_filename).write_text(json.dumps(repo_names))
    write_list_to_file(repo_names, Path("ssb-pypitemplate-repos.txt"))
    return pypitemplate_repos


def main(token):
    logging.info("Script started")
    g = Github(token)
    org = g.get_organization("statisticsnorway")

    if not Path(repo_list_filename).is_file():
        repos = get_repos(org)
        pypitemplate_repos = filter_pypitemplate_repos(repos)
    else:
        logging.info(f"Reading repos from {repo_list_filename}...")
        pypitemplate_repos = json.loads(Path(repo_list_filename).read_text())

    logging.info(
        f"There are {len(pypitemplate_repos)} repos created from ssb-pypitemplate"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    parser.add_argument("token", help="GitHub Personal Access Token")
    args = parser.parse_args()

    main(args.token)
