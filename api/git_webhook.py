#!/usr/bin/env python3.11
import requests
import os
import json

USERNAME = "yungryce"
WEBHOOK_URL = "https://blue-field-058d36703.2.azurestaticapps.net"

try:
    with open('./local.settings.json') as f:
        settings = json.load(f)
        GITHUB_TOKEN = settings['Values'].get('GITHUB_TOKEN')
except Exception:
    pass

headers = {"Authorization": f"token {GITHUB_TOKEN}"}

# 1. Get all repositories for your account
repos_url = f"https://api.github.com/user/repos?per_page=100"
repos = requests.get(repos_url, headers=headers).json()

if isinstance(repos, dict) and "message" in repos:
    print(f"GitHub API error: {repos['message']}")
    exit(1)

for repo in repos:
    repo_name = repo["name"]
    owner = repo["owner"]["login"]
    hooks_url = f"https://api.github.com/repos/{owner}/{repo_name}/hooks"

    # 2. Check existing hooks
    existing_hooks = requests.get(hooks_url, headers=headers).json()
    already_exists = any(h["config"].get("url") == WEBHOOK_URL for h in existing_hooks if "config" in h)

    if already_exists:
        print(f"Webhook already exists for {repo_name}")
        continue

    # 3. Create new webhook
    payload = {
        "name": "web",
        "active": True,
        "events": ["push"],
        "config": {
            "url": WEBHOOK_URL,
            "content_type": "json",
            "insecure_ssl": "0"
        }
    }
    r = requests.post(hooks_url, headers=headers, json=payload)

    if r.status_code == 201:
        print(f"✅ Webhook created for {repo_name}")
    else:
        print(f"❌ Failed for {repo_name}: {r.status_code}, {r.text}")
