import base64
import os
import re
import warnings
from typing import Dict, Union

import jinja2
import pandas as pd
import requests
from tqdm import tqdm

from config import GITHUB_API_URL, GITHUB_ORG, HOMEDIR, PYPISTATS_API_URL
from utils import ensure_dir, get_current_time_str, join_url, try_get_json


def get_basic_info(repo) -> Dict[str, Union[str, float]]:
    return {
        "Name": f"[{repo['name']}]({repo['html_url']})",
        "Stars": repo["stargazers_count"],
        "Forks": repo["forks_count"],
    }


def get_packge_info(repo_contents, session=None) -> Dict[str, Union[str, int]]:
    for content in repo_contents:
        if content["name"] not in ("setup.cfg", "pyproject.toml"):
            continue

        file_b64 = try_get_json(content["git_url"], session=session)["content"]
        file_text = base64.b64decode(file_b64).decode()

        # Try to extract package name
        if (pkg_name := re.compile(r"\nname = ([\w\"\']*)\n").findall(file_text)):
            if len(pkg_name) > 1:
                warnings.warn(
                    f"Found multiple pkg name: {pkg_name}\nUsing the first one: {pkg_name[0]}",
                    RuntimeWarning,
                    stacklevel=2,
                )
            pkg_name = pkg_name[0].replace('"', "").replace("'", "")
        else:
            continue

        # Get PyPI stats given the package name
        pypi_stats = try_get_json(join_url(PYPISTATS_API_URL, "packages", pkg_name, "recent"))["data"]

        return {
            "Package name": pkg_name,
            "Weekly downloads": int(pypi_stats["last_week"]),
            "Monthly downloads": int(pypi_stats["last_month"]),
        }

    return {}


def get_zenodo_info(repo_contents, session=None) -> Dict[str, str]:
    for content in repo_contents:
        if content["name"] != "README.md":
            continue

        file_b64 = try_get_json(content["git_url"], session=session)["content"]
        file_text = base64.b64decode(file_b64).decode()

        pattern = re.compile(r"\[!\[DOI\]\(https://zenodo.org/badge/DOI/[\w.//]*\)\]\([\w.://]*\)")
        if (zenodo_badges := pattern.findall(file_text)):
            return {"Zenodo": "".join(zenodo_badges)}

    return {}


def get_software_info_summary() -> pd.DataFrame:
    with requests.Session() as s:
        if (gh_token := os.environ.get("GH_TOKEN")):
            s.headers.update({"Authorization": f"Bearer {gh_token}"})
        repos = try_get_json(join_url(GITHUB_API_URL, "orgs", GITHUB_ORG, "repos"), s)

        stats_list = []
        for repo in tqdm(repos):
            repo_contents = try_get_json(join_url(repo["url"], "contents"), s)

            repo_stats = get_basic_info(repo)
            repo_stats.update(get_packge_info(repo_contents, session=s))
            repo_stats.update(get_zenodo_info(repo_contents, session=s))

            stats_list.append(repo_stats)

    return (
        pd
        .DataFrame(stats_list)
        .fillna("-")
        .sort_values("Stars", ascending=False)
        .reset_index(drop=True)
    )


def main():
    path = HOMEDIR / "software_info"
    time_str = get_current_time_str(date_only=True)

    # Get software info summary table and save a copy of the result
    df = get_software_info_summary()
    df.to_csv(ensure_dir(path / "hist") / f"{time_str}.csv")

    # Update software info table in the readme by rendering the template
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath=path))
    template = env.get_template("readme_template.md.jinja")
    content = template.render(
        software_info_summary_table=df.to_markdown(index=False),
        last_updated=time_str,
    )

    # Save rendered readme
    with open(path / "README.md", "w") as f:
        f.write(content)


if __name__ == "__main__":
    main()
