import re
import json
from sys import exit
from pathlib import Path
from src import repository, gh

def convert_title(text):
    if not text or not isinstance(text, str):
        return text
    if text.lower() == 'instagram':
        return 'MorpheIG'
    return text.title()

def extract_version(file_path):
    if not file_path:
        return 'unknown'
    path = Path(file_path)
    base_name = path.stem
    
    if '_' in base_name:
        parts = base_name.split('_')
        if len(parts) > 1:
            ver_part = parts[1].split('-v')[0] if '-v' in parts[1] else parts[1]
            if ver_part.lower().startswith('v') and not ver_part[1:].isalpha():
                ver_part = ver_part[1:]
            return ver_part

    match = re.search(r'(\d+\.\d+\.\d+|\d{3,})', base_name)
    return match.group(1) if match else 'unknown'

def create_github_release(name, patches_name, cli_name, apk_file_path, failed_patches=None):
    if failed_patches is None:
        failed_patches = []

    patches_dir = Path(".")
    mpp_files = list(patches_dir.glob("*.mpp"))
    rvp_files = list(patches_dir.glob("*.rvp"))
    jar_files = list(patches_dir.glob("*.jar"))
    
    is_morphe = False
    
    if mpp_files:
        patchver = re.search(r'(\d+\.\d+\.\d+(-[a-z]+\.\d+)?(-release\d*)?)', mpp_files[0].stem)
        patchver = patchver.group(1) if patchver else 'unknown'
        is_morphe = True
    elif rvp_files:
        patchver = re.search(r'(\d+\.\d+\.\d+(-[a-z]+\.\d+)?(-release\d*)?)', rvp_files[0].stem)
        patchver = patchver.group(1) if patchver else 'unknown'
    else:
        patchver = re.search(r'(\d+\.\d+\.\d+(-[a-z]+\.\d+)?(-release\d*)?)', Path(patches_name).stem)
        patchver = patchver.group(1) if patchver else 'unknown'
        if patches_name.lower().endswith('.mpp') or 'morphe' in patches_name.lower():
            is_morphe = True
            
    cli_match = None
    if Path(cli_name).exists() and Path(cli_name).is_file():
        cli_match = re.search(r'(\d+\.\d+\.\d+(-[a-z]+\.\d+)?(-release\d*)?)', Path(cli_name).stem)
    
    if not cli_match and jar_files:
        cli_target = next((f for f in jar_files if "cli" in f.name.lower()), jar_files[0])
        cli_match = re.search(r'(\d+\.\d+\.\d+(-[a-z]+\.\d+)?(-release\d*)?)', cli_target.stem)
        
    cliver = cli_match.group(1) if cli_match else 'unknown'
    cli_filename = Path(cli_name).name.lower()
    
    if name.lower() == 'instagram':
        patch_branding = "piko"
        cli_branding = "Morphe"
        include_microg_note = False
    elif 'morphe' in cli_filename or is_morphe or cliver != 'unknown':
        patch_branding = "Morphe"
        cli_branding = "Morphe"
        include_microg_note = True
        microg_name = "Morphe MicroG-RE"
        microg_link = "https://github.com/MorpheApp/MicroG-RE"
    else:
        patch_branding = "ReVanced"
        cli_branding = "ReVanced"
        include_microg_note = True
        microg_name = "ReVanced GmsCore"
        microg_link = "https://github.com/revanced/gmscore/releases/latest"
    
    app_version = extract_version(str(apk_file_path))
    tag_name = f"mph-ig-{app_version}-{patchver}"

    apk_path = Path(apk_file_path)
    if not apk_path.exists():
        exit(1)

    repo = gh.get_repo(repository)

    try:
        existing_release = repo.get_release(tag_name)
    except:
        existing_release = None

    if existing_release:
        for asset in existing_release.get_assets():
            if asset.name == apk_path.name:
                asset.delete_asset()

    releases = list(repo.get_releases())
    suffix_match = re.search(r'(-[a-z]+\.\d+)$', patchver)
    current_suffix = suffix_match.group(1) if suffix_match else ''

    for r in releases:
        release_tag = r.tag_name
        if release_tag.startswith("mph-ig-") and release_tag != tag_name:
            try:
                old_version = release_tag.split("mph-ig-")[-1]
                if '-' in old_version:
                    old_patchver = old_version.split('-')[-1]
                else:
                    old_patchver = old_version
                
                old_suffix_match = re.search(r'(-[a-z]+\.\d+)$', old_patchver)
                old_suffix = old_suffix_match.group(1) if old_suffix_match else ''

                if old_suffix == current_suffix:
                    old_numeric = re.sub(r'(-[a-z]+\.\d+)?(-release\d*)?$', '', old_patchver)
                    current_numeric = re.sub(r'(-[a-z]+\.\d+)?(-release\d*)?$', '', patchver)
                    if old_numeric < current_numeric:
                        r.delete_release()
            except:
                pass

    if not existing_release:
        # Dynamically compile the warning section block layout structure
        release_body = "# Release Notes\n\n"
        
        if failed_patches:
            release_body += "### ⚠️ Disclaimer: Failed Patches\nThe following patches could not be installed properly or were skipped this release:\n"
            for failed_patch in failed_patches:
                release_body += f"- `{failed_patch}`\n"
            release_body += "\n---\n\n"

        release_body += f"""## Build Tools:
- **{patch_branding} Patches:** v{patchver}
- **{cli_branding} CLI:** v{cliver}
"""
        if include_microg_note:
            release_body += f"""
## Note:
**{microg_name}** is **necessary** to function correctly. 
- Please **download** it from [HERE]({microg_link}).
"""

        release_name = f"{convert_title(name)} v{app_version}-{patchver}"
        
        existing_release = repo.create_git_release(
            tag=tag_name,
            name=release_name,
            message=release_body,
            draft=False,
            prerelease=False
        )

    existing_release.upload_asset(
        path=str(apk_path),
        label=apk_path.name,
        content_type='application/vnd.android.package-archive'
    )
