import os
import requests
from google import genai
from groq import Groq
from dotenv import load_dotenv
from datetime import datetime, timezone

# Ladataan ympäristömuuttujat (paikallista käyttöä varten .env-tiedostosta, GitHubissa Secrets-asetuksista)
load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Luotettavat globaalit uutismediat (whitelist)
TRUSTED_DOMAINS = (
    "reuters.com,apnews.com,bbc.co.uk,bbc.com,nytimes.com,washingtonpost.com,"
    "bloomberg.com,theguardian.com,politico.com,cnn.com,wsj.com,cnbc.com"
)

def get_trump_news():
    if not NEWS_API_KEY:
        print("Virhe: NEWS_API_KEY puuttuu! Varmista ympäristömuuttujat tai .env-tiedosto.")
        return

    print("Haetaan tuoreimpia uutisia...")
    url = (
        f"https://newsapi.org/v2/everything?"
        f"q=Trump&"
        f"domains={TRUSTED_DOMAINS}&"
        f"language=en&"
        f"sortBy=publishedAt&"
        f"pageSize=20&"
        f"apiKey={NEWS_API_KEY}"
    )
    
    try:
        response = requests.get(url).json()
    except Exception as e:
        print(f"Yhteysvirhe uutispalveluun: {e}")
        return

    if response.get("status") == "error":
        print(f"NewsAPI Virhe: {response.get('message')}")
        return

    articles = response.get("articles", [])
    if not articles:
        print("Ei löytynyt Trump-aiheisia uutisia.")
        return

    # Muotoillaan uutisotsikot ja -kuvaukset yhteen pötköön tekoälylle lähetettäväksi
    news_feed_text = ""
    for idx, art in enumerate(articles):
        if art.get('title') and art.get('description'):
            news_feed_text += (
                f"[{idx}] Title: {art['title']}\n"
                f"Source: {art['source']['name']}\n"
                f"URL: {art['url']}\n"
                f"Snippet: {art['description']}\n\n"
            )

    prompt = f"""
    Tehtäväsi on luoda objektiivinen Top 5 -tiivistys viimeisimmistä ja tärkeimmistä Donald Trumpiin liittyvistä uutisista.
    Käytä alla olevaa uutissyötettä materiaalina.

    Säännöt:
    1. Kirjoita jokainen tiivistys suomeksi (noin 2-4 napakkaa lausetta per uutinen).
    2. Liitä JOKAISEN uutisen loppuun alkuperäinen englanninkielinen lähde ja URL-osoite muodossa: (Lähde: [Median Nimi], URL: [Linkki])
    3. Valitse vain oikeasti uutisarvoiset ja merkittävät aiheet. Älä toista samaa uutisaihetta useasti.
    4. Palauta vastaus numeroituna listana, jossa uutiset alkavat muodossa "1. ", "2. " jne., jotta koodi osaa palastella ne siisteiksi laatikoiksi.

    UUTISSYÖTE:
    {news_feed_text}
    """

    print(f"Löytyi {len(articles)} uutista. Luodaan Top 5 -tiivistystä...")
    tiivistys = ""
    kaytetty_tekoaly = ""

    # YRITYS 1: Google Gemini (Ensisijainen)
    if GEMINI_API_KEY:
        try:
            print("Yritetään luoda tiivistelmä Google Geminillä...")
            client = genai.Client(api_key=GEMINI_API_KEY)
            gemini_response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
            )
            tiivistys = gemini_response.text
            kaytetty_tekoaly = "Google Gemini"
        except Exception as e:
            print(f"-> Gemini epäonnistui tai oli ruuhkainen. Virhe: {e}")

    # YRITYS 2 (FALLBACK): Groq API (Varajärjestelmä)
    if not tiivistys and GROQ_API_KEY:
        try:
            print("-> Siirrytään varajärjestelmään (Groq)...")
            groq_client = Groq(api_key=GROQ_API_KEY)
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
            )
            tiivistys = chat_completion.choices[0].message.content
            kaytetty_tekoaly = "Groq (Llama 3)"
        except Exception as e:
            print(f"Kriittinen virhe: Myös varajärjestelmä Groq epäonnistui. Virhe: {e}")

    # Jos jompikumpi tekoäly tuotti vastauksen, kirjoitetaan HTML-sivu
    if tiivistys:
        kirjoita_html_sivu(tiivistys, kaytetty_tekoaly)
    else:
        print("Uutistiivistelmän luonti epäonnistui molemmilla tekoälypalveluilla.")

import re

def kirjoita_html_sivu(teksti, tekoaly):
    nykyhetki = datetime.now(timezone.utc).strftime("%d.%m.%Y klo %H:%M (UTC)")
    
    # Korvataan rivinvaihdot HTML-rivinvaihdoilla
    muotoiltu_teksti = teksti.replace("\n", "<br>")
    
    # Tunnistetaan tekstissä olevat URL-osoitteet ja muutetaan ne klikattaviksi HTML-linkeiksi.
    # target="_blank" varmistaa, että linkki aukeaa puhelimessa uuteen välilehteen.
    url_pattern = r'(https?://[^\s\)\>]+)'
    muotoiltu_teksti = re.sub(url_pattern, r'<a href="\1" target="_blank">\1</a>', muotoiltu_teksti)
    
    # Korjataan mahdolliset tuplalinkitykset, jos LLM on jo tuottanut valmiiksi HTML-linkkejä
    muotoiltu_teksti = muotoiltu_teksti.replace('href="<a href="', 'href="')
    
    # Paloitellaan teksti uutisiksi numeroiden (esim. "1. ", "2. ") perusteella,
    # jotta saamme jokaisen uutisen omaan tyylikkääseen laatikkoonsa.
    uutiset = []
    current_part = muotoiltu_teksti
    
    for i in range(1, 6):
        seuraava_numero = f"{i+1}. "
        nykyinen_numero = f"{i}. "
        
        if nykyinen_numero in current_part:
            if i < 5 and seuraava_numero in current_part:
                # Otetaan teksti nykyisen ja seuraavan numeron välistä
                osat = current_part.split(seuraava_numero, 1)
                uutis_osa = osat[0].replace(nykyinen_numero, "").strip()
                current_part = seuraava_numero + osat[1] # Jätetään loppuosa seuraavaa kierrosta varten
            else:
                # Viimeinen uutinen (numero 5) ottaa kaiken lopun tekstistä
                uutis_osa = current_part.replace(nykyinen_numero, "").strip()
            
            # Siistitään turhat rivinvaihdot uutisen alusta ja lopusta
            while uutis_osa.startswith("<br>"): uutis_osa = uutis_osa[4:]
            while uutis_osa.endswith("<br>"): uutis_osa = uutis_osa[:-4]
            
            # Luodaan uutislaatikon (card) HTML-rakenne
            uutiset.append(f"""
            <div class="news-card">
                <div class="card-number">Uutinen #{i}</div>
                <div class="card-content">{uutis_osa}</div>
            </div>
            """)

    # Jos palastelu epäonnistui (LLM ei palauttanut numerolistaa), käytetään varasysteeminä yhtä isoa laatikkoa
    if not uutiset:
        html_sisalto = f'<div class="news-card"><div class="card-content">{muotoiltu_teksti}</div></div>'
    else:
        html_sisalto = "\n".join(uutiset)
    
    # Koko HTML-sivun pohja ja CSS-tyylit
    html_content = f"""<!DOCTYPE html>
<html lang="fi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Päivän Trump-tiivistys</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #2D3748;
            background-color: #F7FAFC;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 20px auto;
            padding: 10px;
        }}
        h1 {{
            font-size: 26px;
            color: #1A202C;
            margin-top: 0;
            margin-bottom: 5px;
            font-weight: 800;
            letter-spacing: -0.5px;
        }}
        .meta {{
            font-size: 13px;
            color: #718096;
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .meta::before {{
            content: "•";
            color: #E53E3E;
            font-weight: bold;
        }}
        .news-card {{
            background: #ffffff;
            padding: 24px;
            border-radius: 16px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            border: 1px solid #E2E8F0;
            margin-bottom: 20px;
            position: relative;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .news-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.02);
        }}
        .card-number {{
            font-size: 12px;
            font-weight: 800;
            color: #E53E3E;
            background: #FFF5F5;
            padding: 4px 10px;
            border-radius: 20px;
            display: inline-block;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .card-content {{
            font-size: 15.5px;
            color: #2D3748;
        }}
        a {{
            color: #3182CE;
            text-decoration: none;
            font-weight: 600;
            word-break: break-all; /* Estää pitkiä linkkejä rikkomasta laatikon reunoja puhelimessa */
        }}
        a:hover {{
            text-decoration: underline;
        }}
        footer {{
            margin-top: 50px;
            font-size: 11px;
            color: #A0AEC0;
            text-align: center;
            border-top: 1px solid #E2E8F0;
            padding-top: 20px;
            letter-spacing: 0.5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Päivän Trump-tiivistys</h1>
        <div class="meta">Päivitetty: {nykyhetki}</div>
        <div class="content">
            {html_sisalto}
        </div>
        <footer>
            AUTOMAATTINEN KOOSTE • LÄHTEENÄ VALITUT MEDIAT • TEKOÄLY: {tekoaly.upper()}
        </footer>
    </div>
</body>
</html>
"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("index.html päivitetty onnistuneesti! Linkit ovat nyt klikattavia.")

if __name__ == "__main__":
    get_trump_news()