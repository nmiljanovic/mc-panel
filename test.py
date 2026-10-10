#!/usr/bin/env python3

import urllib.request
import re

wiki_url = 'https://minecraft.wiki/w/Bedrock_Dedicated_Server'

def get_latest_version_url(wiki_url):
    try:
        # Get the HTML
        req = urllib.request.Request(
            wiki_url, headers={"User-Agent": "Wget/1.21"})
        with urllib.request.urlopen(req, timeout=10) as response:
            # urllib returns bytes, decode to string
            html_content = response.read().decode('utf-8')
        # print(response.status)
        # Look for https link containing 'bin-linux' ending in .zip
        # links = re.findall(
        #    r'https://[^\s"<>]+bin-linux[^\s"<>]+?\.zip', html_content)
        # Filter out "preview" versions
        # stable_link = [link for link in links if "preview" not in link.lower()]
        # Return the last match
        #return stable_link[-1] if stable_link else None
        match = re.search(
            r'<b>Release:</b>\s*<a[^>]*>([0-9.]+)</a>', 
            html_content
        )
        
        if match:
            version = match.group(1)
            return f"https://www.minecraft.net/bedrockdedicatedserver/bin-linux/bedrock-server-{version}.zip"
    
    except Exception:
        return None

if __name__ == '__main__':
    version_url = get_latest_version_url(wiki_url)
    print(version_url)
