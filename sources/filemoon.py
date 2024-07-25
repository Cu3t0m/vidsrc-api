import re
import requests
from utils import Utilities
from typing import Optional, Tuple, Dict, Any

class FilemoonExtractor:
    @staticmethod
    def unpack(p: str, a: int, c: int, k: list, e: Optional[Any]=None, d: Optional[Any]=None) -> str:
        for i in range(c-1, -1, -1):
            if k[i]: p = re.sub("\\b"+Utilities.int_2_base(i,a)+"\\b", k[i], p)
        return p

    def resolve_source(self, url: str, **kwargs: Dict[str, Any]) -> Tuple[Optional[str], None, Optional[str]]:
        req = requests.get(url)
        if req.status_code != 200:
            print(f"[FilemoonExtractor] Failed to retrieve media, status code: {req.status_code}...")
            return None, None, None

        matches = re.search(r"eval\(function\(p,a,c,k,e,d\).*?\}\('(.*?)'\.split", req.text)
        if not matches:
            print("[FilemoonExtractor] Failed to retrieve media, could not find eval function...")
            return None, None, None
        
        DE_packer_args = re.search(r"^(.*?}\);)\',(.*?),(.*?),'(.*?)$", matches.group(1))
        processed_matches = list(DE_packer_args.groups())
        processed_matches[1] = int(processed_matches[1])
        processed_matches[2] = int(processed_matches[2])
        processed_matches[3] = processed_matches[3].split("|")

        unpacked = self.unpack(*processed_matches)
        hls_urls = re.findall(r"\{file:\"([^\"]*)\"\}", unpacked)

        # hls_filename = hls_urls[0].split("?")[0].rsplit("/")[-1]
        # mp4_url = hls_urls[0].replace("hls2", "download") #.replace(hls_filename, "media") # filename is arbitrary
        
        return hls_urls, None, url