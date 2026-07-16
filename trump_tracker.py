import os
import re
import requests
from google import genai
from groq import Groq
from dotenv import load_dotenv
from datetime import datetime, timezone

# Ladataan ympäristömuuttujat (.env tai GitHub Secrets)
load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

TRUSTED_DOMAINS = (
    "reuters.com,apnews.com,bbc.co.uk,bbc.com,nytimes.com,washingtonpost.com,"
    "bloomberg.com,theguardian.com,politico.com,cnn.com,wsj.com,cnbc.com"
)

def get_trump_news():
    if not NEWS_API_KEY:
        print("Virhe: NEWS_API_KEY puuttuu!")
        return

    print("Haetaan tuoreimpia uutisia...")
    url = (
        f"https://newsapi.org/v2/everything?"
        f"q=Trump"
        f"&domains={TRUSTED_DOMAINS}"
        f"&language=en"
        f"&sortBy=publishedAt"
        f"&pageSize=20"
        f"&apiKey={NEWS_API_KEY}"
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

    news_feed_text = ""
    for idx, art in enumerate(articles):
        if art.get('title') and art.get('description'):
            news_feed_text += (
                f"[{idx}] Title: {art['title']}\n"
                f"Source: {art['source']['name']}\n"
                f"URL: {art['url']}\n"
                f"Snippet: {art['description']}\n\n"
            )

    # Tiukennettu prompti, joka kieltää suorat käännökset ja vaatii uutistoimittajan otetta
    prompt = f"""
    Olet kokenut suomalainen uutistoimittaja ja toimitussihteeri. Tehtäväsi on luoda objektiivinen Top 5 -uutiskatsaus viimeisimmistä Donald Trumpiin liittyvistä uutisista.
    Käytä alla olevaa englanninkielistä uutissyötettä raakamateriaalina.

    TÄRKEÄT KIELIOHJEET (ÄLÄ TEE SUORAA KÄÄNNÖSTÄ):
    - Älä käännä sanoja tai lauserakenteita suoraan englannista suomeksi. Lue uutinen, ymmärrä sen ydin ja kirjoita se uudelleen sujuvalle ja luonnolliselle suomen yleiskielelle.
    - Välidä anglismeja, huonoja suoria käännöksiä (kuten "poliisiluokka", "yhteisöllisyys" väärässä kontekstissa) tai tönkköjä passiivirakenteita.
    - Kirjoita uutistyyliin: napakasti, asiallisesti, selkeästi ja ammattimaisesti.
    - Jokaisen tiivistelmän pituus tulee olla 2-4 lausetta.
    - Liitä jokaisen uutisen loppuun englanninkielinen lähde ja URL-osoite muodossa: (Lähde: [Median Nimi], URL: [Linkki])

    Muotoile vastauksesi TISMALLEEN näin jokaisen 5 uutisen kohdalla (ilman Markdown-tähtiä tai -merkintöjä):
    <uutinen>
    <otsikko>Tähän lyhyt, iskevä ja uutismainen suomenkielinen otsikko</otsikko>
    <sisalto>Tähän suomenkielinen uutisteksti ja loppuun lähde linkkeineen.</sisalto>
    </uutinen>

    UUTISSYÖTE:
    {news_feed_text}
    """

    print(f"Löytyi {len(articles)} uutista. Luodaan Top 5 -tiivistystä suomeksi...")
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

    # YRITYS 2 (FALLBACK): Groq API (Päivitetty huomattavasti älykkäämpään 70B-malliin!)
    if not tiivistys and GROQ_API_KEY:
        try:
            print("-> Siirrytään varajärjestelmään (Groq)...")
            groq_client = Groq(api_key=GROQ_API_KEY)
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-specdec",  # Järeä, suomea hyvin osaava 70-miljardinen malli
            )
            tiivistys = chat_completion.choices[0].message.content
            kaytetty_tekoaly = "Groq (Llama 3.3 70B)"
        except Exception as e:
            print(f"Kriittinen virhe: Myös varajärjestelmä Groq epäonnistui. Virhe: {e}")

    if tiivistys:
        kirjoita_html_sivu(tiivistys, kaytetty_tekoaly)
    else:
        print("Uutistiivistelmän luonti epäonnistui kokonaan.")

def kirjoita_html_sivu(teksti, tekoaly):
    nykyhetki = datetime.now(timezone.utc).strftime("%d.%m.%Y klo %H:%M (UTC)")
    
    # Etsitään tekoälyn tuottamat <uutinen>-lohkot raakatekstistä
    uutis_lohkot = re.findall(r'<uutinen>(.*?)</uutinen>', teksti, re.DOTALL)
    
    html_sisalto = ""
    url_pattern = r'(https?://[^\s\)\>]+)'
    
    if uutis_lohkot:
        for lohko in uutis_lohkot:
            # Kaivetaan otsikko ja sisältö tagien sisältä
            otsikko_match = re.search(r'<otsikko>(.*?)</otsikko>', lohko, re.DOTALL)
            sisalto_match = re.search(r'<sisalto>(.*?)</sisalto>', lohko, re.DOTALL)
            
            otsikko = otsikko_match.group(1).strip() if otsikko_match else "Uutinen"
            sisalto = sisalto_match.group(1).strip() if sisalto_match else lohko.strip()
            
            # Siistitään tähdet pois tekstistä
            otsikko = otsikko.replace("**", "").replace("*", "")
            sisalto = sisalto.replace("**", "").replace("*", "")
            
            # Korvataan rivinvaihdot HTML-rivinvaihdoilla
            sisalto_html = sisalto.replace("\n", "<br>")
            
            # Muutetaan tekstissä olevat linkit klikattaviksi HTML-linkeiksi
            sisalto_html = re.sub(url_pattern, r'<a href="\1" target="_blank">\1</a>', sisalto_html)
            
            # Luodaan puhdas ja tiivis korttirakenne
            html_sisalto += f"""
            <div class="news-card">
                <div class="card-title">{otsikko}</div>
                <div class="card-content">{sisalto_html}</div>
            </div>
            """
    else:
        # Varasysteemi, jos tekoäly jostain syystä ohitti tagit kokonaan
        muotoiltu_teksti = teksti.replace("\n", "<br>")
        muotoiltu_teksti = re.sub(url_pattern, r'<a href="\1" target="_blank">\1</a>', muotoiltu_teksti)
        html_sisalto = f'<div class="news-card"><div class="card-content">{muotoiltu_teksti}</div></div>'
    
    # HTML-sivun muotoilu puhtaalla ja modernilla ilmeellä ilman punaista
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
            margin-bottom: 25px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .meta::before {{
            content: "•";
            color: #4A5568;
            font-weight: bold;
        }}
        .news-card {{
            background: #ffffff;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03), 0 2px 4px -1px rgba(0, 0, 0, 0.02);
            border: 1px solid #E2E8F0;
            margin-bottom: 16px;
        }}
        .card-title {{
            font-size: 18px;
            font-weight: 750;
            color: #1A202C;
            margin-bottom: 8px;
            line-height: 1.35;
        }}
        .card-content {{
            font-size: 14.5px;
            color: #4A5568;
        }}
        a {{
            color: #3182CE;
            text-decoration: none;
            font-weight: 600;
            word-break: break-all;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        footer {{
            margin-top: 40px;
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
    print("index.html päivitetty onnistuneesti parannetulla kielellä, jättimallilla ja linkeillä!")

if __name__ == "__main__":
    get_trump_news()
