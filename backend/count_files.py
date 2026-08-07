import sys
import requests

def count_github_files(repo_url: str):
    # Parse the owner/repo from the URL
    repo_slug = repo_url.strip().rstrip("/")
    if "github.com" in repo_slug:
        repo_slug = repo_slug.split("github.com/")[-1]
    repo_slug = repo_slug.replace(".git", "")
    
    # 1. Fetch repo metadata to find the default branch
    api_base = f"https://api.github.com/repos/{repo_slug}"
    print(f"Fetching repo info for: {repo_slug}...")
    
    repo_info = requests.get(api_base).json()
    if "default_branch" not in repo_info:
        print(f"Error: Could not fetch repo info. {repo_info.get('message', 'Unknown error.')}")
        return
        
    branch = repo_info["default_branch"]
    
    # 2. Fetch the full recursive tree for the default branch
    print(f"Fetching file tree for branch '{branch}'...")
    tree_url = f"{api_base}/git/trees/{branch}?recursive=1"
    tree_data = requests.get(tree_url).json()
    
    if "tree" not in tree_data:
        print(f"Error: Could not fetch tree. {tree_data.get('message', 'Unknown error.')}")
        if tree_data.get("truncated"):
            print("Warning: The repository tree is too large to fetch in a single request.")
        return
        
    # 3. Count only blobs (files), ignoring trees (directories)
    files = [item for item in tree_data["tree"] if item["type"] == "blob"]
    
    print("-" * 40)
    print(f"Total number of files in {repo_slug}: {len(files)}")
    print("-" * 40)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python count_files.py <github_repo_url>")
        sys.exit(1)
    
    count_github_files(sys.argv[1])
