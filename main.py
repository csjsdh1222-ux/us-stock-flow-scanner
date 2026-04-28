import csv
import os
import requests
import yfinance as yf
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

SECTORS = {
    "Technology": "XLK",
    "Communication": "XLC",
    "Energy": "XLE",
    "Financials": "XLF",
    "Healthcare": "XLV",
    "Consumer": "XLY",
}

SECTOR_STOCKS = {
    "Technology": ["NVDA", "MSFT", "AAPL", "AMD", "AVGO", "ORCL"],
    "Communication": ["META", "GOOGL", "NFLX", "DIS"],
    "Energy": ["XOM", "CVX", "COP"],
    "Financials": ["JPM", "BAC", "GS", "MS", "WFC"],
    "Healthcare": ["LLY", "UNH", "JNJ", "MRK"],
    "Consumer": ["AMZN", "TSLA", "HD", "MCD", "NKE"],
}


def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram 설정 없음: .env 확인 필요")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        response = requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
            },
            timeout=30,
        )

        if response.status_code == 200:
            print("Telegram 알림 전송 완료")
        else:
            print(f"Telegram 전송 실패: {response.status_code} / {response.text}")

    except Exception as e:
        print(f"Telegram 전송 오류: {e}")


def get_sector_performance():
    results = []

    for name, ticker in SECTORS.items():
        try:
            data = yf.Ticker(ticker).history(period="5d")

            if data.empty or len(data) < 2:
                continue

            latest_close = data["Close"].iloc[-1]
            previous_close = data["Close"].iloc[-2]
            change = (latest_close - previous_close) / previous_close * 100

            results.append({
                "sector": name,
                "ticker": ticker,
                "change": round(change, 2)
            })

        except Exception as e:
            print(f"Error fetching sector {name}: {e}")

    return sorted(results, key=lambda x: x["change"], reverse=True)


def get_stock_data(ticker, sector, sector_change):
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="30d")

        if data.empty or len(data) < 2:
            return None

        latest_close = data["Close"].iloc[-1]
        previous_close = data["Close"].iloc[-2]
        change = (latest_close - previous_close) / previous_close * 100

        latest_volume = data["Volume"].iloc[-1]
        avg_volume = data["Volume"].tail(20).mean()
        volume_ratio = latest_volume / avg_volume if avg_volume != 0 else 0

        info = stock.info
        market_cap = info.get("marketCap", 0)

        return {
            "ticker": ticker,
            "sector": sector,
            "change": round(change, 2),
            "volume_ratio": round(volume_ratio, 2),
            "market_cap": market_cap,
            "sector_change": sector_change,
        }

    except Exception as e:
        print(f"Error fetching stock {ticker}: {e}")
        return None


def score_stock(stock):
    score = 0

    if stock["change"] >= 5:
        score += 40
    elif stock["change"] >= 3:
        score += 30
    elif stock["change"] >= 2:
        score += 20
    elif stock["change"] >= 1:
        score += 10

    if stock["volume_ratio"] >= 2:
        score += 30
    elif stock["volume_ratio"] >= 1.5:
        score += 25
    elif stock["volume_ratio"] >= 1.2:
        score += 20
    elif stock["volume_ratio"] >= 1:
        score += 10

    if stock["sector_change"] >= 1:
        score += 25
    elif stock["sector_change"] >= 0.5:
        score += 15
    elif stock["sector_change"] >= 0.2:
        score += 10

    if stock["market_cap"] >= 500_000_000_000:
        score += 20
    elif stock["market_cap"] >= 100_000_000_000:
        score += 15
    elif stock["market_cap"] >= 10_000_000_000:
        score += 10

    return min(score, 100)


def get_label(score):
    if score >= 80:
        return "🔥 강력 후보"
    elif score >= 60:
        return "관심 후보"
    elif score >= 40:
        return "관찰"
    else:
        return "보류"


def scan_leading_stocks(top_sectors):
    candidates = []

    for sector_data in top_sectors:
        sector = sector_data["sector"]
        sector_change = sector_data["change"]

        for ticker in SECTOR_STOCKS.get(sector, []):
            stock = get_stock_data(ticker, sector, sector_change)

            if stock is None:
                continue

            if stock["change"] < 1:
                continue

            if stock["volume_ratio"] < 1:
                continue

            if stock["market_cap"] < 2_000_000_000:
                continue

            stock["score"] = score_stock(stock)
            stock["label"] = get_label(stock["score"])

            candidates.append(stock)

    return sorted(candidates, key=lambda x: x["score"], reverse=True)


def format_market_cap(value):
    if value >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.2f}T"
    elif value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    return str(value)


def save_to_csv(candidates):
    os.makedirs("logs", exist_ok=True)

    file_path = "logs/daily_candidates.csv"
    today = datetime.now().strftime("%Y-%m-%d")

    existing_keys = set()

    if os.path.isfile(file_path):
        with open(file_path, mode="r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            for row in reader:
                existing_keys.add((row["date"], row["ticker"]))

    file_exists = os.path.isfile(file_path)

    with open(file_path, mode="a", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)

        if not file_exists or os.path.getsize(file_path) == 0:
            writer.writerow([
                "date",
                "ticker",
                "sector",
                "change",
                "volume_ratio",
                "market_cap",
                "score",
                "label"
            ])

        saved_count = 0

        for stock in candidates:
            key = (today, stock["ticker"])

            if key in existing_keys:
                continue

            writer.writerow([
                today,
                stock["ticker"],
                stock["sector"],
                stock["change"],
                stock["volume_ratio"],
                stock["market_cap"],
                stock["score"],
                stock["label"]
            ])

            saved_count += 1

    print(f"\nCSV 신규 저장 {saved_count}건 → logs/daily_candidates.csv")


def build_telegram_report(candidates):
    strong_candidates = [s for s in candidates if s["score"] >= 80]

    if not strong_candidates:
        return None

    lines = []
    lines.append("🔥 미국주식 수급 강력 후보 발생")
    lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")

    for stock in strong_candidates:
        lines.append(
            f"{stock['ticker']} | {stock['sector']} | "
            f"Change {stock['change']}% | "
            f"Volume {stock['volume_ratio']}x | "
            f"Score {stock['score']} | {stock['label']}"
        )

    lines.append("")
    lines.append("※ 투자 추천이 아닌 데이터 기반 관심 후보입니다.")

    return "\n".join(lines)


def main():
    print("\n[MARKET FLOW SCANNER]")
    print("Date:", datetime.now().strftime("%Y-%m-%d"))

    sectors = get_sector_performance()

    print("\nTop Sectors:")
    for i, s in enumerate(sectors[:3], 1):
        print(f"{i}. {s['sector']} ({s['ticker']}) {s['change']}%")

    print("\nScanning leading stocks...")
    candidates = scan_leading_stocks(sectors[:3])

    print("\nCandidates:")
    if not candidates:
        print("No candidates found today.")
        return

    for stock in candidates:
        print(
            f"{stock['ticker']} | "
            f"{stock['sector']} | "
            f"Change {stock['change']}% | "
            f"Volume {stock['volume_ratio']}x | "
            f"Cap {format_market_cap(stock['market_cap'])} | "
            f"Score {stock['score']} | "
            f"{stock['label']}"
        )

    save_to_csv(candidates)

    telegram_message = build_telegram_report(candidates)
    if telegram_message:
        send_telegram_message(telegram_message)
    else:
        print("Telegram 알림 대상 없음: 강력 후보 없음")


if __name__ == "__main__":
    main()