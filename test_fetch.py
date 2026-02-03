import urllib.request
import re
from urllib.parse import quote, urljoin

def test_fetch():
    movie = "Race 2"
    url = f"https://www.yts-official.top/browse-movies?keyword={quote(movie)}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    try:
        print(f"📡 Terminal Search for '{movie}'...")
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
            # Find ALL movie links to show the user the matching
            matches = re.findall(r'href="([^"]*/movies/[^"]+)"', html)
            unique_links = []
            for m in matches:
                full_url = urljoin("https://www.yts-official.top/", m)
                if '/movies/' in full_url and full_url not in unique_links:
                    unique_links.append(full_url)
            
            print(f"🔍 Found {len(unique_links)} matches on the search page:")
            for idx, link in enumerate(unique_links):
                print(f"   [{idx+1}] {link}")
            
            if unique_links:
                # Let's try to be smart and find an exact match if possible
                target_link = None
                for link in unique_links:
                    if "race-2-" in link.lower() and "death" not in link.lower():
                        target_link = link
                        break
                
                if not target_link: target_link = unique_links[-1]
                
                print(f"\n🎯 Selected Target: {target_link}")
                
                # Fetch Magnet
                req2 = urllib.request.Request(target_link, headers=headers)
                with urllib.request.urlopen(req2) as resp2:
                    details = resp2.read().decode('utf-8', errors='ignore')
                    magnets = re.findall(r'magnet:\?xt=urn:btih:[^"\'\s<>]+', details)
                    if magnets:
                        print(f"✅ Found Magnet: {magnets[0][:60]}...")
                    else:
                        print("❌ No magnet found.")
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    test_fetch()
