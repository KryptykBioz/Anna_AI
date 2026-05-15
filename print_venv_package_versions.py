import os
import re

def find_site_packages(path, found):
    try:
        entries = list(os.scandir(path))
    except PermissionError:
        return
    for e in entries:
        if not e.is_dir():
            continue
        if e.name == 'site-packages':
            found.append(e.path)
        else:
            find_site_packages(e.path, found)

def collect_packages(site_packages):
    results = []
    try:
        entries = os.scandir(site_packages)
    except PermissionError:
        return results
    for e in entries:
        if e.is_dir() and e.name.endswith('.dist-info'):
            m = re.match(r'^(.+)-([^-]+)\.dist-info$', e.name)
            if m:
                results.append((m.group(1), m.group(2)))
    return results

found = []
find_site_packages('.', found)

if not found:
    print("[Warning] No site-packages directories found.")
else:
    all_packages = []
    for sp in found:
        all_packages.extend(collect_packages(sp))
    all_packages.sort(key=lambda x: x[0].lower())
    for name, version in all_packages:
        print(f"{name}=={version}")