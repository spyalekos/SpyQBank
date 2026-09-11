"""
Prefetch and package full metadata dataset for SpyQBank.
"""
import os
import sys
import time
import random
import zipfile
import json
from datetime import datetime

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.version import APP_NAME, __version__
from src.iep_api import IepApiClient
from src.storage import StorageManager


def build_data_package():
    print("=" * 52)
    print(f"  {APP_NAME} v{__version__} - Full Data Package Builder")
    print("=" * 52 + "\n")

    api_client = IepApiClient()
    storage = StorageManager()

    print("[1/3] Loading School Tree...")
    tree = storage.load_tree()
    if not tree:
        print("  -> Fetching tree from IEP API...")
        tree = api_client.get_school_tree()
        storage.save_tree(tree)
        print(f"  [OK] Saved tree with {len(tree)} school types.")
    else:
        print(f"  [OK] Found existing tree with {len(tree)} school types.")

    all_subjects = []
    for st in tree:
        for cl in st.classes:
            for sub in cl.lessons:
                all_subjects.append((st, cl, sub))

    total = len(all_subjects)
    print(f"\n[2/3] Checking and Prefetching {total} subjects...")

    downloaded = 0
    cached = 0
    errors = 0
    total_items = 0
    start_time = time.time()

    for idx, (st, cl, sub) in enumerate(all_subjects, start=1):
        prefix = f"[{idx:03d}/{total:03d}] ({st.name[:6]} - {cl.name}) {sub.name[:35]}"
        existing = storage.load_subject_items(st.id, cl.id, sub.id)
        if existing is not None:
            cached += 1
            cnt = len(existing)
            total_items += cnt
            print(f"  [CACHE] {prefix} -> {cnt} items")
            continue

        time.sleep(random.uniform(0.6, 1.4))
        try:
            items = api_client.get_subject_items(st.id, cl.id, sub.id)
            storage.save_subject_items(st.id, cl.id, sub.id, items)
            downloaded += 1
            cnt = len(items)
            total_items += cnt
            print(f"  [API OK] {prefix} -> {cnt} items")
        except Exception as ex:
            errors += 1
            print(f"  [ERROR] {prefix} -> {ex}")

    elapsed = round(time.time() - start_time, 1)
    print("\n" + "-" * 52)
    print(f"Prefetch completed in {elapsed}s:")
    print(f"  * Total Subjects: {total}")
    print(f"  * Downloaded from API: {downloaded}")
    print(f"  * Already Cached: {cached}")
    print(f"  * Errors: {errors}")
    print(f"  * Total Question Items in Cache: {total_items}")
    print("-" * 52 + "\n")

    print("[3/3] Creating distribution ZIP archive...")
    dist_dir = os.path.abspath("dist")
    os.makedirs(dist_dir, exist_ok=True)
    zip_filename = f"SpyQBank_Data_Package_v{__version__}.zip"
    zip_path = os.path.join(dist_dir, zip_filename)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        data_dir = os.path.abspath("data")
        tree_file = os.path.join(data_dir, "school_tree.json")
        if os.path.exists(tree_file):
            zipf.write(tree_file, os.path.join("data", "school_tree.json"))
        cache_dir = os.path.join(data_dir, "cache")
        if os.path.exists(cache_dir):
            for fname in os.listdir(cache_dir):
                if fname.endswith(".json"):
                    fpath = os.path.join(cache_dir, fname)
                    zipf.write(fpath, os.path.join("data", "cache", fname))

    zip_size_mb = round(os.path.getsize(zip_path) / (1024 * 1024), 2)
    print("  SUCCESS: Data package created!")
    print(f"  Archive: {zip_path}")
    print(f"  Size: {zip_size_mb} MB\n")
    return zip_path


if __name__ == "__main__":
    build_data_package()
