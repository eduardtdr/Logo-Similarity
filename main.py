import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
from PIL import Image
import imagehash
from collections import defaultdict

df = pd.read_parquet("logos.snappy.parquet", engine="pyarrow")

sample_df = df.copy()

def get_logo_url(domain):
    for scheme in ['https://', 'http://']:
        try:
            url = f"{scheme}{domain}"
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, 'html.parser')

            for tag in soup.find_all(['link', 'img', 'meta']):
                tag_str = str(tag).lower()
                if 'logo' in tag_str or 'icon' in tag_str:
                    if tag.has_attr('href'):
                        return urljoin(url, tag['href'])
                    elif tag.has_attr('src'):
                        return urljoin(url, tag['src'])
                    elif tag.has_attr('content'):
                        return urljoin(url, tag['content'])

            favicon_url = url + "/favicon.ico"
            fav_response = requests.get(favicon_url, timeout=5)
            if fav_response.status_code == 200 and 'image' in fav_response.headers.get('Content-Type', ''):
                return favicon_url

        except Exception as e:
            continue
    return None

logo_urls = []
for i in range(len(sample_df)):
    domain = sample_df.iloc[i, 0]
    print(f"URL for {domain}")
    logo_url = get_logo_url(domain)
    logo_urls.append(logo_url)

sample_df['logo_url'] = logo_urls

os.makedirs("../logos", exist_ok=True)
valid_extensions = (".png", ".jpg", ".jpeg", ".ico", ".svg")
downloaded_files = []

for i, row in sample_df.iterrows():
    domain = row['domain']
    url = row['logo_url']

    if not isinstance(url, str) or not url.lower().endswith(valid_extensions):
        downloaded_files.append(None)
        continue

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
            ext = url.split('.')[-1].split('?')[0][:4]  # Short clean extension
            filename = f"logos/{domain.replace('.', '_')}.{ext}"
            with open(filename, 'wb') as f:
                f.write(response.content)
            downloaded_files.append(filename)
        else:
            downloaded_files.append(None)
    except Exception as e:
        print(f"Error downloading {domain}: {e}")
        downloaded_files.append(None)

sample_df['logo_file'] = downloaded_files
sample_df.to_csv("sample_logos_with_files.csv", index=False)

hashes = []
files = sample_df['logo_file'].tolist()

for file in files:
    if file and os.path.exists(file):
        try:
            img = Image.open(file).convert("RGBA").resize((64, 64))
            hash_val = imagehash.phash(img)
            hashes.append(hash_val)
        except Exception as e:
            print(f"Error processing image {file}: {e}")
            hashes.append(None)
    else:
        hashes.append(None)

sample_df['phash'] = hashes

groups = defaultdict(list)

for i in range(len(sample_df)):
    h1 = sample_df.iloc[i]['phash']
    if h1 is None:
        continue
    added = False
    for group_hash, members in groups.items():
        if group_hash - h1 <= 10:
            members.append(sample_df.iloc[i]['domain'])
            added = True
            break
    if not added:
        groups[h1] = [sample_df.iloc[i]['domain']]


print("Similar Logos:")
for i, (h, domains) in enumerate(groups.items(), 1):
    print(f"Group {i}: {domains}")
