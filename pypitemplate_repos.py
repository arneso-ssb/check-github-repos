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


pypitemplate_repos_file = "ssb-pypitemplate-repos.json"
stat_repos_file = "stat-repos.json"

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
    non_archived_repos = [repo for repo in repos if not repo.archived]
    repo_full_names = sorted([repo.full_name for repo in non_archived_repos])
    write_list_to_file(repo_full_names, Path("ssb-all-repos.txt"))
    ssb_prefix_repos = [
        repo for repo in repo_full_names if repo.startswith("statisticsnorway/ssb-")
    ]
    write_list_to_file(ssb_prefix_repos, Path("ssb-prefix-repos.txt"))
    stat_prefix_repos = [
        repo for repo in repo_full_names if repo.startswith("statisticsnorway/stat-")
    ]
    write_list_to_file(stat_prefix_repos, Path("stat-prefix-repos.txt"))
    return non_archived_repos


def filter_template_repos(repos: list[Repository]) -> tuple[list[str], list[str]]:
    logging.info(
        "Scanning for repos created with ssb-pypitemplate or stat-repos with template-stat..."
    )
    pypitemplate_repos = []
    stat_repos = []
    for index, repo in enumerate(repos, start=1):
        try:
            logging.info(
                f"Checking repo {index}; Found pypitemplate: {len(pypitemplate_repos)}, stat: {len(stat_repos)}"
            )
            contents = repo.get_contents(".cruft.json").decoded_content.decode("utf-8")
            if contents:
                if "ssb-pypitemplate" in contents:
                    logging.info(
                        f"{repo.full_name} contains .cruft.json from ssb-pypitemplate"
                    )
                    pypitemplate_repos.append(repo)
                elif "template-stat" in contents and repo.full_name.startswith(
                    "statisticsnorway/stat-"
                ):
                    logging.info(
                        f"{repo.full_name} contains .cruft.json from ssb-project-template-stat"
                    )
                    stat_repos.append(repo)
        except UnknownObjectException:
            pass  # If the file is not found, an exception is raised
        except GithubException as e:
            if e.status != 404:
                raise e

    pypitemplate_repo_names = sorted([repo.full_name for repo in pypitemplate_repos])
    Path(pypitemplate_repos_file).write_text(json.dumps(pypitemplate_repo_names))
    write_list_to_file(pypitemplate_repo_names, Path("ssb-pypitemplate-repos.txt"))

    stat_repo_names = sorted([repo.full_name for repo in stat_repos])
    Path(stat_repos_file).write_text(json.dumps(stat_repo_names))
    write_list_to_file(stat_repo_names, Path("stat-repos.txt"))

    return pypitemplate_repo_names, stat_repo_names


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


def get_repos_statistics(
    token: str, template_repos: list[str], template: str
) -> pd.DataFrame:
    g = Github(token)
    template_commits = get_template_commits(template, token)

    data = []
    for repo_name in template_repos:
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


def save_as_html(df: pd.DataFrame, filename: str, title: str) -> None:
    df["latest_update"] = df["latest_update"].dt.date
    df["template_date"] = df["template_date"].dt.date
    table_html = df.to_html(
        table_id="pypitemplate",
        classes="display",
        index=False,
        border=0,
    )

    current_timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")

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
        <h1>{title}</h1>
        <p>Generated at {current_timestamp}</p>
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

    if Path(pypitemplate_repos_file).is_file() and Path(stat_repos_file).is_file():
        logging.info(f"Reading repos from {pypitemplate_repos_file}...")
        pypitemplate_repos = json.loads(Path(pypitemplate_repos_file).read_text())
        logging.info(f"Reading repos from {stat_repos_file}...")
        stat_repos = json.loads(Path(pypitemplate_repos_file).read_text())
    else:
        repos = get_repos(org)
        pypitemplate_repos, stat_repos = filter_template_repos(repos)

    logging.info(
        f"There are {len(pypitemplate_repos)} repos created from ssb-pypitemplate"
    )
    logging.info(f"There are {len(stat_repos)} repos created from stat-template")

    pypitemplate_repo_stats = get_repos_statistics(
        token, pypitemplate_repos, "statisticsnorway/ssb-pypitemplate"
    )
    save_as_html(
        pypitemplate_repo_stats,
        "ssb-pypitemplate-repos.html",
        "GitHub repos based on ssb-pypitemplate.",
    )
    stat_repo_stats = get_repos_statistics(
        token, stat_repos, "statisticsnorway/ssb-project-template-stat"
    )
    save_as_html(
        stat_repo_stats,
        "stat-repos.html",
        "GitHub repos based on ssb-project-template-stat with stat-prefix.",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    parser.add_argument("token", help="GitHub Personal Access Token")
    args = parser.parse_args()

    main(args.token)
