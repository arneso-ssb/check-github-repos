import argparse
import sys
from github import Github


def main(token):
    print("Scanning organization for repos containing Jupyter Notebooks...")
    g = Github(token)

    for repo in g.get_organization("statisticsnorway").get_repos():
        if "Jupyter Notebook" in repo.get_languages():
            print(f"{repo.full_name}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    parser.add_argument('token', help="GitHub Personal Access token")
    args = parser.parse_args()

    print(args.token)
    main(args.token)
