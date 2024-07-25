import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote
from typing import Optional, Tuple, Dict, List

from fastapi import FastAPI, HTTPException, Query

from sources.f2cloud import F2CloudExtractor
from sources.filemoon import FilemoonExtractor
from utils import Utilities, VidSrcError, NoSourcesFound

app = FastAPI()

SUPPORTED_SOURCES = ["F2Cloud", "Filemoon"]

class VidSrcExtractor:
    BASE_URL = "https://vidsrc.to"
    PROVIDER_URL = "https://vid2v11.site"  # vidplay.site / vidplay.online / vidplay.lol
    TMDB_BASE_URL = "https://www.themoviedb.org"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
    KEYS = {}

    def __init__(self, source_name: str = "F2Cloud", fetch_subtitles: bool = False) -> None:
        self.source_name = source_name
        self.fetch_subtitles = fetch_subtitles
        self.KEYS = F2CloudExtractor.get_keys()

    def get_encryption_key(self) -> str:
        return F2CloudExtractor.get_key(self.KEYS, True, 0)

    def get_decryption_key(self) -> str:
        return F2CloudExtractor.get_key(self.KEYS, False, 0)

    def encode_id(self, v_id: str) -> str:
        key = self.get_encryption_key()
        return F2CloudExtractor.encode(key, v_id)

    def decrypt_source_url(self, source_url: str) -> str:
        encoded = Utilities.decode_base64_url_safe(source_url)
        decoded = Utilities.decode_data(self.get_decryption_key(), encoded)
        decoded_text = decoded.decode('utf-8')
        return unquote(decoded_text)

    def get_source_url(self, source_id: str) -> str:
        req = requests.get(f"{VidSrcExtractor.BASE_URL}/ajax/embed/source/{source_id}?token={self.encode_id(source_id)}")
        if req.status_code != 200:
            error_msg = f"Couldn't fetch {req.url}, status code: {req.status_code}..."
            raise VidSrcError(error_msg)

        data = req.json()
        encrypted_source_url = data.get("result", {}).get("url")
        return self.decrypt_source_url(encrypted_source_url)

    def get_sources(self, data_id: str) -> Dict:
        req = requests.get(f"{VidSrcExtractor.BASE_URL}/ajax/embed/episode/{data_id}/sources?token={self.encode_id(data_id)}")
        if req.status_code != 200:
            error_msg = f"Couldn't fetch {req.url}, status code: {req.status_code}..."
            raise VidSrcError(error_msg)

        data = req.json()
        return {video.get("title"): video.get("id") for video in data.get("result")}

    def get_streams(self, media_type: str, media_id: str, season: Optional[str], episode: Optional[str]) -> Tuple[Optional[List], Optional[Dict], Optional[str]]:
        url = f"{VidSrcExtractor.BASE_URL}/embed/{media_type}/{media_id}"
        if season and episode:
            url += f"/{season}/{episode}"

        req = requests.get(url)
        if req.status_code != 200:
            return None, None, None

        soup = BeautifulSoup(req.text, "html.parser")
        sources_code = soup.find('a', {'data-id': True})
        if not sources_code:
            return None, None, None

        sources_code = sources_code.get("data-id")
        sources = self.get_sources(sources_code)
        source = sources.get(self.source_name)
        if not source:
            return None, None, None

        source_url = self.get_source_url(source)

        if self.source_name == "F2Cloud":
            extractor = F2CloudExtractor(self.KEYS)
            return extractor.resolve_source(url=source_url, fetch_subtitles=self.fetch_subtitles, provider_url=VidSrcExtractor.PROVIDER_URL)

        elif self.source_name == "Filemoon":
            extractor = FilemoonExtractor()
            return extractor.resolve_source(url=source_url, fetch_subtitles=self.fetch_subtitles, provider_url=VidSrcExtractor.PROVIDER_URL)

        else:
            return None, None, None

def get_streaming_url(tmdb_id: str, source_name: str, media_type: str, season: Optional[str] = None, episode: Optional[str] = None) -> str:
    extractor = VidSrcExtractor(source_name=source_name, fetch_subtitles=False)
    streams, subtitles, source_url = extractor.get_streams(media_type, tmdb_id, season, episode)
    if streams:
        return streams[0] if isinstance(streams, list) else streams
    else:
        raise NoSourcesFound("Could not find any streams for the given parameters.")

@app.get("/api/scrape/{tmdb_id}")
def scrape_streaming_url(tmdb_id: str, s: Optional[str] = Query(None), e: Optional[str] = Query(None), source_name: str = "F2Cloud", media_type: str = "movie"):
    try:
        url = get_streaming_url(
            tmdb_id=tmdb_id,
            source_name=source_name,
            media_type=media_type,
            season=s,
            episode=e
        )
        return {"sources": [{'label': 'Auto', 'file': f'https://vid-nl-prx.streamflix.one/proxy?url={url}'}]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Run the application using uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9876)