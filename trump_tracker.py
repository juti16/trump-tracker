import os
import requests
from google import genai
from groq import Groq
from dotenv import load_dotenv
from datetime import datetime, timezone

# Ladataan ympäristömuuttujat (paikallista käyttöä varten .env, GitHubissa ne tulevat secrets-asetuksista)
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

    UUTISSYÖTE:
    {news_feed_text}
    """

    print(f"Löytyi {len(articles)} uutista. Luodaan Top 5 -tiivistystä...")
    tiivistys = ""
    kaytetty_tekoaly = ""

    # YRITYS 1: Google Gemini
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

    # YRITYS 2 (FALLBACK): Groq API (Llama-malli)
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

    if tiivistys:
        kirjoita_html_sivu(tiivistys, kaytetty_tekoaly)
    else:
        print("Uutistiivistelmän luonti epäonnistui kokonaan.")

def kirjoita_html_sivu(teksti, tekoaly):
    nykyhetki = datetime.now(timezone.utc).strftime("%d.%m.%Y klo %H:%M (UTC)")
    
    # Muutetaan markdown-tyyliset linkit [Teksti](URL) HTML-linkeiksi
    # Koska uutisbotti tuottaa usein linkkejä muodossa (Lähde: Reuters, URL: https://...)
    # Tehdään simppeli tekstin muotoilu HTML:ää varten
    html_teksti = teksti.replace("\n", "<br>")
    
    # Parannellaan listojen ulkoasua jos LLM palauttaa ne markdown-muodossa
    for i in range(1, 6):
        html_teksti = html_teksti.replace(f"{i}. ", f"<h3>{i}. ")
    
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
            color: #333;
            background-color: #faf8f5;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 650px;
            margin: 40px auto;
            background: #ffffff;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            border: 1px solid #eef0f2;
        }}
        h1 {{
            font-size: 24px;
            color: #1a1a1a;
            margin-top: 0;
            border-bottom: 2px solid #eaeaea;
            padding-bottom: 10px;
        }}
        .meta {{
            font-size: 13px;
            color: #888;
            margin-bottom: 25px;
        }}
        .content {{
            font-size: 16px;
        }}
        h3 {{
            color: #c92a2a;
            font-size: 18px;
            margin-top: 25px;
            margin-bottom: 5px;
        }}
        a {{
            color: #228be6;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        footer {{
            margin-top: 40px;
            font-size: 12px;
            color: #aaa;
            text-align: center;
            border-top: 1px solid #eee;
            padding-top: 15px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Päivän Trump-tiivistys (Top 5)</h1>
        <div class="meta">Päivitetty: {nykyhetki}</div>
        <div class="content">
            {html_teksti}
        </div>
        <footer>
            Luotu automaattisesti käyttäen uutishakua ja tekoälyä ({tekoaly}).
        </footer>
    </div>
</body>
</html>
"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("index.html päivitetty onnistuneesti!")

if __name__ == "__main__":
    get_trump_news()