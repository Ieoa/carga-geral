import requests
from bs4 import BeautifulSoup
import json
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings

URL = "https://www.praticagem-rj.com.br/"

# tipos permitidos
TIPOS_PERMITIDOS = {
    "CARGO SHIP",
    "OFFSHORE SHIP",
    "DIVING SUPPORT VESSEL",
    "SUPPLY SHIP",
    "CONTAINER SHIP"
}

def get_navios_cargo_reduzido():
    """
    Faz scraping direto do site da Praticagem e retorna
    apenas navios do tipo Cargo (etc) nos terminais TECONTPROLONG / TECONT1.
    """
    try:
        response = requests.get(URL, timeout=20)
        response.raise_for_status()
    except requests.RequestException:
        return _load_cached_navios()

    soup = BeautifulSoup(response.text, "html.parser")
    tabela = soup.find("table", {"class": "tabelaManobras"})

    navios_filtrados = []

    if tabela:
        linhas = tabela.find_all("tr")[1:]  # ignorar header
        for linha in linhas:
            colunas = linha.find_all("td")
            if len(colunas) < 6:
                continue

            data = colunas[0].get_text(strip=True)
            hora = colunas[1].get_text(strip=True)
            navio = colunas[2].get_text(strip=True)
            tipo_navio = colunas[3].get_text(strip=True).upper()
            terminal = colunas[5].get_text(strip=True).upper()

            if ("TECONTPROLONG" in terminal or "TECONT1" in terminal) and tipo_navio in TIPOS_PERMITIDOS:
                navios_filtrados.append({
                    "data": data,
                    "hora": hora,
                    "navio": navio,
                    "tipo_navio": tipo_navio,
                    "terminal": terminal,
                })

    _save_cached_navios(navios_filtrados)
    return navios_filtrados


def _load_cached_navios():
    CACHE_FILE = _cache_file()
    if not CACHE_FILE.exists():
        return []

    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _save_cached_navios(navios):
    CACHE_FILE = _cache_file()
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(navios, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _cache_file():
    try:
        media_root = getattr(settings, "MEDIA_ROOT", Path.cwd() / "media")
    except ImproperlyConfigured:
        media_root = Path.cwd() / "media"
    return Path(media_root) / "cache" / "praticagem_navios.json"


if __name__ == "__main__":
    dados = get_navios_cargo_reduzido()
    print(f"Total navios filtrados: {len(dados)}")
    for n in dados:
        print(n)
