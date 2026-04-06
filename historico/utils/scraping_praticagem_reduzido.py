import requests
from bs4 import BeautifulSoup

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
    response = requests.get(URL, timeout=20)
    response.raise_for_status()

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

    return navios_filtrados


if __name__ == "__main__":
    dados = get_navios_cargo_reduzido()
    print(f"Total navios filtrados: {len(dados)}")
    for n in dados:
        print(n)
