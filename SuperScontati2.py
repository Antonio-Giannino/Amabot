import telebot
from telebot import types
import random
import re
import requests
import urllib.parse
from bs4 import BeautifulSoup
import threading
import time
from datetime import datetime
import os
from flask import Flask, request

TOKEN = "8881087185:AAFgDpXgtPLmx2VtAp2cDSEF8jpZn7aYxkk"

# ⚠️ INSERISCI QUI IL LINK CHE TI DARA' RENDER.COM (Senza la barra / finale)
# Esempio: "https://super-scontati-bot.onrender.com"
URL_RENDER = "https://amabot-rhkj.onrender.com"

GRUPPO_ID = -1004474584375 
TAG_AFFILIAZIONE = "agsmshop-21"
CHIAVE_SCRAPERAPI = "65695565af4705f1753039e7ea57eb87"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ⚙️ CONFIGURAZIONE CATEGORIE E THREAD ID (STANZE DEL FORUM)
CAT_DISPONIBILI = {
    "412609031": {"nome": "💻 Elettronica", "tag": "Elettronica", "thread_id": 3}, 
    "425916031": {"nome": "🖥️ Informatica", "tag": "Informatica", "thread_id": 4}, 
    "524015031": {"nome": "🏠 Casa e Cucina", "tag": "Casa", "thread_id": 5}, 
    "411664031": {"nome": "📚 Libri", "tag": "Libri", "thread_id": 9},
    "412606031": {"nome": "🎮 Videogiochi", "tag": "Videogiochi", "thread_id": None},
    "415082031": {"nome": "🧸 Giocattoli", "tag": "Giocattoli", "thread_id": None},
    "164001031": {"nome": "⚽ Sport", "tag": "Sport", "thread_id": 8},
    "65051031":  {"nome": "💊 Salute", "tag": "Salute", "thread_id": None},
    "65057031":  {"nome": "💄 Bellezza", "tag": "Bellezza", "thread_id": None},
    "2454160031": {"nome": "🛠️ Fai da te", "tag": "FaiDaTe", "thread_id": None},
    "2454152031": {"nome": "👕 Abbigliamento", "tag": "Abbigliamento", "thread_id": 10},
    "2454158031": {"nome": "👟 Scarpe e Borse", "tag": "Scarpe", "thread_id": 11},
    "domotica":   {"nome": "🏡 Domotica", "tag": "Domotica", "thread_id": 7}
}

impostazioni_bot = {
    "sconto_minimo": 0,
    "categorie_scelte": [], 
    "errori_prezzo": False
}

post_in_sospeso = {}

# ==========================================
# GESTORE CANCELLAZIONE AUTOMATICA (BACKGROUND)
# ==========================================
post_da_cancellare = [] 

def thread_cancellazione_automatica():
    """Controlla ogni 60 secondi se ci sono post scaduti da eliminare."""
    while True:
        try:
            ora_attuale = datetime.now()
            da_rimuovere = []
            
            for item in post_da_cancellare:
                if ora_attuale > item['scadenza']:
                    try:
                        bot.delete_message(item['chat_id'], item['message_id'])
                        print(f"✅ Post {item['message_id']} eliminato automaticamente per scadenza.")
                    except Exception as e:
                        print(f"⚠️ Impossibile eliminare il post {item['message_id']}: {e}")
                    
                    da_rimuovere.append(item)
            
            for item in da_rimuovere:
                post_da_cancellare.remove(item)
                
        except Exception as e:
            print(f"Errore nel thread di cancellazione: {e}")
            
        time.sleep(60)

t = threading.Thread(target=thread_cancellazione_automatica, daemon=True)
t.start()

# ==========================================
# 1. MENU PRINCIPALE E SOTTOMENU
# ==========================================

def menu_principale(chat_id, message_id=None):
    try:
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_auto = types.InlineKeyboardButton("🤖 Genera Automaticamente ❌", callback_data="menu_auto")
        btn_manuale = types.InlineKeyboardButton("✍️ Genera Manualmente", callback_data="menu_manuale")
        btn_canale = types.InlineKeyboardButton("📢 Gestione Gruppo Forum", callback_data="menu_canale")
        markup.add(btn_auto, btn_manuale, btn_canale)
        
        testo = "🛠️ **Pannello Controllo Bot Amazon**\nScegli la modalità di lavoro:"
        if message_id:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=testo, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, testo, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        print(f"Errore menu_principale: {e}")

def menu_auto(chat_id, message_id):
    try:
        markup = types.InlineKeyboardMarkup(row_width=2)
        num_cat = len(impostazioni_bot['categorie_scelte'])
        testo_cat = f"📁 Categorie: {num_cat}" if num_cat > 0 else "📁 Cat: Nessuna"
        btn_cat = types.InlineKeyboardButton(testo_cat, callback_data="menu_categorie")
        btn_sconto = types.InlineKeyboardButton(f"📉 Sconto: {impostazioni_bot['sconto_minimo']}%", callback_data="menu_sconti")
        stato_errori = "ON ✅" if impostazioni_bot['errori_prezzo'] else "OFF ❌"
        btn_errore = types.InlineKeyboardButton(f"⚠️ Errori Prezzo: {stato_errori}", callback_data="filtro_errore")
        btn_indietro = types.InlineKeyboardButton("🔙 Torna Indietro", callback_data="torna_principale")
        
        markup.add(btn_cat, btn_sconto)
        markup.add(btn_errore)
        markup.add(btn_indietro)
        
        testo = "🤖 **Impostazioni API Automatiche (In sviluppo)**\nPrepara i filtri per la ricerca:"
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=testo, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        menu_principale(chat_id)

def menu_canale(chat_id, message_id):
    try:
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_verifica = types.InlineKeyboardButton("🚀 Verifica Permessi Bot", callback_data="verifica_canale")
        btn_indietro = types.InlineKeyboardButton("🔙 Torna Indietro", callback_data="torna_principale")
        markup.add(btn_verifica, btn_indietro)
        
        testo = (f"📢 **Gestione Gruppo Forum**\nID Gruppo impostato: `{GRUPPO_ID}`\n\n"
                 f"⚠️ **ATTENZIONE:** Il bot DEVE essere Amministratore nel gruppo forum per poter inviare messaggi nei vari Topic.\n")
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=testo, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        menu_principale(chat_id)

def sottomenu_categorie(chat_id, message_id):
    try:
        markup = types.InlineKeyboardMarkup(row_width=2)
        pulsanti = []
        for codice, dati in CAT_DISPONIBILI.items():
            testo_btn = f"✅ {dati['nome']}" if codice in impostazioni_bot["categorie_scelte"] else dati['nome']
            pulsanti.append(types.InlineKeyboardButton(testo_btn, callback_data=f"cat_{codice}"))
            
        markup.add(*pulsanti)
        markup.add(types.InlineKeyboardButton("💾 Salva e Torna", callback_data="salva_categorie"))
        
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, 
                              text="📁 **Seleziona le categorie:**", reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        menu_principale(chat_id)

def chiedi_sconto(message):
    chat_id = message.chat.id
    try:
        if not message.text: raise ValueError("Input vuoto")
        valore = int(message.text.strip().replace('%', '')) 
        impostazioni_bot["sconto_minimo"] = valore
        bot.send_message(chat_id, f"✅ Perfetto! Cercherò solo prodotti con almeno il **{valore}%** di sconto.", parse_mode="Markdown")
        menu_principale(chat_id)
    except Exception as e:
        bot.send_message(chat_id, "❌ Errore: inserisci solo un NUMERO intero (es. 30). Riprova.")
        menu_principale(chat_id)

# ==========================================
# 2. SISTEMA DI ANTEPRIMA E MENU MODIFICHE
# ==========================================

def mostra_anteprima(chat_id, message_id=None):
    try:
        if chat_id not in post_in_sospeso:
            bot.send_message(chat_id, "❌ Dati del post scaduti. Riprova.")
            menu_principale(chat_id)
            return
            
        dati = post_in_sospeso[chat_id]
        
        testo_post = (
            f"‎\n*{dati['titolo']}*\n\n"
            f"_{dati['descrizione']}_\n\n"
            f"{dati['prezzo_riga']}"
            f"{dati['risparmio_riga']}"
            f"{dati['scadenza_riga']}"
            f"{dati['recensioni_riga']}"
            f"{dati['venditore_riga']}"
            f"🛒 [👉 VAI ALL'OFFERTA]({dati['link']})"
        )
        
        dati['testo_finale'] = testo_post
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_pubblica = types.InlineKeyboardButton("📤 PUBBLICA POST NEL GRUPPO", callback_data="pubblica_ora")
        btn_modifica = types.InlineKeyboardButton("✏️ MODIFICA POST", callback_data="menu_modifica")
        btn_annulla = types.InlineKeyboardButton("❌ Annulla e Torna", callback_data="torna_principale")
        markup.add(btn_pubblica, btn_modifica, btn_annulla)
        
        if message_id:
            if dati["immagine"]:
                try: bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=testo_post, reply_markup=markup, parse_mode="Markdown")
                except: bot.send_photo(chat_id, photo=dati["immagine"], caption=testo_post, parse_mode="Markdown", reply_markup=markup)
            else:
                try: bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=testo_post, reply_markup=markup, parse_mode="Markdown")
                except: bot.send_message(chat_id, testo_post, parse_mode="Markdown", reply_markup=markup)
        else:
            if dati["immagine"]:
                bot.send_photo(chat_id, photo=dati["immagine"], caption=testo_post, parse_mode="Markdown", reply_markup=markup)
            else:
                bot.send_message(chat_id, testo_post, parse_mode="Markdown", disable_web_page_preview=False, reply_markup=markup)
    except Exception as e:
        print(f"Errore anteprima: {e}")
        bot.send_message(chat_id, "❌ Impossibile caricare l'anteprima. Torno al menù.")
        menu_principale(chat_id)

def mostra_menu_modifiche(chat_id):
    try:
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_titolo = types.InlineKeyboardButton("📝 Titolo", callback_data="edit_titolo")
        btn_desc = types.InlineKeyboardButton("📝 Descrizione", callback_data="edit_desc")
        btn_prezzo = types.InlineKeyboardButton("💰 Prezzo", callback_data="edit_prezzo")
        btn_scad = types.InlineKeyboardButton("⏳ Scadenza", callback_data="edit_scadenza")
        btn_salva = types.InlineKeyboardButton("💾 SALVA E AGGIORNA ANTEPRIMA", callback_data="ritorna_anteprima")
        
        markup.add(btn_titolo, btn_desc)
        markup.add(btn_prezzo, btn_scad)
        markup.add(btn_salva)
        
        bot.send_message(chat_id, "⚙️ **PANNELLO DI MODIFICA POST**\nLe tue modifiche vengono salvate in memoria in background.\n\n_Scegli cosa modificare e clicca su **Salva e Aggiorna** solo quando hai finito!_", reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        menu_principale(chat_id)

def chiedi_nuovo_titolo(message):
    chat_id = message.chat.id
    try:
        if not message.text: raise ValueError("Testo vuoto")
        if chat_id in post_in_sospeso:
            nuovo_testo = re.sub(r'[*_`\[\]]', '', message.text.strip())
            post_in_sospeso[chat_id]['titolo'] = nuovo_testo
            bot.send_message(chat_id, "✅ Titolo memorizzato nella bozza!")
            mostra_menu_modifiche(chat_id)
    except Exception:
        bot.send_message(chat_id, "❌ Testo non valido.")
        mostra_menu_modifiche(chat_id)
 
def chiedi_nuova_descrizione(message):
    chat_id = message.chat.id
    try:
        if not message.text: raise ValueError("Testo vuoto")
        if chat_id in post_in_sospeso:
            nuovo_testo = re.sub(r'[*_`\[\]]', '', message.text.strip())
            post_in_sospeso[chat_id]['descrizione'] = nuovo_testo
            bot.send_message(chat_id, "✅ Descrizione memorizzata nella bozza!")
            mostra_menu_modifiche(chat_id)
    except Exception:
        bot.send_message(chat_id, "❌ Testo non valido.")
        mostra_menu_modifiche(chat_id)

def chiedi_nuovo_prezzo(message):
    chat_id = message.chat.id
    try:
        if not message.text: raise ValueError("Testo vuoto")
        if chat_id in post_in_sospeso:
            nuovo_testo = re.sub(r'[*_`\[\]]', '', message.text.strip())
            post_in_sospeso[chat_id]['prezzo_riga'] = f"💰 *Prezzo:* {nuovo_testo}\n"
            bot.send_message(chat_id, "✅ Prezzo memorizzato nella bozza!")
            mostra_menu_modifiche(chat_id)
    except Exception:
        bot.send_message(chat_id, "❌ Testo non valido.")
        mostra_menu_modifiche(chat_id)

def chiedi_nuova_scadenza(message):
    chat_id = message.chat.id
    try:
        if not message.text: raise ValueError("Testo vuoto")
        if chat_id in post_in_sospeso:
            testo_data = message.text.strip()
            data_scadenza = datetime.strptime(testo_data, "%d/%m/%Y").replace(hour=23, minute=59, second=59)
            post_in_sospeso[chat_id]['scadenza_cancellazione'] = data_scadenza
            post_in_sospeso[chat_id]['scadenza_riga'] = f"⏳ *Scadenza:* {testo_data}\n"
            bot.send_message(chat_id, f"✅ Data impostata ({testo_data}).\nIl bot eliminerà il post dal canale in automatico.")
            mostra_menu_modifiche(chat_id)
    except ValueError:
        bot.send_message(chat_id, "❌ Formato errato. Usa GG/MM/AAAA (es. 25/12/2026).")
        mostra_menu_modifiche(chat_id)
    except Exception:
        bot.send_message(chat_id, "❌ Errore tecnico.")
        mostra_menu_modifiche(chat_id)

def mostra_selezione_categorie_pubblicazione(chat_id, message_id):
    try:
        dati = post_in_sospeso[chat_id]
        markup = types.InlineKeyboardMarkup(row_width=2)
        pulsanti = []
        
        for codice, cat_info in CAT_DISPONIBILI.items():
            is_selected = codice in dati["categorie_selezionate"]
            testo_btn = f"✅ {cat_info['nome']}" if is_selected else cat_info['nome']
            pulsanti.append(types.InlineKeyboardButton(testo_btn, callback_data=f"pubcat_{codice}"))
            
        markup.add(*pulsanti)
        markup.add(types.InlineKeyboardButton("🚀 CONFERMA E INVIA AI TOPIC", callback_data="conferma_e_pubblica_canale"))
        markup.add(types.InlineKeyboardButton("🔙 Annulla e Torna", callback_data="ritorna_anteprima_diretta"))
        
        testo_selezione = "🏷️ **Seleziona uno o più Topic del Forum dove pubblicare l'offerta:**"
        
        if dati["immagine"]:
            try: bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=testo_selezione, reply_markup=markup, parse_mode="Markdown")
            except: bot.send_message(chat_id, testo_selezione, reply_markup=markup, parse_mode="Markdown")
        else:
            try: bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=testo_selezione, reply_markup=markup, parse_mode="Markdown")
            except: bot.send_message(chat_id, testo_selezione, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        menu_principale(chat_id)

# ==========================================
# 3. SCRAPER (ESTRAZIONE DATI)
# ==========================================

def elabora_link_manuale(message):
    chat_id = message.chat.id
    try:
        if not message.text:
            bot.send_message(chat_id, "❌ Input non valido. Incolla un link testuale di Amazon.")
            menu_principale(chat_id)
            return

        url_utente = message.text.strip()
        
        if "amazon" not in url_utente and "amzn.to" not in url_utente:
            bot.send_message(chat_id, "❌ Link non valido. Incolla un URL di Amazon.")
            menu_principale(chat_id)
            return

        msg_caricamento = bot.send_message(chat_id, "⏳ *Estrazione dati in corso...*", parse_mode="Markdown")

        url_lungo = url_utente
        if "amzn.to" in url_utente:
            try:
                risposta = requests.head(url_utente, allow_redirects=True, timeout=5)
                url_lungo = risposta.url
            except: pass 

        asin_match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', url_lungo)
        if asin_match:
            asin_prodotto = asin_match.group(1)
            link_affiliato = f"https://www.amazon.it/dp/{asin_prodotto}?tag={TAG_AFFILIAZIONE}"
        else:
            connettore = "&" if "?" in url_lungo else "?"
            link_affiliato = f"{url_lungo}{connettore}tag={TAG_AFFILIAZIONE}"

        payload = {'api_key': CHIAVE_SCRAPERAPI, 'url': url_lungo, 'render': 'false'}
        risposta_scraper = requests.get('http://api.scraperapi.com', params=payload, timeout=45)
        
        if risposta_scraper.status_code == 200:
            soup = BeautifulSoup(risposta_scraper.content, 'html.parser')
            
            titolo_elem = soup.find(id='productTitle')
            titolo = titolo_elem.get_text().strip() if titolo_elem else "Prodotto in Offerta su Amazon"
            titolo = re.sub(r'[*_`\[\]]', '', titolo) 
            titolo_pulito = titolo[:120] + "..." if len(titolo) > 120 else titolo

            desc_elem = soup.find(id='feature-bullets')
            if desc_elem:
                punti = desc_elem.find_all('li')
                descrizione_completa = punti[0].get_text().strip() if punti else "Scopri i dettagli sulla pagina."
                descrizione_pulita = descrizione_completa[:150] + "..." if len(descrizione_completa) > 150 else descrizione_completa
                descrizione_pulita = re.sub(r'[*_`\[\]]', '', descrizione_pulita)
            else:
                descrizione_pulita = "Scopri tutti i dettagli sulla pagina ufficiale."
            
            prezzo_attuale = ""
            prezzo_originale = ""
            
            prezzo_elem = soup.select_one('span.priceToPay span.a-offscreen, span.apexPriceToPay span.a-offscreen, #corePriceDisplay_desktop_feature_div .a-price span.a-offscreen')
            if prezzo_elem and any(c.isdigit() for c in prezzo_elem.get_text()):
                prezzo_attuale = prezzo_elem.get_text().strip()
            else:
                prezzo_int_elem = soup.find('span', class_='a-price-whole')
                prezzo_dec_elem = soup.find('span', class_='a-price-fraction')
                if prezzo_int_elem and any(c.isdigit() for c in prezzo_int_elem.get_text()):
                    p_int = prezzo_int_elem.get_text().strip().replace(',', '').replace('.', '')
                    p_dec = re.sub(r'[^\d]', '', prezzo_dec_elem.get_text()) if prezzo_dec_elem else "00"
                    prezzo_attuale = f"{p_int},{p_dec}€"
                else:
                    terzi_elem = soup.select_one('span.a-color-price')
                    if terzi_elem and any(c.isdigit() for c in terzi_elem.get_text()):
                        prezzo_attuale = terzi_elem.get_text().strip()
                    else:
                        prezzo_attuale = "Non visibile"
            
            prezzo_orig_elem = soup.select_one('span.a-price.a-text-price span.a-offscreen, span.basisPrice span.a-offscreen, span.a-text-strike')
            if prezzo_orig_elem and any(c.isdigit() for c in prezzo_orig_elem.get_text()):
                prezzo_originale = prezzo_orig_elem.get_text().strip()

            sconto_badge = ""
            risparmio_badge = ""
            try:
                def parse_prezzo(testo):
                    match = re.search(r'(\d[\d\.\,]*\d|\d)', testo)
                    if match: return float(match.group(1).replace('.', '').replace(',', '.'))
                    return 0.0
                val_attuale = parse_prezzo(prezzo_attuale)
                val_orig = parse_prezzo(prezzo_originale)
                if val_orig > val_attuale and val_attuale > 0:
                    risparmio = val_orig - val_attuale
                    perc_sconto = int(round((risparmio / val_orig) * 100))
                    sconto_badge = f"(-{perc_sconto}%)"
                    risparmio_badge = f"📉 *RISPARMI:* {risparmio:.2f}€\n".replace('.', ',')
            except: pass

            scadenza_badge = ""
            if soup.select_one('label[id^="couponText"]'):
                scadenza_badge = f"⏳ *Scadenza:* Spunta la casella Coupon sulla pagina!\n"
            elif soup.select_one('.a-badge-text[data-a-badge-color="sx-lightning-deal-red"]'):
                scadenza_badge = f"⏳ *Scadenza:* Offerta a tempo, scade a breve!\n"
                
            rating_elem = soup.select_one('span.a-icon-alt')
            rating = rating_elem.get_text().strip().split()[0] if rating_elem else "-" 
            voti_elem = soup.select_one('#acrCustomerReviewText')
            voti = voti_elem.get_text().strip().split()[0] if voti_elem else "0"
            venditore_elem = soup.select_one('#merchant-info a, #sellerProfileTriggerId')
            venditore = venditore_elem.get_text().strip() if venditore_elem else "Amazon"
            
            url_immagine = None
            img_elem = soup.select_one('#landingImage, #imgBlkFront, #main-image')
            if img_elem:
                url_immagine = img_elem.get('data-old-hires') or img_elem.get('src') 

            img_data = None
            if url_immagine:
                try:
                    h = {'User-Agent': 'Mozilla/5.0'}
                    r = requests.get(url_immagine, headers=h, timeout=10)
                    if r.status_code == 200: img_data = r.content
                except: pass

            try: bot.delete_message(chat_id=chat_id, message_id=msg_caricamento.message_id)
            except: pass

            post_in_sospeso[chat_id] = {
                "titolo": titolo_pulito,
                "descrizione": descrizione_pulita,
                "prezzo_riga": f"💰 *Prezzo:* {prezzo_attuale} {sconto_badge}\n",
                "risparmio_riga": risparmio_badge,
                "scadenza_riga": scadenza_badge,
                "scadenza_cancellazione": None, 
                "recensioni_riga": f"⭐ *Recensioni:* {voti} ({rating} / 5.0)\n",
                "venditore_riga": f"🚚 *Venduto da:* _{venditore}_\n\n",
                "link": link_affiliato,
                "immagine": img_data,
                "categorie_selezionate": [] 
            }

            mostra_anteprima(chat_id)
                
        else:
            try: bot.edit_message_text(chat_id=chat_id, message_id=msg_caricamento.message_id, text=f"❌ Errore API Amazon. Riprova.")
            except: bot.send_message(chat_id, f"❌ Errore API. Riprova.")
            menu_principale(chat_id)
            
    except Exception as e:
        bot.send_message(chat_id, "❌ Si è verificato un problema tecnico. Torno al menù.")
        menu_principale(chat_id)

# ==========================================
# 4. ASCOLTATORI (CALLBACK E COMANDI)
# ==========================================

@bot.message_handler(commands=['start'])
def avvia_bot(message):
    try: menu_principale(message.chat.id)
    except: pass

@bot.callback_query_handler(func=lambda call: True)
def gestione_pulsanti(call):
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    
    try:
        bot.clear_step_handler_by_chat_id(chat_id)
        
        if call.data == "torna_principale":
            menu_principale(chat_id, msg_id)
            
        elif call.data == "menu_auto":
            menu_auto(chat_id, msg_id)
            
        elif call.data == "menu_canale":
            menu_canale(chat_id, msg_id)
            
        elif call.data == "menu_manuale":
            bot.answer_callback_query(call.id)
            msg = bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="🔗 **Incolla qui l'URL di Amazon:**", parse_mode="Markdown")
            bot.register_next_step_handler(msg, elabora_link_manuale)

        elif call.data == "pubblica_ora":
            if chat_id in post_in_sospeso:
                bot.answer_callback_query(call.id)
                mostra_selezione_categorie_pubblicazione(chat_id, msg_id)
            else:
                bot.answer_callback_query(call.id, "❌ Post scaduto o non trovato.", show_alert=True)

        elif call.data.startswith("pubcat_"):
            codice_cat = call.data.split("_")[1]
            if chat_id in post_in_sospeso:
                bot.answer_callback_query(call.id)
                dati = post_in_sospeso[chat_id]
                if codice_cat in dati["categorie_selezionate"]:
                    dati["categorie_selezionate"].remove(codice_cat)
                else:
                    dati["categorie_selezionate"].append(codice_cat)
                
                mostra_selezione_categorie_pubblicazione(chat_id, msg_id)
            else:
                bot.answer_callback_query(call.id, "❌ Post scaduto.", show_alert=True)

        elif call.data == "conferma_e_pubblica_canale":
            if chat_id in post_in_sospeso:
                dati = post_in_sospeso[chat_id]
                
                if not dati["categorie_selezionate"]:
                    bot.answer_callback_query(call.id, "❌ Seleziona almeno una stanza!", show_alert=True)
                    return

                for codice in dati["categorie_selezionate"]:
                    cat_info = CAT_DISPONIBILI[codice]
                    if cat_info["thread_id"] is None:
                        bot.answer_callback_query(
                            call.id, 
                            f"⚠️ Crea la categoria '{cat_info['nome']}' sul canale e inserisci il suo ID!", 
                            show_alert=True
                        )
                        return 

                hashtags = [f"#{CAT_DISPONIBILI[c]['tag']}" for c in dati["categorie_selezionate"] if c in CAT_DISPONIBILI]
                stringa_hashtags = " " + " ".join(hashtags) if hashtags else ""
                
                testo_post_canale = (
                    f"‎\n*{dati['titolo']}*\n\n"
                    f"_{dati['descrizione']}_\n\n"
                    f"{dati['prezzo_riga']}"
                    f"{dati['risparmio_riga']}"
                    f"{dati['scadenza_riga']}"
                    f"{dati['recensioni_riga']}"
                    f"{dati['venditore_riga']}"
                    f"{stringa_hashtags}\n\n"
                    f"🛒 [👉 VAI ALL'OFFERTA]({dati['link']})"
                )

                try:
                    pubblicati_con_successo = 0
                    
                    for codice in dati["categorie_selezionate"]:
                        cat_info = CAT_DISPONIBILI[codice]
                        t_id = cat_info["thread_id"] 
                        
                        msg_inviato = None
                        if dati["immagine"]:
                            msg_inviato = bot.send_photo(GRUPPO_ID, photo=dati["immagine"], caption=testo_post_canale, parse_mode="Markdown", message_thread_id=t_id)
                        else:
                            msg_inviato = bot.send_message(GRUPPO_ID, testo_post_canale, parse_mode="Markdown", disable_web_page_preview=False, message_thread_id=t_id)
                        
                        pubblicati_con_successo += 1
                        
                        if dati.get('scadenza_cancellazione'):
                            post_da_cancellare.append({
                                'chat_id': GRUPPO_ID,
                                'message_id': msg_inviato.message_id,
                                'scadenza': dati['scadenza_cancellazione']
                            })
                    
                    bot.answer_callback_query(call.id, f"✅ Pubblicato in {pubblicati_con_successo} stanze!")
                    try: bot.delete_message(chat_id, msg_id)
                    except: pass
                    bot.send_message(chat_id, f"✅ **Post inviato in {pubblicati_con_successo} Topic differenti!**", parse_mode="Markdown")
                    del post_in_sospeso[chat_id]
                    menu_principale(chat_id)
                    
                except Exception as e:
                    bot.answer_callback_query(call.id, f"❌ Errore d'invio: {e}", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "❌ Post scaduto.", show_alert=True)

        elif call.data == "menu_modifica":
            bot.answer_callback_query(call.id)
            mostra_menu_modifiche(chat_id)
            
        elif call.data == "edit_titolo":
            msg = bot.send_message(chat_id, "✍️ Scrivi il **NUOVO TITOLO**:", parse_mode="Markdown")
            bot.register_next_step_handler(msg, chiedi_nuovo_titolo)
            
        elif call.data == "edit_desc":
            msg = bot.send_message(chat_id, "✍️ Scrivi la **NUOVA DESCRIZIONE**:", parse_mode="Markdown")
            bot.register_next_step_handler(msg, chiedi_nuova_descrizione)
            
        elif call.data == "edit_prezzo":
            msg = bot.send_message(chat_id, "✍️ Scrivi il **NUOVO PREZZO** (es. 19,99€):", parse_mode="Markdown")
            bot.register_next_step_handler(msg, chiedi_nuovo_prezzo)
            
        elif call.data == "edit_scadenza":
            msg = bot.send_message(chat_id, "✍️ Scrivi la **DATA DI SCADENZA** in formato GG/MM/AAAA:", parse_mode="Markdown")
            bot.register_next_step_handler(msg, chiedi_nuova_scadenza)

        elif call.data == "ritorna_anteprima":
            bot.answer_callback_query(call.id, "✅ Rigenero l'anteprima...")
            try: bot.delete_message(chat_id, msg_id)
            except: pass
            mostra_anteprima(chat_id)
            
        elif call.data == "ritorna_anteprima_diretta":
            bot.answer_callback_query(call.id)
            mostra_anteprima(chat_id, message_id=msg_id)

        elif call.data == "verifica_canale":
            try:
                chat = bot.get_chat(GRUPPO_ID)
                member = bot.get_chat_member(GRUPPO_ID, bot.get_me().id)
                if member.status in ['administrator', 'creator']:
                    bot.answer_callback_query(call.id, "✅ OK! Bot Amministratore.", show_alert=True)
                else:
                    bot.answer_callback_query(call.id, "⚠️ Bot NON amministratore!", show_alert=True)
            except: bot.answer_callback_query(call.id, "❌ Impossibile connettersi.", show_alert=True)

        elif call.data == "menu_categorie": sottomenu_categorie(chat_id, msg_id)
            
        elif call.data.startswith("cat_"):
            codice_nodo = call.data.split("_")[1]
            if codice_nodo in impostazioni_bot["categorie_scelte"]:
                impostazioni_bot["categorie_scelte"].remove(codice_nodo)
            else:
                impostazioni_bot["categorie_scelte"].append(codice_nodo)
            sottomenu_categorie(chat_id, msg_id)
            
        elif call.data == "salva_categorie":
            bot.answer_callback_query(call.id, "✅ Salvato!")
            menu_auto(chat_id, msg_id) 

        elif call.data == "menu_sconti":
            bot.answer_callback_query(call.id)
            msg = bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="✍️ Sconto min (%):")
            bot.register_next_step_handler(msg, chiedi_sconto)
            
        elif call.data == "filtro_errore":
            impostazioni_bot["errori_prezzo"] = not impostazioni_bot["errori_prezzo"]
            menu_auto(chat_id, msg_id)

    except Exception as e:
        try: bot.answer_callback_query(call.id, "❌ Errore", show_alert=True)
        except: pass
        menu_principale(chat_id)

# ==========================================
# 5. SERVER WEB (FLASK PER RENDER.COM)
# ==========================================

@app.route('/', methods=['GET'])
def ping():
    """Questa pagina serve a cron-job.org per tenere sveglio il bot"""
    return "<h1>Il Bot Amazon è ONLINE! 🚀</h1>", 200

@app.route('/' + TOKEN, methods=['POST'])
def webhook_ricevi_messaggi():
    """Qui Telegram invia i messaggi degli utenti al nostro server"""
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    
    if URL_RENDER != "INSERISCI_QUI_IL_LINK_DI_RENDER":
        # Imposta il ponte invisibile tra Telegram e il tuo server web
        bot.set_webhook(url=f"{URL_RENDER}/{TOKEN}")
        print(f"✅ Webhook impostato su {URL_RENDER}/{TOKEN}")
    else:
        print("⚠️ ATTENZIONE: URL_RENDER non è impostato! Modifica il codice dopo aver ottenuto il link da Render.com")
        
    # Avvia il server Flask. Su Render usa la porta data dal sistema, sul PC usa la porta 5000
    porta = int(os.environ.get("PORT", 5000))
    print(f"🚀 Server web avviato sulla porta {porta}")
    app.run(host="0.0.0.0", port=porta)
