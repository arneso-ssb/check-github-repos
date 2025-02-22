"""This script lists repos created with from ssb-pypitemplate with cruft."""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import TypedDict

import pandas as pd
from github import Github
from github import GithubException
from github import Organization
from github import Repository
from github import UnknownObjectException


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


def filter_pypitemplate_repos(repos: list[Repository]) -> list[str]:
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


class CommitInfo(TypedDict):
    date: datetime
    tag: str | None


def get_template_commits(repo_name: str, token: str) -> dict[str, CommitInfo]:
    logging.info(f"Get commits from repo {repo_name}")
    repo = Github(token).get_repo(repo_name)

    first_ssb_commit_date = datetime(year=2023, month=6, day=1)
    commits = repo.get_commits(sha=repo.default_branch, since=first_ssb_commit_date)

    tags = {tag.commit.sha: tag.name for tag in repo.get_tags()}

    commits_info: dict[str, CommitInfo] = {}
    for commit in commits:
        commit_hash = commit.sha
        tag = tags.get(commit_hash)

        commits_info[commit_hash] = {"date": commit.commit.author.date, "tag": tag}

    return commits_info


def get_repos_statistics(token: str, pypitemplate_repos: list[str]) -> pd.DataFrame:
    g = Github(token)
    template_commits = get_template_commits("statisticsnorway/ssb-pypitemplate", token)

    data = []
    for repo_name in pypitemplate_repos:
        repo = g.get_repo(repo_name)
        contents = repo.get_contents(".cruft.json").decoded_content.decode("utf-8")
        cruft_dict = json.loads(contents)
        template_hash = cruft_dict["commit"]
        template_date = template_commits[template_hash]["date"]
        template_tag = template_commits[template_hash]["tag"]
        latest_update = repo.pushed_at
        latest_commiter = repo.get_commits()[0].commit.author.name
        data.append(
            {
                "repo_name": repo_name,
                "latest_update": latest_update,
                "latest_commiter": latest_commiter,
                "template_hash": template_hash,
                "template_date": template_date,
                "template_tag": template_tag,
            }
        )
        logging.info(f"{repo_name}: {template_hash} {template_date} ({template_tag})")

    return pd.DataFrame(
        data,
        columns=[
            "repo_name",
            "latest_update",
            "latest_commiter",
            "template_hash",
            "template_date",
            "template_tag",
        ],
    )


def save_as_html(df: pd.DataFrame, filename: str) -> None:
    df["latest_update"] = df["latest_update"].dt.date
    df["template_date"] = df["template_date"].dt.date
    table_html = df.to_html(
        table_id="pypitemplate",
        classes="display",
        index=False,
        border=0,
    )

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>DataTables Example</title>
        <!-- jQuery -->
        <script src="https://code.jquery.com/jquery-3.7.1.js"></script>
        <!-- DataTables CSS -->
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/2.2.2/css/dataTables.dataTables.css">
        <!-- DataTables JS -->
        <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/2.2.2/js/dataTables.js"></script>
        <style>
            /* Additional styling for the table */
            table.dataTable {{
                width: 80%;
            }}
        </style>
    </head>
    <body>
        <h1>GitHub repos based on ssb-pypitemplate</h1>
        {table_html}
        <script>
            $('#pypitemplate').DataTable({{
                pageLength: 100,
                autoWidth: false
            }});
        </script>
    </body>
    </html>
    """
    with open(filename, "w", encoding="utf-8") as file:
        file.write(html_template)


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

    repo_stat = get_repos_statistics(token, pypitemplate_repos)
    save_as_html(repo_stat, "ssb-pypitemplate-repos.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    parser.add_argument("token", help="GitHub Personal Access Token")
    args = parser.parse_args()

    main(args.token)
