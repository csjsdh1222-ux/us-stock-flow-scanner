import yfinance as yf
import requests
import csv
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

CSV_FILE = "logs/daily_candidates.csv"

SECTORS = {
    "Technology": "XLK",
    "Communication": "XLC",
    "Energy": "XLE",
    "Financials": "XLF",
    "Healthcare": "XLV",
    "Consumer": "XLY"
}

STOCKS = {
    "Technology": ["NVDA", "AMD", "MSFT"],
    "Communication": ["GOOGL", "META"],
    "Financials": ["JPM", "WFC"],
    "Energy": ["XOM", "CVX"],
    "Healthcare": ["JNJ", "PFE"],
    "Consumer": ["AMZN", "TSLA"]
}


def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg
    }

    requests.post(url, data=data, timeout=10)


def get_sector_performance():
    results = []

    for name, ticker in SECTORS.items():
        try:
            data = yf.Ticker(ticker).history(period="2d")

            if len(data) < 2:
                continue

            change = (data["Close"].iloc[-1] - data["Close"].iloc[-2]) / data["Close"].iloc[-2] * 100

            results.append({
                "sector": name,
                "change": round(change, 2)
            })

        except:
            continue

    return sorted(results, key=lambda x: x["change"], reverse=True)


def get_stock_data(ticker):
    try:
        data = yf.Ticker(ticker)
        hist = data.history(period="5d")

        if len(hist) < 2:
            return None

        change = (hist["Close"].iloc[-1] - hist["Close"].iloc[-2]) / hist["Close"].iloc[-2] * 100
        volume_ratio = hist["Volume"].iloc[-1] / hist["Volume"].mean()

        market_cap = data.info.get("marketCap", 0)

        return {
            "change": round(change, 2),
            "volume_ratio": round(volume_ratio, 2),
            "market_cap": market_cap
        }

    except:
        return None


def score_stock(data):
    score = 0

    if data["change"] > 3:
        score += 40
    if data["volume_ratio"] > 1.2:
        score += 30
    if data["market_cap"] > 10_000_000_000:
        score += 10

    return score


def save_to_csv(rows):
    file_exists = os.path.isfile(CSV_FILE)
    existing_keys = set()

    if file_exists:
        with open(CSV_FILE, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                existing_keys.add((r["date"], r["ticker"]))

    os.makedirs("logs", exist_ok=True)

    new_count = 0

    with open(CSV_FILE, mode="a", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)

        if not file_exists:
            writer.writerow(["date", "ticker", "sector", "change", "volume_ratio", "market_cap", "score", "label"])

        for row in rows:
            key = (row["date"], row["ticker"])

            if key in existing_keys:
                continue

            writer.writerow([
                row["date"],
                row["ticker"],
                row["sector"],
                row["change"],
                row["volume_ratio"],
                row["market_cap"],
                row["score"],
                row["label"]
            ])
            new_count += 1

    print(f"CSV 신규 저장 {new_count}건 → {CSV_FILE}")


def main():
    print("\n[MARKET FLOW SCANNER]")
    print("Date:", datetime.now().strftime("%Y-%m-%d"))

    sectors = get_sector_performance()

    print("\nTop Sectors:")
    for i, s in enumerate(sectors[:3], 1):
        print(f"{i}. {s['sector']} {s['change']}%")

    candidates = []

    print("\nScanning leading stocks...")

    for sector in sectors[:3]:
        name = sector["sector"]

        for ticker in STOCKS.get(name, []):
            data = get_stock_data(ticker)

            if not data:
                continue

            score = score_stock(data)

            label = "관찰"
            if score >= 80:
                label = "🔥 강력 후보"
            elif score >= 60:
                label = "관심 후보"

            if score >= 50:
                candidates.append({
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "ticker": ticker,
                    "sector": name,
                    "change": data["change"],
                    "volume_ratio": data["volume_ratio"],
                    "market_cap": data["market_cap"],
                    "score": score,
                    "label": label
                })

    print("\nCandidates:")
    msg = "📊 오늘의 후보 종목\n"

    for c in candidates:
        line = f"{c['ticker']} | {c['sector']} | Score {c['score']} | {c['label']}"
        print(line)
        msg += line + "\n"

    save_to_csv(candidates)

    # 🔥 Telegram 안정화 (핵심)
    try:
        send_telegram(msg)
        print("Telegram 전송 완료")
    except Exception as e:
        print(f"Telegram 실패 → 무시: {e}")


if __name__ == "__main__":
    main()