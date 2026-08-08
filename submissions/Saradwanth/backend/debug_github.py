from config import settings
from github_client import get_rate_limit_status, fetch_repo_files

print(f"Token from settings: {settings.GITHUB_TOKEN[:15]}...")

try:
    print(get_rate_limit_status())
    print("Rate limit check passed!")
except Exception as e:
    print(f"Rate limit failed: {e}")

try:
    res, count = fetch_repo_files("https://github.com/eliasku/unit")
    print(f"Fetch files passed! Got {count} files.")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Fetch files failed: {e}")
