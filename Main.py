import os
import time
import requests

ADDRESS = os.getenv("ADDRESS", "ltc1qus9m8e8tr78z4vely70apy957e29fu6srg4pm3")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# BlockCypher: Address Full Endpoint (Litecoin mainnet)
API_URL = f"https://api.blockcypher.com/v1/ltc/main/addrs/{ADDRESS}/full?limit=10"

SEEN_FILE = "seen_txids.txt"


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for txid in sorted(seen):
            f.write(txid + "\n")


def send_telegram(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("BOT_TOKEN oder CHAT_ID fehlt (Railway Variables setzen).")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=20)
    r.raise_for_status()


def fetch_txs():
    r = requests.get(API_URL, timeout=20)
    r.raise_for_status()
    return r.json().get("txs", [])


def main():
    seen = load_seen()

    # Beim ersten Start: aktuelle unbestätigte TXs merken, NICHT spammen
    if not seen:
        try:
            txs = fetch_txs()
            for tx in txs:
                if tx.get("confirmations", 0) == 0:
                    seen.add(tx.get("hash"))
            save_seen(seen)
        except Exception:
            pass

    while True:
        try:
            txs = fetch_txs()

            for tx in txs:
                txid = tx.get("hash")
                conf = tx.get("confirmations", 0)

                # nur unbestätigte
                if conf == 0 and txid and txid not in seen:
                    seen.add(txid)
                    save_seen(seen)

                    # Betrag, der an die Adresse geht (satoshi -> LTC)
                    value_to_addr = 0
                    for out in tx.get("outputs", []):
                        if ADDRESS in out.get("addresses", []):
                            value_to_addr += int(out.get("value", 0))

                    ltc_amount = value_to_addr / 100_000_000

                    msg = (
                        "🚨 Neue UNBESTÄTIGTE LTC Transaktion\n\n"
                        f"Adresse: {ADDRESS}\n"
                        f"Betrag an Adresse: {ltc_amount} LTC\n"
                        f"TXID: {txid}\n"
                        f"Explorer: https://litecoinspace.org/tx/{txid}"
                    )
                    send_telegram(msg)

        except Exception:
            # Wenn API kurz down/Rate limit: einfach weiterprobieren
            pass

        time.sleep(20)


if __name__ == "__main__":
    main()
