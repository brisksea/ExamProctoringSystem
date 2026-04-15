import os
import sys
import zipfile
import urllib.request
import json
import shutil
import stat

def get_platform(platform_override=None):
    if platform_override:
        return platform_override
    
    if sys.platform == "linux":
        return "linux64"
    elif sys.platform == "darwin":
        import platform
        if platform.machine() == "arm64":
            return "mac-arm64"
        return "mac-x64"
    elif sys.platform == "win32":
        return "win64"
    return "linux64"

def get_full_version(major_version):
    """
    Look up the latest full version for a given major version from the CfT API.
    """
    url = "https://googlechromelabs.github.io/chrome-for-testing/latest-versions-per-milestone.json"
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            milestones = data.get("milestones", {})
            if str(major_version) in milestones:
                return milestones[str(major_version)]["version"]
            else:
                print(f"Warning: Milestone {major_version} not found in CfT API.")
                return None
    except Exception as e:
        print(f"Error fetching version data: {e}")
        return None

def download_chromedriver(version_input, target_dir="chromedrivers", platform_override=None):
    platform = get_platform(platform_override)
    
    # Check if version_input is just a major version (no dots)
    if "." not in version_input:
        print(f"Looking up latest version for milestone {version_input}...")
        full_version = get_full_version(version_input)
        if not full_version:
            print(f"Could not find full version for {version_input}. Please specify the full version.")
            return False
        version = full_version
        major_version_str = version_input
        print(f"Found full version: {version}")
    else:
        version = version_input
        major_version_str = version.split(".")[0]

    major_version = int(major_version_str)
    
    # Ensure target directory exists
    os.makedirs(target_dir, exist_ok=True)
    # Temporary directory for extraction
    temp_extract_dir = os.path.join(target_dir, f"temp_{version}")
    os.makedirs(temp_extract_dir, exist_ok=True)

    if major_version >= 115:
        # Chrome for Testing (CfT) URL
        download_url = f"https://storage.googleapis.com/chrome-for-testing-public/{version}/{platform}/chromedriver-{platform}.zip"
    else:
        # Older versions
        download_url = f"https://chromedriver.storage.googleapis.com/{version}/chromedriver_{platform}.zip"

    zip_path = os.path.join(temp_extract_dir, "chromedriver.zip")
    
    print(f"Downloading ChromeDriver {version} for {platform}...")
    print(f"URL: {download_url}")
    
    try:
        urllib.request.urlretrieve(download_url, zip_path)
    except Exception as e:
        print(f"Error downloading: {e}")
        # Cleanup
        shutil.rmtree(temp_extract_dir)
        return False

    print("Extracting...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_dir)
        
        # Check for windows binary name if target platform is windows
        original_binary_name = "chromedriver"
        final_binary_name = f"chromedriver_{major_version_str}"
        if "win" in platform:
            original_binary_name += ".exe"
            final_binary_name += ".exe"
            
        found_binary = None
        for root, dirs, files in os.walk(temp_extract_dir):
            if original_binary_name in files:
                found_binary = os.path.join(root, original_binary_name)
                break
        
        if found_binary:
            target_path = os.path.join(target_dir, final_binary_name)
            
            # Move and rename to the target_dir
            if os.path.exists(target_path):
                os.remove(target_path)
            shutil.move(found_binary, target_path)
            
            # Make it executable (only relevant for non-Windows platforms)
            if "win" not in platform:
                st = os.stat(target_path)
                os.chmod(target_path, st.st_mode | stat.S_IEXEC)
            print(f"Successfully installed to: {target_path}")
        else:
            print(f"Could not find {original_binary_name} binary in the zip.")
            return False
            
    except Exception as e:
        print(f"Error extracting or moving: {e}")
        return False
    finally:
        if os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir)
            
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Download ChromeDriver")
    parser.add_argument("version", help="ChromeDriver version or major version milestone")
    parser.add_argument("--platform", choices=["linux64", "mac-arm64", "mac-x64", "win32", "win64"], 
                        help="Platform override (default: auto-detect)")
    
    args = parser.parse_args()
    
    if download_chromedriver(args.version, platform_override=args.platform):
        print("Done.")
    else:
        print("Failed.")
        sys.exit(1)
