import argparse
import shutil
import subprocess
import sys
from github import Github
from git import Repo
from pathlib import Path
import os
import stat


def credentials_url(url, token):
    """Create url including credentials."""
    credentials = token + '@'
    split_index = url.find('//') + 2
    url_with_credentials = url[:split_index] + credentials + url[split_index:]
    return url_with_credentials


def check_file(file):
    argv = ['nbstripout', file]
    try:
        subprocess.run(argv, check=True)
    except subprocess.CalledProcessError:
        print("  ERROR from nbstripout command")


def del_ro(action, name, exc):
    """Delete read_only files in .git directory by making them writeable"""
    os.chmod(name, stat.S_IWRITE)
    os.remove(name)


def check_branch(git_repo, path, branch):
    print(f"Checking branch: {branch}")
    git_repo.git.checkout(branch)

    files_to_check = path.rglob("*.ipynb")
    # print("  Files to check for output:")
    for file in files_to_check:
        # print(f"    {file}")
        check_file(file)

    changed_files = [item.a_path for item in git_repo.index.diff(None)]
    if changed_files:
        print("  Files that contains output:")
        for file in changed_files:
            print(f"    {file}")

    # Cleanup
    git_repo.git.reset("--hard")
    print(f"  Branch {branch} is DIRTY") if changed_files else print(f"  Branch {branch} is CLEAN")
    return True if changed_files else False


def check_repo(repo, token):
    clone_url = credentials_url(repo.clone_url, token)
    print("--------------------------------------------")
    print(f"Checking repo: {repo.full_name}")
    # print(f"Checking repo: {repo.full_name}, {repo.name}, {repo.clone_url}")
    path = Path.cwd() / "repos" / repo.name
    if path.exists():
        shutil.rmtree(path, onerror=del_ro)
    git_repo = Repo.clone_from(clone_url, path)
    # git_repo = Repo(path)
    branches = [b.name[7:] for b in git_repo.remote().refs]
    if "HEAD" in branches:
        branches.remove("HEAD")
    print(f"Branches: {branches}")

    failed_repo = False
    for branch in branches:
        if check_branch(git_repo, path, branch):
            failed_repo = True

    print(f"Repo {repo.name} is DIRTY") if failed_repo else print(f"Repo {repo.name} is CLEAN")


def main(token):
    print("Scanning organization for repos containing Jupyter Notebooks...")
    g = Github(token)

    jupyter_repos = []
    for repo in g.get_organization("statisticsnorway").get_repos():
        if "Jupyter Notebook" in repo.get_languages():
            print(f"{repo.full_name}")
            jupyter_repos.append(repo)
    print(f"There are {len(jupyter_repos)} repos with Jupyter Notebooks")

    # repo = g.get_repo("statisticsnorway/testrepo")
    # check_repo(repo, token)
    for repo in jupyter_repos:
        check_repo(repo, token)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    parser.add_argument('token', help="GitHub Personal Access Token")
    args = parser.parse_args()

    main(args.token)
